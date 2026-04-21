# Command Reference

All commands run from the repo root with the venv active.

---

## If you used the legacy code

The legacy workflow had three separate pieces. Here is how each maps to CLI commands:

**Legacy Phase 1 — `Arduino_DAC_control_sketch.ino`**
Power rail firmware (LDO/INA219 control, DIO, LED, ADC reads). Had to be flashed separately.
→ Now replaced by a single unified firmware. Flash it once with `dacdemo flash`.

**Legacy Phase 2 — `legacy_8027_DAC_Arduino_test.py`**
Python script that sent serial commands to the Phase 1 Arduino (SET_VOLTAGE, READ_VOLTAGE, etc.).
→ `dacdemo bias` sets rail voltages. `dacdemo health` reads voltage/current/power per rail.
The underlying serial protocol is identical — the same command strings are sent.
The legacy script called SET_VOLTAGE twice with slightly different values. The current CLI sends it exactly once with all five rails.

**Legacy Phase 3 — `sine_din_h.ino`**
A separate Arduino sketch that auto-ran once in `loop()` and loaded a hardcoded sine into the DAC — no serial control.
→ `dacdemo play-sine` sends `DAC_PLAY_SINE` over serial. The firmware computes and loads the sine, then enables the pattern. You no longer need to reflash to change `F_OUT` or `F_SAMPLE`.

**Key change: one firmware, not two sketches.**
You used to have to choose which sketch to flash. The new firmware handles both rail control and DAC sine loading. Flash once; drive everything from CLI commands.

| Legacy | CLI equivalent |
|---|---|
| Flash `Arduino_DAC_control_sketch.ino` | `dacdemo flash` |
| Flash `sine_din_h.ino` | `dacdemo flash` (same firmware) |
| Run `legacy_8027_DAC_Arduino_test.py` | `dacdemo bias` + `dacdemo health` |
| Sine auto-starts on Arduino boot | `dacdemo play-sine` |
| Run both phases together | `dacdemo run-demo` |

**Still need the original two-sketch legacy flow?** Use `dacdemo legacy`. It runs detect-port → flash `legacy/sketch/Arduino_DAC_control_sketch/` → bias, then pauses for you to physically connect the DUT socket, then flashes `legacy/sketch/sine_din_h/`. See the `legacy` section below.

---

## Config ownership

`config/dacdemo.toml` has two kinds of fields: **inputs** (set by the user or back-calculated) and **derived** (always written by `dacdemo calc` — do not edit manually).

| Key | Section | Kind | Set by |
|---|---|---|---|
| `fs_app` | `[coherent_tone]` | input | edit TOML or `calc --fs-app` |
| `x_seed` | `[coherent_tone]` | input | edit TOML, `calc --x-seed`, or `calc --from-fout` |
| `fin` | `[coherent_tone]` | input | edit TOML or `calc --from-fout` |
| `num_samples` | `[dac]` | hardware constant | edit TOML only |
| `f_sample` | `[dac]` | **derived** | `dacdemo calc` |
| `f_out` | `[dac]` | **derived** | `dacdemo calc` |

**Rule:** only edit `[coherent_tone]` inputs and `num_samples`. Everything else in `[dac]` is computed. Run `dacdemo calc` after any change to `[coherent_tone]` to keep the config in sync.

For this coherent-tone flow, `f_out` is not independent of `f_sample`. With `num_samples = N` fixed, tones are generated on coherent bins:
`f_out = k × f_sample / N`
where `k` is the selected prime bin.

---

## Activate venv

```
.venv\Scripts\activate
```

---

## 1. Auto-detect board port and save to config

```
dacdemo detect-port
```

Finds the Adafruit board by USB VID and writes the port to `config/dacdemo.toml`.
Run this once after plugging in, or any time you change USB ports.

---

## 2. Auto-detect instrument addresses and save to config

```
dacdemo detect-instruments
```

Queries the VISA resource manager for the R&S SMA100B signal generator, Keysight N9010B EXA signal analyzer, and Keysight oscilloscope. Identifies each by IDN and writes `siggen_addr`, `sa_addr`, and `scope_addr` directly into `config/dacdemo.toml`. If the same instrument appears under multiple VISA resources, duplicates are removed automatically. If multiple distinct instruments of the same type are found, you are prompted to pick one.

```
dacdemo detect-instruments --subnet 192.168.10
```

Also scans the given LAN subnet for instruments not yet registered in the VISA resource manager.

Run this once when setting up a new bench, or any time an instrument changes IP address.

---

## 2. No-hardware checks (run any time)

```
dacdemo list-ports
```
Lists all serial ports visible to the OS. Confirm your board's port appears.

```
dacdemo calc
```
Computes the coherent tone plan from `[coherent_tone]` in `config/dacdemo.toml` and **writes the result back into `[dac]`**.

The derivation chain:
- `fs_app` → `fs_actual = fs_app × 2^20` → written as `f_sample`
- `x_seed` → nearest pair of prime FFT bins (`prime_bins`)
- `fin` (`"low"` or `"high"`) → selects which prime bin → written as `f_out`

Equivalent view:
- choose `f_sample`
- hold `num_samples = N` fixed
- choose coherent bin `k`
- get `f_out = k × f_sample / N`

`multiplier` (the `2^20` scale factor) is a fixed constant in code — not a config param.
`num_samples` comes from `[dac]` — not duplicated in `[coherent_tone]`.

Saves the full plan to `data/coherent_tone_plan.json`. No hardware needed.

**Run `calc` any time you change `[coherent_tone]` params.** Everything downstream (`gen-sine`, `play-sine`, `run-demo`, `set-siggen`) reads `f_out` and `f_sample` from `[dac]`.

**Forward workflow — change the clock or bin:**
```
# Edit fs_app or x_seed in dacdemo.toml, then:
dacdemo calc
dacdemo set-siggen        # sends new f_sample to R&S
dacdemo play-sine         # uses new f_out + f_sample
```

**Forward workflow — change bin only (f_sample unchanged):**
```
dacdemo calc --x-seed 7
# finds primes near 7 → [5, 7], uses fin from config to pick f_out
# f_sample unchanged (fs_app unchanged)
```

**Back-calculation — start from a desired f_out:**
```
dacdemo calc --from-fout 61.44e6
# finds the prime bin closest to 61.44 MHz given current f_sample
# updates x_seed and fin in [coherent_tone], then runs forward calc
# f_sample + f_out written back to [dac]
```

**Override fs_app and write to TOML:**
```
dacdemo calc --fs-app 5000
```

```
dacdemo gen-sine
```
Generates the sine code table from `[dac] f_out` and `[dac] f_sample` and saves it to `data/generated_patterns/sine_codes.json`. Pass `--f-out` / `--f-sample` to override for a one-off frequency without touching the config. No hardware needed.

---

## 3. Board connected — serial link test (no chip required)

```
dacdemo detect-port
```
Run again to confirm port is correct after connecting.

```python
python -c "from dacdemo.board_control import BoardSession; s=BoardSession.open('COM5'); print(s.led_on()); print(s.led_off()); s.close()"
```
Toggles the onboard LED. Confirms serial link is alive and firmware is responding.
Replace `COM5` with your port if not using config directly.

---

## 4. Rail health read (no chip required, board powered)

```
dacdemo health
```
Reads voltage, shunt voltage, current, and power from all rails via INA219.
Safe to run without chip in socket — read-only, does not set any voltages.

---

## 5. DAC pattern load and enable (no chip required)

```
dacdemo gen-sine
```
Generate the pattern first (or skip if already done). Reads `f_out` and `f_sample` from `[dac]`.

```
dacdemo play-sine
```
Loads and enables the sine pattern in one command. Equivalent to `dac_load_sine` + `dac_enable_pattern` over serial.

---

## 6. Bias rails (DO NOT run with chip in socket until compliance fix is applied)

```
dacdemo bias --initialize-compliance
```
Sets rail voltages from `config/dacdemo.toml` `[rails]`. The `--initialize-compliance`
flag resets current limits before applying voltages.

### Pre-connect wrapper — `dacdemo prep`

```
dacdemo prep --initialize-compliance
```
One-shot wrapper that runs `detect-port` → `calc` → `flash` → `bias` with numbered banners at each step and prints `Prep complete. Safe to connect the socket now.` when finished. The `calc` step refreshes derived `[dac]` values (`f_sample`, `f_out`) from the current `[coherent_tone]` config before firmware/programming steps continue. Same flags as the underlying commands (`--fqbn`, `--sketch`, `--port`, `--baudrate`, `--initialize-compliance`) — each omitted flag falls back to config. Intended for the pre-socket sequence; do not run with the DUT already seated.

### Legacy two-sketch wrapper — `dacdemo legacy`

```
dacdemo legacy --initialize-compliance
```
Runs the original two-sketch workflow end-to-end:
1. `detect-port`
2. `flash legacy/sketch/Arduino_DAC_control_sketch/`
3. `bias` (reads all rails from `[rails]`; same serial protocol as the unified firmware)
4. Prints `>>> Connect the DUT socket now. <<<` and waits for Enter.
5. `flash legacy/sketch/sine_din_h/` — the sine auto-runs in `loop()` after boot.

Use `--no-prompt` for scripted runs (skips the pause; assumes the socket is already connected).

---

## 7. Full demo sequence (chip in socket, after compliance fix)

```
dacdemo run-demo --initialize-compliance
```
Runs the full sequence: compliance init → bias rails → read back voltages → load and enable sine pattern.
Reads `f_out` and `f_sample` from `[dac]`. Pass `--f-out` / `--f-sample` to override for a one-off run.

---

## 8. Signal generator (R&S SMA100B over LAN)

```
dacdemo set-siggen
```
Sends `f_sample` from `[dac]` to the signal generator (CW mode, level from `siggen_level_dbm`). Use after `dacdemo calc` to push the new clock frequency to the instrument.

```
dacdemo set-siggen --level -10
```
Override output level (dBm) for this run only.

```
dacdemo set-siggen --freq 5.24288e9
```
Override `f_sample` directly. Updates `f_sample` in `[dac]` config and prints the coherent `f_out` options for the new frequency. Also back-calculates `fs_app` from the new frequency and writes it to `[coherent_tone]`, keeping both config sections in sync.

```
dacdemo set-siggen --off
```
Turn RF output off without closing the connection.

---

## 9. Digital capture (AD3 logic analyzer)

The AD3 must be closed in the WaveForms GUI before running — it requires exclusive access.

Wiring (as labelled in `host/dacdemo/ad3_capture.py`):

| DIO | ItsyBitsy pin | Signal |
|---|---|---|
| 0 | 1 | SPI_SCK_PAT (bit clock) |
| 1 | 12 | SPI_SCAN (HIGH during control word) |
| 4 | 9 | DIN_PAT (serial data) |
| 5 | 13 | WR_PAT (HIGH during data burst) |
| 6 | 7 | EN_PAT (pattern enable) |
| 7 | SDA | I2C SDA (INA219) |

```
dacdemo capture
```
Arms the AD3 logic analyzer (hardware trigger on `SPI_SCAN` rising edge), runs the DAC demo over serial, waits for the SPI transaction, then decodes and validates the captured signals. Saves to `data/captures/`:
- `capture_raw.csv` — raw 16-bit DIO samples with per-channel bit columns
- `decoded_words.csv` — 256 decoded 12-bit words vs expected sine, with pass/fail per word

```
dacdemo capture --no-validate
```
Capture and decode only — skip comparison against expected pattern.

```
dacdemo capture --output-dir PATH
```
Write CSV files to a custom directory instead of `data/captures/`.

The same logic runs as a standalone script: `python tools/capture_validate.py`

---

## 10. Oscilloscope measurements (Keysight MSOS054A over LAN)

```
dacdemo scope-measure
```
Connects to the scope, measures CH1, prints results, and appends a timestamped row to `data/captures/scope_measurements.csv`.

Measurements: `frequency_hz`, `vpp_v`, `rise_time_s`, `fall_time_s`, `duty_cycle_pct`.
Values reported as `None` if the scope returned a sentinel (no signal or out of range).

```
dacdemo scope-measure --channel 2
```
Measure a different channel.

```
dacdemo scope-measure --screenshot
```
Also save a PNG screenshot to `data/captures/scope_screenshot.png`.

```
dacdemo scope-measure --output PATH
```
Write measurements CSV to a custom path.

---

## 11. Signal Analyzer measurements (Keysight N9010B EXA over LAN)

### Peak power — `sa-measure`

```
dacdemo sa-measure
```
Connects to the N9010B, configures a spectrum view centered on `dac.f_out` with a 2 MHz span (10 kHz RBW/VBW, 0 dBm reference level), runs one sweep, places a peak marker, and appends a timestamped row to `data/captures/sa_measurements.csv`.

Measurements: `center_hz`, `span_hz`, `rbw_hz`, `vbw_hz`, `ref_level_dbm`, `peak_freq_hz`, `peak_amp_dbm`.

```
dacdemo sa-measure --center 12.288e6 --span 5e6
```
Override center frequency and span for this run.

```
dacdemo sa-measure --rbw 1e3 --vbw 1e3
```
Narrow the resolution and video bandwidth for finer frequency resolution.

```
dacdemo sa-measure --ref -10
```
Lower the reference level (dBm) to zoom in on a weak signal.

```
dacdemo sa-measure --screenshot
```
Also save a PNG screenshot to `data/captures/sa_screenshot.png`.

```
dacdemo sa-measure --output PATH
```
Write measurements CSV to a custom path.

---

### Single-tone SFDR - `sa-sfdr`

```
dacdemo sa-sfdr
```
Measures SFDR at the current `dac.f_out`. Runs one sweep with the SA window fixed at the full Nyquist band (center = `f_sample/4`, span = `f_sample/2`, RBW = 100 kHz, VBW = 10 kHz), places marker 1 on the highest peak (fundamental) and marker 2 on the next-lower peak (worst spur). Appends a timestamped row to `data/captures/sa_sfdr.csv`.

Measurements: `center_hz`, `span_hz`, `rbw_hz`, `vbw_hz`, `ref_level_dbm`, `fund_freq_hz`, `fund_amp_dbm`, `spur_freq_hz`, `spur_amp_dbm`, `sfdr_dbc`.

If no second peak is found (instrument error 780), `spur_freq_hz`, `spur_amp_dbm`, and `sfdr_dbc` are written as `nan` — pandas reads these as `NaN` automatically.

```
dacdemo sa-sfdr --center 266e6 --span 500e6
```
Override the SA window for this run.

```
dacdemo sa-sfdr --screenshot --output PATH
```
Also save a PNG screenshot; write CSV to a custom path.

---

### Single-tone SNR - `sa-snr`

```
dacdemo sa-snr
```
Measures SNR at the current `dac.f_out`. Runs one sweep, places the fundamental at the highest trace peak, then estimates the noise floor from nearby left/right trace windows while excluding the fundamental and predicted 2nd-5th harmonics. Appends a timestamped row to `data/captures/sa_snr.csv`.

Formula:
`snr_db = fund_amp_dbm - (noise_level_dbm + 10*log10(noise_bw_hz / rbw_hz))`

By default `noise_bw_hz = span_hz`, so the integrated noise bandwidth tracks the acquisition span unless you override it.

Measurements include: `center_hz`, `span_hz`, `rbw_hz`, `vbw_hz`, `ref_level_dbm`, `fund_freq_hz`, `fund_amp_dbm`, `noise_freq_hz`, `noise_left_freq_hz`, `noise_left_dbm`, `noise_right_freq_hz`, `noise_right_dbm`, `noise_level_dbm`, `noise_bandwidth_hz`, `noise_exclusion_hz`, `noise_method`, `snr_db`.

```
dacdemo sa-snr --center 266e6 --span 50e6 --noise-bw 10e6
```
Override the SA window and the integrated noise bandwidth.

```
dacdemo sa-snr --rbw 30e3 --vbw 10e3 --screenshot
```
Change RBW/VBW and also save a PNG screenshot.

---

### SFDR frequency sweep - `sa-sfdr-sweep`

Iterates the DAC output tone across a set of target frequencies, reprograms the DAC at each step, measures SFDR from the signal analyzer, and appends one row per step to a CSV.

**Frequency quantization:** target frequencies are first clipped to Nyquist (`f_sample / 2`), then snapped to the nearest in-band prime FFT bin: `tone_hz_actual = prime_bin × f_sample / num_samples`. The requested target and the actual frequency are both recorded in the CSV. Targets that map to the same prime bin are skipped.

This means the sweep holds `f_sample` fixed and `num_samples` fixed, while the effective sweep variable is the coherent bin index `k`. The user supplies desired `f_out` targets; the CLI converts each one into the nearest coherent prime bin and uses that bin's actual tone.

Before the first measurement point, the command also programs the R&S siggen to `[dac].f_sample` so the external sample clock matches the sweep assumptions.

---

#### Sweep config files

Frequency lists live in `config/sweeps/` as individual TOML files. The active file is set by `[sweep] config` in `config/dacdemo.toml`:

```toml
# config/dacdemo.toml
[sweep]
config = "default"   # → loads config/sweeps/default.toml
```

```toml
# config/sweeps/default.toml
frequencies = [
    225280000.0,
    348160000.0,
    471040000.0,
]
```

Create as many sweep files as needed (`low_band.toml`, `nyquist_full.toml`, etc.) and switch between them with `--sweep-config`:

```
dacdemo sa-sfdr-sweep --sweep-config low_band
```

This updates `[sweep] config` in `dacdemo.toml` and runs immediately. Subsequent bare `dacdemo sa-sfdr-sweep` calls use whichever config was last set.

---

#### Specifying frequencies — three ways (evaluated in priority order)

*Option 1 — linear range on the command line:*
```
dacdemo sa-sfdr-sweep --freq-start 200e6 --freq-stop 500e6 --freq-step 50e6
```
Generates targets `[200, 250, 300, …, 500]` MHz. All three arguments are required together. Does not modify any sweep config file.

*Option 2 - arbitrary list on the command line:*
```
dacdemo sa-sfdr-sweep --freqs 200e6 266e6 400e6 471e6
```
Each target is clipped to Nyquist, then snapped to the nearest coherent in-band prime bin. Duplicates are dropped, meaning two requested frequencies that land on the same `k` produce one measurement point. The resulting actual frequencies are written to the currently active sweep config file (`config/sweeps/{config}.toml`) for reuse.

*Option 3 — active sweep config file:*
```
dacdemo sa-sfdr-sweep
dacdemo sa-sfdr-sweep --sweep-config low_band
```
When no frequency arguments are given, frequencies are read from the active sweep config file. Use `--sweep-config` to switch files.

---

#### Measurement modes

**Standard (default):** one wide-span sweep per frequency point. SA window is fixed at the full Nyquist band (center = `f_sample/4`, span = `f_sample/2`). Marker 1 reports the highest peak (fundamental); marker 2 steps to the next-lower peak (worst spur).

**Windowed (`--windowed`):** divides the Nyquist band into 4 equal sub-windows (each span = `f_sample/8`), runs one sweep per window, finds the highest peak in each, then computes SFDR from the two highest peaks across all four windows. Provides 4× better frequency resolution at the same RBW — useful when a tone is split across adjacent SA display bins in the wide-span view.

```
dacdemo sa-sfdr-sweep --windowed
dacdemo sa-sfdr-sweep --windowed --sa-settle 2.0
```

The `--sa-settle` delay is inserted between configuring each SA window and triggering the sweep, giving the trace time to stabilize after a window change. Distinct from `--settle` (DAC settling after a frequency hop).

**Spur classification (both modes).** After each SFDR reading, the CLI computes where the 2nd–5th harmonics of the measured fundamental would land (folded into the Nyquist band) and classifies the reported spur:

| `spur_class` | Meaning |
|---|---|
| `harmonic_N` | Spur is within tolerance of the Nth-folded harmonic of the fundamental (closest order wins) |
| `bin_split` | Spur is within tolerance of the fundamental — the calculation is corrupted by display-bin splitting, `sfdr_valid=False` |
| `other` | Real peak but not a predicted harmonic (IMD, clock leakage, noise ridge, etc.) |
| `unknown` | Spur is NaN (no second peak was found on the trace) |

Tolerance = `max(3 × sweep_span / 1001, 2 × rbw_hz, 1 coherent FFT bin)`. `sweep_span` is the actual swept span (full Nyquist in single mode, `f_sample/8` per window in windowed mode), so windowed runs have a much tighter (~1.5 MHz) tolerance than single mode (~6 MHz at `f_sample = 4.19 GHz`).

---

#### Output CSV

Both modes write a single unified schema to `data/captures/sa_sfdr_sweep.csv`. If the existing file's header does not match the current schema (e.g., after a code update that changes columns), the old file is auto-renamed to `sa_sfdr_sweep.legacy-YYYYMMDDTHHMMSS.csv` and a fresh header is written. A `-N` counter suffix is appended if the same-second name is taken.

| Column | Description |
|---|---|
| `timestamp` | ISO 8601 |
| `mode` | `single` or `windowed` |
| `tone_hz_target` | requested frequency (Hz) |
| `dac_clock_hz` | DAC `f_sample` used for harmonic-aliasing math |
| `center_hz`, `span_hz` | SA window center / span. In windowed mode this describes the full Nyquist band (`f_sample/4`, `f_sample/2`) — the actual sweep is 4 sub-windows of `window_span_hz` |
| `window_span_hz` | Width of each sub-window (windowed mode). `NaN` in single mode |
| `n_windows` | `1` (single) or `4` (windowed) |
| `rbw_hz`, `vbw_hz`, `ref_level_dbm` | SA configuration |
| `fund_freq_hz`, `fund_amp_dbm` | Fundamental peak used in SFDR calc |
| `spur_freq_hz`, `spur_amp_dbm` | Worst spur used in SFDR calc (`NaN` if no second peak) |
| `sfdr_dbc` | `fund_amp_dbm − spur_amp_dbm` |
| `spur_class` | `harmonic_N` / `bin_split` / `other` / `unknown` (see table above) |
| `sfdr_valid` | `False` iff `spur_class == bin_split` |
| `harmonic_tol_hz` | Tolerance used for classification |
| `expected_h2_hz` … `expected_h5_hz` | Predicted folded-harmonic locations for the measured fundamental |
| `peak_1_freq_hz`, `peak_1_amp_dbm` … `peak_4_freq_hz`, `peak_4_amp_dbm` | **Traceability.** In single mode: peak 1 = marker 1 (fund), peak 2 = marker 2 (spur), peaks 3–4 `NaN`. In windowed mode: peak N = window N's peak in window order (lowest center → highest), regardless of which ones won fund/spur after sorting |

---

#### Options

| Option | Default | Notes |
|---|---|---|
| `--freq-start/stop/step` | — | Linear range; all three required if used |
| `--freqs HZ [HZ ...]` | — | Arbitrary list; snapped to prime bins and saved to active sweep config |
| `--sweep-config NAME` | — | Switch active sweep config to `config/sweeps/NAME.toml` |
| `--windowed` | off | 4-window Nyquist measurement for higher resolution |
| `--center` | `f_sample / 4` | Override SA window center (standard mode only) |
| `--span` | `f_sample / 2` | Override SA window span (standard mode only) |
| `--rbw` | `100e3` | Resolution bandwidth (Hz) |
| `--vbw` | `10e3` | Video bandwidth (Hz) |
| `--ref` | `0.0` | SA reference level (dBm) |
| `--settle` | `0.5` | DAC settling time after reprogramming (s) |
| `--sa-settle` | `1.0` | SA settle delay between window configure and sweep trigger (s) |
| `--port` | config | Serial port override |
| `--baudrate` | config | Baudrate override |
| `--output` | `data/captures/sa_sfdr_sweep.csv` | Output CSV path |

---

### SNR frequency sweep - `sa-snr-sweep`

Iterates the DAC output tone across a set of target frequencies, reprograms the DAC at each step, measures SNR from the signal analyzer, and appends one row per step to a CSV.

Frequency selection and coherent-bin snapping behave exactly like `sa-sfdr-sweep`: use `--freq-start/stop/step`, `--freqs`, or the active sweep config file. Targets above Nyquist are clipped before coherent-bin selection.

Like `sa-sfdr-sweep`, this keeps `f_sample` fixed and `num_samples` fixed during the run, and sweeps by selecting different coherent prime bins `k` for the requested `f_out` values.
Before the first measurement point, it also programs the R&S siggen to `[dac].f_sample`.

```
dacdemo sa-snr-sweep
dacdemo sa-snr-sweep --sweep-config low_band
dacdemo sa-snr-sweep --freq-start 200e6 --freq-stop 500e6 --freq-step 50e6 --noise-bw 20e6
```

Per point, the analyzer:
1. Sweeps the configured span.
2. Takes the highest trace peak as the signal.
3. Probes left/right nearby noise windows.
4. Rejects windows that overlap the tone, expected harmonics, or obvious local spurs.
5. Computes `snr_db` using the requested `noise_bw_hz` and current `rbw_hz`.

Output CSV: `data/captures/sa_snr_sweep.csv`

| Column | Description |
|---|---|
| `timestamp` | ISO 8601 |
| `mode` | Currently always `single` |
| `tone_hz_target` | requested frequency (Hz) |
| `dac_clock_hz` | DAC `f_sample` used for harmonic exclusion |
| `center_hz`, `span_hz`, `rbw_hz`, `vbw_hz`, `ref_level_dbm` | SA configuration |
| `fund_freq_hz`, `fund_amp_dbm` | Fundamental peak used in the SNR calculation |
| `noise_freq_hz` | Representative noise-probe frequency (`NaN` on fallback modes) |
| `noise_left_freq_hz`, `noise_left_dbm` | Left-side probe result when available |
| `noise_right_freq_hz`, `noise_right_dbm` | Right-side probe result when available |
| `noise_level_dbm` | Noise level measured in RBW before bandwidth scaling |
| `noise_bandwidth_hz` | Integrated noise bandwidth used in the formula |
| `noise_exclusion_hz` | Guard band around the tone and harmonics |
| `noise_method` | `paired_probes`, `single_probe`, `masked_median_fallback`, or failure mode |
| `snr_db` | Final SNR result in dB |

| Option | Default | Notes |
|---|---|---|
| `--freq-start/stop/step` | - | Linear range; all three required if used |
| `--freqs HZ [HZ ...]` | - | Arbitrary list; snapped to prime bins and saved to active sweep config |
| `--sweep-config NAME` | - | Switch active sweep config to `config/sweeps/NAME.toml` |
| `--center` | `f_sample / 4` | SA window center |
| `--span` | `f_sample / 2` | SA window span |
| `--rbw` | `100e3` | Resolution bandwidth (Hz) |
| `--vbw` | `10e3` | Video bandwidth (Hz) |
| `--noise-bw` | `span` | Integrated noise bandwidth used in the SNR formula |
| `--ref` | `0.0` | SA reference level (dBm) |
| `--settle` | `0.5` | DAC settling time after reprogramming (s) |
| `--sa-settle` | `1.0` | SA settle delay between configure and sweep trigger (s) |
| `--port` | config | Serial port override |
| `--baudrate` | config | Baudrate override |
| `--output` | `data/captures/sa_snr_sweep.csv` | Output CSV path |

---

### Comprehensive frequency sweep - `sa-comprehensive-sweep`

Runs one wide-span SA sweep per tone and derives all of the following from that single trace:
- `SFDR`
- `SNR`
- `THD`
- `H2`
- `H3`

Harmonics are searched near the predicted aliased 2nd-5th harmonic locations, `SNR` comes from the nearby masked noise-floor estimate, and `THD` is calculated from the summed power of H2-H5.

Frequency selection uses the same rule as the other sweep commands:
- hold `f_sample` fixed
- hold `num_samples` fixed
- clip requested `f_out` to Nyquist
- snap to the nearest coherent in-band prime bin `k`
- generate `f_out_actual = k × f_sample / num_samples`

```
dacdemo sa-comprehensive-sweep
dacdemo sa-comprehensive-sweep --freqs 100e6 500e6 1e9 2e9 3e9 4e9
```

Output CSV: `data/captures/sa_comprehensive_sweep.csv`

Key columns:
- `tone_hz_target`, `tone_hz_clipped`, `tone_hz_actual`, `coherent_bin_k`
- `fund_freq_hz`, `fund_amp_dbm`
- `sfdr_dbc`, `spur_freq_hz`, `spur_amp_dbm`, `spur_class`
- `snr_db`, `noise_level_dbm`, `noise_bandwidth_hz`, `noise_method`
- `thd_dbc`
- `h2_freq_hz`, `h2_amp_dbm`, `h2_dbc`
- `h3_freq_hz`, `h3_amp_dbm`, `h3_dbc`
- `h4_freq_hz`, `h4_amp_dbm`
- `h5_freq_hz`, `h5_amp_dbm`

| Option | Default | Notes |
|---|---|---|
| `--freq-start/stop/step` | - | Linear range; all three required if used |
| `--freqs HZ [HZ ...]` | - | Arbitrary list; clipped to Nyquist, snapped to coherent bins, and saved to active sweep config |
| `--sweep-config NAME` | - | Switch active sweep config to `config/sweeps/NAME.toml` |
| `--center` | `f_sample / 4` | SA window center |
| `--span` | `f_sample / 2` | SA window span |
| `--rbw` | `100e3` | Resolution bandwidth (Hz) |
| `--vbw` | `10e3` | Video bandwidth (Hz) |
| `--noise-bw` | `span` | Integrated noise bandwidth used in the SNR formula |
| `--ref` | `0.0` | SA reference level (dBm) |
| `--settle` | `0.5` | DAC settling time after reprogramming (s) |
| `--sa-settle` | `1.0` | SA settle delay between configure and sweep trigger (s) |
| `--port` | config | Serial port override |
| `--baudrate` | config | Baudrate override |
| `--output` | `data/captures/sa_comprehensive_sweep.csv` | Output CSV path |
