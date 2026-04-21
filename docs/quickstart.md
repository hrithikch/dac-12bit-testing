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

In this coherent-tone workflow, `num_samples` is fixed and `f_sample` is chosen first. That means each requested output tone is realized by choosing a coherent prime bin `k`, with `f_out = k × f_sample / num_samples`.

Run this any time you change `fs_app`, `x_seed`, or `fin`. Everything downstream reads from `[dac]`.

```
dacdemo calc --x-seed 7         # change output frequency bin
dacdemo calc --from-fout 61e6   # back-calculate x_seed + fin from a desired f_out
dacdemo calc --fs-app 5000      # write fs_app, recompute f_sample + f_out in config
```

**`dacdemo gen-sine`**
Generates the 256-sample 12-bit sine table from `f_out` and `f_sample`, saves to `data/generated_patterns/`. Skippable — `play-sine` and `run-demo` do this internally.

---

## Board commands

**`dacdemo health`**
Reads voltage, shunt voltage, current, and power from all five rails via INA219. Read-only — safe without chip in socket.

**`dacdemo prep`** — one-shot pre-connect wrapper: `detect-port` → `calc` → `flash` → `bias`. Runs before the DUT socket is attached.
```bash
dacdemo prep --initialize-compliance
```

**`dacdemo legacy`** — runs the original two-sketch workflow end-to-end: detect → flash `legacy/sketch/Arduino_DAC_control_sketch/` → bias → pause for socket connection → flash `legacy/sketch/sine_din_h/`. Use `--no-prompt` to skip the pause.

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

**`dacdemo sa-snr`**
Single-tone SNR measurement. Runs one SA sweep, finds the fundamental as the highest peak, then estimates nearby noise from left/right trace windows that avoid the tone and expected harmonics. SNR is calculated as `fund_amp_dbm - (noise_level_dbm + 10*log10(noise_bw_hz / rbw_hz))`. By default `noise_bw_hz = span`.
```
dacdemo sa-snr
dacdemo sa-snr --noise-bw 10e6
```

**`dacdemo sa-sfdr-sweep`**
Sweeps the DAC output tone across a set of frequencies and records SFDR at each step. Frequency lists live in separate files under `config/sweeps/` (e.g. `config/sweeps/default.toml`). The active sweep is selected by name in `config/dacdemo.toml` under `[sweep] config`.

Mental model: for a given sweep run, `f_sample` and `num_samples` stay fixed. Each requested `f_out` is snapped to the nearest coherent prime bin `k`, then the actual generated tone is `k × f_sample / num_samples`.

At sweep start, the CLI also programs the R&S siggen to the current `f_sample` from `[dac]`, so the clock source is aligned with the DAC settings for the whole run.

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

Target frequencies are first clipped to Nyquist (`f_sample / 2`), then snapped to the nearest coherent in-band prime bin. In other words, the sweep variable is the bin index `k` while `f_sample` and `num_samples` remain fixed. Duplicate bins are skipped. Output: `data/captures/sa_sfdr_sweep.csv` - 30-column unified schema shared by both modes, including `sfdr_dbc`, `spur_class` (`harmonic_N` / `bin_split` / `other`), `sfdr_valid`, expected-harmonic frequencies, and per-marker / per-window peak traceability. If the file's header doesn't match the current schema (e.g., after a code update) it is auto-archived as `sa_sfdr_sweep.legacy-<timestamp>.csv` before writing. Use `--windowed` when the fundamental is split across SA display bins in wide-span mode. See `docs/command_reference.md` for the full column list and options.

**`dacdemo sa-snr-sweep`**
Sweeps the DAC output tone across frequencies and records SNR at each step using the same coherent-bin sweep machinery as `sa-sfdr-sweep`. Output: `data/captures/sa_snr_sweep.csv`.

It uses the same fixed-`f_sample`, fixed-`num_samples`, sweep-`k` model as `sa-sfdr-sweep`: requested `f_out` values are snapped to coherent prime bins and the actual generated tone is `k × f_sample / num_samples`.
It also programs the R&S siggen to `[dac].f_sample` before the sweep starts.
```
dacdemo sa-snr-sweep
dacdemo sa-snr-sweep --freq-start 200e6 --freq-stop 500e6 --freq-step 50e6 --noise-bw 20e6
```

**`dacdemo sa-comprehensive-sweep`**
Sweeps the DAC output tone across frequencies and records `SFDR`, `SNR`, `THD`, `H2`, and `H3` from one SA trace per point. It uses the same Nyquist-clipped, coherent-bin sweep logic as the other SA sweep commands and writes `data/captures/sa_comprehensive_sweep.csv`.
```
dacdemo sa-comprehensive-sweep --freqs 100e6 500e6 1e9 2e9 3e9 4e9
```

---

## Typical full sequence

```bash
# 1. edit config/dacdemo.toml or config/sweeps/<name>.toml
# 2. choose the sample clock
dacdemo calc --fs-app 5000                # example: writes fs_app, f_sample, and f_out to config

# 3. prep the bench
dacdemo prep --initialize-compliance      # detect port + calc + flash + bias

# 4. run a sweep
dacdemo sa-comprehensive-sweep --freqs 100e6 500e6 1e9 2e9 3e9 4e9
```
