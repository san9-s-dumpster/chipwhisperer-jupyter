# Husky + CW308_STM32F4 capture protocol

The active notebook lives one directory above this companion folder. Its
programming cells use STM32FProgrammer and its recorder attaches to the same
`scope`/`target` objects, without opening a second device session.

The setup uses external HS2 clock near 7.3728 MHz, SimpleSerial 1.1 at 38400
baud, TIO1 serial RX, TIO2 TX, and TIO4 basic rising-edge trigger. Keep the
known-working target power/shunt/probe/jumper settings. Record the board,
MCU, wiring and physical changes in your run notes. Software records device
serial, measured clocks, gain, window, compiler, source and image hashes.

Builds (from the companion folder) do not access hardware:

```bash
python -m firmware.build --chipwhisperer "$HOME/Desktop/work/chipwhisperer-new" \
  --platform CW308_STM32F4 --variant variable_time
python -m firmware.build --chipwhisperer "$HOME/Desktop/work/chipwhisperer-new" \
  --platform CW308_STM32F4 --variant variable_time --profile calibration
```

Every build is clean. Separate directories prevent cross-profile object reuse.
The ordinary image excludes calibration code. Upstream source hashes are
checked before compilation. FLS is retained as source but deferred from the
active notebook.

## Serial commands

- `p`: 34 bytes `rho || x || y`; `r`: 32-byte SHA3-256(LE16(output[256])).
- `i`: zero-byte identity request; `i`: 21 bytes. Byte 0 bit 0 selects FLS;
  bit 7 marks calibration. The remaining 20 bytes are the upstream revision.
- Calibration only, `t`: zero-byte request after a sample; `t`: six LE32 words
  (first squeeze entry, return, second entry, return, total cycles, call count).
- SimpleSerial `z00` acknowledgement follows successful replies. `v`, `w`,
  and `y` are library commands and are not reused by the application.

The trigger covers only the upstream sampler. Coefficient zeroing, output
encoding, SHA3 digest verification and all UART replies occur outside it.
The calibration adapter uses volatile DWT counter reads and the linker wrapper;
it never sends data while the trigger is high. Calibration timing overhead
means these waveforms cannot be used as representative training/test data.

## ADC settings and units

Survey at multiplier 1, offset 0, up to 130000 samples within the reported
buffer capacity. Require full trigger coverage. Batches use multiplier 4 and
a short delayed window around the first pair; partial operation coverage is
intentional. Non-streaming, one segment, zero presamples, decimation 1.
Read trigger count only after the complete target reply, when TIO4 is low.
Its units are ADC clock cycles. Divide by actual `scope.clock.adc_freq` to
obtain duration; host round-trip time is not the operation duration.

The recorder explicitly requests `get_last_trace(as_int=True)` and saves raw
ADC codes as float32; metadata records units and ADC resolution. For a 12-bit
ADC, normalized voltage units are `codes/4096 - 0.5`. Plots label raw codes.

Start near the previously usable 10 dB gain. Clipping, FIFO errors, missing
replies, invalid digests, timeouts and short/nonfinite arrays stop acquisition.
Do not disable clipping detection. To inspect a rejected capture manually:

```python
raw = scope.get_last_trace(as_int=True)
print(scope.adc.errors, np.min(raw), np.max(raw))
plt.plot(raw)
```

Lower gain and rerun the survey before model data collection. A hardware
condition change after development begins requires a fresh run. Mixed
settings fail analysis instead of being pooled.

For the buffer/offset and trigger-counter definitions, see the official
[scope API](https://chipwhisperer.readthedocs.io/en/latest/scope-api.html).
The [Husky manual](https://chipwhisperer.readthedocs.io/en/latest/Capture/ChipWhisperer-Husky.html)
describes ADC limits and clocking. This notebook does not update capture-board
firmware. Disconnect the old notebook before opening this connection.


## Fresh-session connection failures

The notebook reloads the bundled FPGA configuration using
`cw.scope(force=True, prog_speed=1_000_000)` before setting the lab clock and
I/O. This loads volatile FPGA configuration, separately from USB firmware
updates. An earlier `Unknown hwInfoVer: Default/Unknown` / `Unknown
ChipWhisperer` error means connection did not finish. Stop at that error; no
verified recorder exists yet. Saved programming output from another kernel
does not establish current state. Run both section 4 cells after section 3
succeeds. Survey now checks this prerequisite before acquisition.

If the connection still fails, close other device-owning kernels, reconnect
USB, restart the kernel and retry section 3. Do not proceed with capture after
a connection failure.
