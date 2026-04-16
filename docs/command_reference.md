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

**Override fs_app on the command line (does not write to TOML):**
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
Override `f_sample` directly. Updates `f_sample` in `[dac]` config and prints the coherent `f_out` options for the new frequency. **Note:** this bypasses the `[coherent_tone]` derivation — run `dacdemo calc` afterwards to bring the full plan back into sync.

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
