# Quickstart

Activate the venv first: `.venv\Scripts\activate`

---

## First time

**`dacdemo detect-port`**
Scans USB, finds the Adafruit ItsyBitsy by VID, saves the COM port to `config/dacdemo.toml`. Re-run if you change USB ports.

**`dacdemo flash`**
Compiles and uploads the firmware. Uses port and board from config. Only needed on first setup or after firmware changes.

---

## Coherent tone setup (no hardware needed)

**`dacdemo calc`**
Reads `[coherent_tone]` from config, derives `f_sample` and `f_out`, writes them back into `[dac]`.
- `fs_app` → `f_sample = fs_app × 2^20`
- `x_seed` → nearest prime bins → `f_out = chosen_bin × f_sample / num_samples`
- `fin = "low"` or `"high"` selects which prime bin

Run this any time you change `fs_app`, `x_seed`, or `fin`. Everything downstream reads from `[dac]`.

```
dacdemo calc --x-seed 7         # change output frequency bin
dacdemo calc --from-fout 61e6   # back-calculate x_seed + fin from a desired f_out
```

**`dacdemo gen-sine`**
Generates the 256-sample 12-bit sine table from `f_out` and `f_sample`, saves to `data/generated_patterns/`. Skippable — `play-sine` and `run-demo` do this internally.

---

## Board commands

**`dacdemo health`**
Reads voltage, shunt voltage, current, and power from all five rails via INA219. Read-only — safe without chip in socket.

**`dacdemo bias`**
Sends `SET_VOLTAGE` with all rail targets from `[rails]` in config. Reads back each voltage to confirm.
```
dacdemo bias --initialize-compliance   # reset current limits first (recommended)
```

**`dacdemo play-sine`**
Sends `DAC_PLAY_SINE` over serial — firmware computes the sine table and enables the DAC pattern output. Uses `f_out` and `f_sample` from `[dac]`.

**`dacdemo run-demo`**
Runs the full sequence in one command: compliance init → bias rails → read back voltages → load and enable sine pattern.
```
dacdemo run-demo --initialize-compliance
```

---

## Instruments

**`dacdemo detect-instruments`**
Finds the R&S SMA100B signal generator, Keysight N9010B EXA signal analyzer, and Keysight oscilloscope via VISA, and writes their addresses directly to `config/dacdemo.toml`. Run once when setting up a new bench, or any time an instrument changes IP address.
```
dacdemo detect-instruments                    # VISA only
dacdemo detect-instruments --subnet 192.168.10  # also scan LAN
```

**`dacdemo set-siggen`**
Connects to the R&S SMA100B over LAN, sets CW mode, applies `f_sample` from `[dac]` as the DAC clock frequency, enables RF output.
```
dacdemo set-siggen --level -10   # override power (dBm)
dacdemo set-siggen --off         # turn RF off
```

**`dacdemo capture`**
Arms the AD3 logic analyzer (hardware trigger on `SPI_SCAN` rising edge), runs the DAC demo over serial, captures the full SPI transaction, decodes the 20-bit control word and 256×12-bit sine data, validates against expected pattern. Saves `capture_raw.csv` and `decoded_words.csv` to `data/captures/`.
```
dacdemo capture --no-validate    # skip comparison, just decode
```
Close the WaveForms GUI first — AD3 requires exclusive access.

**`dacdemo scope-measure`**
Connects to the Keysight MSOS054A over LAN, runs standard measurements on CH1 (frequency, Vpp, rise/fall time, duty cycle), appends a timestamped row to `data/captures/scope_measurements.csv`.
```
dacdemo scope-measure --channel 2 --screenshot
```

**`dacdemo sa-measure`**
Connects to the Keysight N9010B EXA Signal Analyzer over LAN, configures a spectrum view centered on `dac.f_out` (2 MHz span, 10 kHz RBW/VBW), runs one sweep, places a peak marker, and appends a timestamped row to `data/captures/sa_measurements.csv`.
```
dacdemo sa-measure --center 12.288e6 --span 5e6 --screenshot
```

**`dacdemo sa-sfdr`**
Single-tone SFDR measurement. SA window covers the full Nyquist band (center = `f_sample/4`, span = `f_sample/2`, RBW = 100 kHz). Places marker 1 on the fundamental and marker 2 on the worst spur. Appends to `data/captures/sa_sfdr.csv`.
```
dacdemo sa-sfdr
```

**`dacdemo sa-sfdr-sweep`**
Sweeps the DAC output tone across a set of frequencies and records SFDR at each step. Frequency lists live in separate files under `config/sweeps/` (e.g. `config/sweeps/default.toml`). The active sweep is selected by name in `config/dacdemo.toml` under `[sweep] config`.

```
# Linear range on the command line:
dacdemo sa-sfdr-sweep --freq-start 200e6 --freq-stop 500e6 --freq-step 50e6

# Explicit list — snaps to prime bins and saves actuals to the active sweep file:
dacdemo sa-sfdr-sweep --freqs 100e6 500e6 1e9 2e9

# Use a named sweep preset:
dacdemo sa-sfdr-sweep --sweep-config high_freq

# Windowed mode — 4 sub-windows across the Nyquist band (better resolution at low frequencies):
dacdemo sa-sfdr-sweep --windowed --sa-settle 1.5
```

Target frequencies snap to the nearest coherent prime bin. Duplicate bins are skipped. Output: `data/captures/sa_sfdr_sweep.csv` (12 columns including `tone_hz_target` and `sfdr_dbc`). Use `--windowed` when the fundamental tone falls below ~200 MHz and appears split across bins in wide-span mode. See `docs/command_reference.md` for full column list and options.

---

## Typical full sequence

```bash
dacdemo calc                              # derive f_sample + f_out
dacdemo set-siggen                        # push f_sample to R&S clock generator
dacdemo run-demo --initialize-compliance  # bias rails + load + enable DAC
dacdemo capture                           # capture + decode + validate SPI
dacdemo scope-measure                     # measure analog output on scope
dacdemo sa-sfdr-sweep                     # sweep SFDR across frequency range
```
