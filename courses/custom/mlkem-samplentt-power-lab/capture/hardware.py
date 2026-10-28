"""Opt-in CW-Lite/Husky acquisition; hardware validation is still required."""
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import numpy as np
from analysis.ground_truth import encode_input, ground_truth, output_digest
from capture.records import Capture


@dataclass
class HardwareSettings:
    model: str
    target_platform: str
    build_json: str
    scope_serial: str
    target_clock_hz: int = 7372800
    adc_multiplier: int = 4
    samples: int = 24000
    offset: int = 0
    gain_db: float = 25.0
    baud: int = 38400
    timeout_seconds: float = 5.0
    stream_mode: bool = False


class HardwareBackend:
    @staticmethod
    def _load_build(settings):
        build_path = Path(settings.build_json).resolve()
        build = json.loads(build_path.read_text())
        if build.get("profile") not in ("measurement", "calibration"):
            raise ValueError("firmware build manifest has a missing/invalid profile; rerun the notebook build cell to reload the current builder and regenerate build.json")
        if build["target_platform"] != settings.target_platform:
            raise ValueError("firmware build and selected target do not match")
        image = Path(build["image"])
        if not image.is_file():
            image = build_path.parent / image.name
        if hashlib.sha256(image.read_bytes()).hexdigest() != build["firmware_sha256"]:
            raise ValueError("firmware image differs from recorded build")
        return build

    def verify_firmware(self):
        """Check the selected variant/revision on an already connected target."""
        self.target.flush()
        self.target.simpleserial_write('i', bytearray())
        info = self.target.simpleserial_read(
            'i', 21, timeout=int(1000*self.settings.timeout_seconds))
        mode = int(self.build["variant"] == "fls") | (0x80 if self.build.get("profile") == "calibration" else 0)
        expected = bytes([mode])+bytes.fromhex(self.build["source_commit"])
        if info is None or bytes(info) != expected:
            raise RuntimeError("firmware identity handshake failed (command i); rebuild and program the ML-KEM target adapter, then reset the target")

    @classmethod
    def from_connected(cls, scope, target, settings, cw_version="unknown"):
        """Use the notebook's scope/target without reconnecting or reconfiguring.

        Build and program the target in visible notebook cells first. This
        attaches verification and recording to those exact device objects.
        """
        if settings.model not in ("Lite", "Husky"):
            raise ValueError("supported capture model settings: Lite or Husky")
        if ("husky" in str(scope).lower()) != (settings.model == "Husky"):
            raise ValueError("connected capture model differs from requested model")
        if int(scope.adc.samples) != settings.samples or int(scope.adc.offset) != settings.offset:
            raise ValueError("scope window differs from recording settings; recreate the session")
        obj = cls.__new__(cls)
        obj.settings, obj.scope, obj.target = settings, scope, target
        obj.build = cls._load_build(settings)
        obj.snapshot, obj.cw_version = str(scope), cw_version
        obj.verify_firmware()
        return obj

    def __init__(self, settings):
        if settings.model not in ("Lite","Husky"):
            raise ValueError("supported capture model settings: Lite or Husky")
        if not settings.scope_serial or not settings.target_platform:
            raise ValueError("supply the scope serial and target platform")
        if settings.samples < 2 or settings.offset < 0 or settings.adc_multiplier not in (1,4):
            raise ValueError("invalid sample window or ADC multiplier (1 or 4)")
        self.settings = settings
        self.build = self._load_build(settings)
        import chipwhisperer as cw  # Mock mode never imports or opens hardware.
        self.scope, self.target = None, None
        try:
            self.scope = cw.scope(sn=settings.scope_serial)
            scope = self.scope
            is_husky = "husky" in str(scope).lower()
            if is_husky != (settings.model == "Husky"):
                raise ValueError("connected capture model differs from requested model")
            scope.default_setup()
            scope.clock.clkgen_freq = settings.target_clock_hz
            if settings.model == "Husky":
                scope.clock.adc_mul = settings.adc_multiplier
            else:
                scope.clock.adc_src = "clkgen_x4" if settings.adc_multiplier == 4 else "clkgen_x1"
            scope.gain.db = settings.gain_db
            if settings.model == "Husky":
                scope.adc.stream_mode = settings.stream_mode
            scope.adc.samples = settings.samples
            scope.adc.offset = settings.offset
            scope.adc.presamples = 0
            scope.adc.basic_mode = "rising_edge"
            scope.adc.timeout = settings.timeout_seconds
            scope.trigger.triggers = "tio4"
            scope.io.tio1, scope.io.tio2 = "serial_rx","serial_tx"
            scope.io.hs2 = "clkgen"
            self.target = cw.target(scope,cw.targets.SimpleSerial)
            self.target.baud = settings.baud
            # Hardware quantizes requested gain/clock; record actual settings.
            settings.gain_db = float(scope.gain.db)
            settings.target_clock_hz = float(scope.clock.clkgen_freq)
            self.verify_firmware()
            self.snapshot = str(scope)
            self.cw_version = cw.__version__
        except BaseException:
            self.close()
            raise

    def capture(self, seed, x=0, y=0, variant="variable_time"):
        self._check_live_settings()
        if variant != self.build["variant"]:
            raise ValueError("requested variant does not match the flashed firmware")
        truth = ground_truth(seed,x,y,variant)
        if not truth.complete:
            raise ValueError("fixed schedule shortfall: exclude and record this generated seed")
        scope, target = self.scope, self.target
        target.flush()
        if self.settings.model == "Husky":
            scope.adc.errors = 0
        scope.arm()
        target.simpleserial_write('p',bytearray(encode_input(seed,x,y)))
        try:
            if scope.capture():
                raise TimeoutError("ADC capture timed out")
        except BaseException as capture_error:
            # The SDK can leave fast SMC timing active if ADC download raises.
            # Restore normal register access before propagating the original error.
            if self.settings.model == "Husky" and not self.settings.stream_mode:
                try:
                    scope.sc.setFastSMC(0)
                except Exception as cleanup_error:
                    if hasattr(capture_error, "add_note"):
                        capture_error.add_note(f"Normal bus-mode cleanup also failed: {cleanup_error}")
            raise
        # This reply occurs after trigger_low, including when only an early
        # window was captured. trig_count is meaningless while trigger is high.
        response = target.simpleserial_read('r',32,timeout=int(1000*self.settings.timeout_seconds))
        if response is None or bytes(response) != output_digest(truth.coefficients):
            raise RuntimeError("missing/incorrect polynomial verification digest")
        if self.settings.model == "Husky" and scope.adc.errors:
            raise RuntimeError(f"ADC reported errors: {scope.adc.errors}")
        # Explicit raw ADC codes: ChipWhisperer versions have different defaults.
        wave = np.asarray(scope.get_last_trace(as_int=True),dtype=np.float32).copy()
        if len(wave) != self.settings.samples or not np.isfinite(wave).all():
            raise RuntimeError("short or non-finite ADC trace")
        ticks = int(scope.adc.trig_count)
        adc_hz = float(scope.clock.adc_freq)
        if ticks <= 0 or adc_hz <= 0:
            raise RuntimeError("invalid trigger counter or ADC clock measurement")
        return Capture(wave,truth.to_dict(),{
            "backend":"chipwhisperer","synthetic":False,
            "wave_units":"ADC codes", "adc_bits":int(getattr(scope.adc,"bits_per_sample",12 if self.settings.model == "Husky" else 10)),
            "timing_value":ticks,"timing_unit":"ADC clock cycles",
            "adc_frequency_hz":adc_hz,"duration_seconds":ticks/adc_hz,
            "full_operation_captured":self.settings.offset == 0 and len(wave) >= ticks,
            "settings":asdict(self.settings),"firmware_build":self.build,
            "scope_snapshot":self.snapshot,"chipwhisperer_version":self.cw_version,
            "verification_digest":bytes(response).hex(),
            "sample_window_start":self.settings.offset})

    def _check_live_settings(self):
        """Do not label new captures with an outdated recorder snapshot."""
        scope, s = self.scope, self.settings
        actual = [int(scope.adc.samples), int(scope.adc.offset), float(scope.gain.db),
                  int(self.target.baud), float(scope.clock.clkgen_freq)]
        expected = [s.samples, s.offset, s.gain_db, s.baud, s.target_clock_hz]
        if s.model == 'Husky':
            actual += [int(scope.clock.adc_mul), bool(scope.adc.stream_mode)]
            expected += [s.adc_multiplier, s.stream_mode]
        if not np.allclose(actual, expected, rtol=1e-6, atol=1e-3):
            raise ValueError('live capture settings changed; recreate the recorder and start a new experiment if model data already exist')

    def calibration_timing(self):
        """Read cycle boundaries after a capture of the calibration build only."""
        if self.build.get("profile") != "calibration":
            raise ValueError("timing markers require the separate calibration firmware")
        self.target.simpleserial_write('t', bytearray())
        raw = self.target.simpleserial_read('t', 24, timeout=int(1000*self.settings.timeout_seconds))
        if raw is None or len(raw) != 24:
            raise RuntimeError("missing calibration timing reply")
        values = np.frombuffer(bytes(raw), dtype='<u4').astype(np.int64).tolist()
        a,b,c,d,total,calls = values
        if not 0 < a < b < c < d < total or calls < 128:
            raise RuntimeError("invalid DWT cycle boundaries; do not infer a window from these")
        return dict(zip(("first_squeeze_start","first_squeeze_return","second_squeeze_start",
                         "second_squeeze_return","total_cycles","squeeze_calls"), values))

    def close(self):
        try:
            if self.target is not None:
                self.target.dis()
        finally:
            if self.scope is not None:
                self.scope.dis()
