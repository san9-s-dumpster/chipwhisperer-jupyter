"""A deliberately invented leakage model, not a hardware emulator."""
from dataclasses import asdict, dataclass
import numpy as np
from analysis.ground_truth import ground_truth, output_digest
from capture.records import Capture


@dataclass
class MockSettings:
    rng_seed: int = 20261028
    noise_sd: float = 0.85
    variable_time_strength: float = 1.2
    fls_strength: float = 0.55
    prefix: int = 64
    samples_per_candidate: int = 12
    timing_noise_sd: float = 0.5


class MockBackend:
    def __init__(self, settings=None):
        self.settings = settings or MockSettings()
        if self.settings.noise_sd < 0 or self.settings.samples_per_candidate < 4:
            raise ValueError("invalid mock noise or segment size")
        self.rng = np.random.default_rng(self.settings.rng_seed)

    def capture(self, seed, x=0, y=0, variant="variable_time"):
        truth = ground_truth(seed,x,y,variant)
        if not truth.complete:
            raise RuntimeError("sampler did not fill the output within its cap")
        cfg, rng = self.settings, self.rng
        width = cfg.samples_per_candidate
        wave = rng.normal(0,cfg.noise_sd,cfg.prefix+len(truth.candidates)*width+32)
        pulse = np.sin(np.linspace(0,np.pi,width))
        strength = cfg.variable_time_strength if variant == "variable_time" else cfg.fls_strength
        for i,(value,valid) in enumerate(zip(truth.candidates,truth.valid)):
            start = cfg.prefix+i*width
            # Inject both validity-related activity and candidate switching.
            amplitude = strength * (1.6*int(valid)+0.05*(value.bit_count()-6))
            wave[start:start+width] += amplitude*pulse
        duration = cfg.prefix+len(truth.candidates)*width+rng.normal(0,cfg.timing_noise_sd)
        return Capture(wave.astype(np.float32),truth.to_dict(),{
            "backend":"mock", "synthetic":True,
            "timing_value":float(duration),"timing_unit":"synthetic ADC samples",
            "full_operation_captured":True,"settings":asdict(cfg),
            "verification_digest":output_digest(truth.coefficients).hex(),
            "warning":"Leakage and duration are injected by this model; no hardware evidence."})
