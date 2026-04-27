# Measurement Calculations And CSV Semantics

This document explains every CSV-producing measurement path in the DAC CLI framework:

- which command writes the CSV
- which fields come directly from an instrument
- which fields are computed on the host
- the exact formulas used
- sanity-check notes on whether the calculations look reasonable

Code references in this document point to the current implementation in `host/dacdemo/` and `instrument_comms/instruments/`.

## Conventions

- Frequency units are Hz unless a column name says otherwise.
- Power and amplitude values from the signal analyzer are in dBm.
- `dBc` values in this codebase are reported as a positive "distance below carrier":
  - `SFDR = fund_amp_dbm - spur_amp_dbm`
  - `H2_dBc = fund_amp_dbm - h2_amp_dbm`
  - `THD_dBc = fund_amp_dbm - harmonic_total_dbm`
- `NaN` means the metric could not be determined from the current trace or instrument response.
- Most CSV writers prepend a `timestamp` column at write time.

## CSV Inventory

| Command | Default CSV |
|---|---|
| `dacdemo capture` | `data/captures/capture_raw.csv`, `data/captures/decoded_words.csv` |
| `dacdemo scope-measure` | `data/captures/scope_measurements.csv` |
| `dacdemo sa-measure` | `data/captures/sa_measurements.csv` |
| `dacdemo sa-sfdr` | `data/captures/sa_sfdr.csv` |
| `dacdemo sa-snr` | `data/captures/sa_snr.csv` |
| `dacdemo sa-sfdr-sweep` | `data/captures/sa_sfdr_sweep.csv` |
| `dacdemo sa-snr-sweep` | `data/captures/sa_snr_sweep.csv` |
| `dacdemo sa-comprehensive-sweep` | `data/captures/sa_comprehensive_sweep.csv` |

## 1. Logic Capture CSVs

### `capture_raw.csv`

Written by `save_raw_csv(...)` in [host/dacdemo/ad3_capture.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/ad3_capture.py:149).

Columns:

- `sample_idx`: sequential capture sample index from the AD3 buffer.
- `raw_hex`: raw 16-bit digital word as hexadecimal.
- `CLK`, `SCAN`, `DIN_PAT`, `WR_PAT`, `EN_PAT`, `SDA`: individual bit extractions from the raw sample.

Formula:

```text
bit_value = (raw_sample >> bit_position) & 1
```

Assessment:

- This is a direct decode of digital samples and is straightforward.
- There is no derived RF math here.

### `decoded_words.csv`

Written by `save_decoded_csv(...)` in [host/dacdemo/ad3_capture.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/ad3_capture.py:167).

Columns:

- `word_idx`: 0-based DAC sample index.
- `decoded`: value reconstructed from captured serial bits.
- `expected`: value from the software-generated reference sine.
- `match`: boolean equality check.

Expected waveform formula from `expected_sine(...)` in [host/dacdemo/ad3_capture.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/ad3_capture.py:246):

```text
M = (f_out * DAC_NUM_SAMPLES) / f_sample
expected[k] = round(2047.5 * sin(2*pi * M * k / DAC_NUM_SAMPLES) + 2047.5)
```

Assessment:

- This matches the sine-table generation used elsewhere in the project.
- The validation is exact sample-by-sample equality, which is appropriate for digital pattern verification.

## 2. Scope Measurement CSV

### `scope_measurements.csv`

Written by `ScopeSession.measure(...)` and `save_measurements_csv(...)` in [host/dacdemo/scope_control.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/scope_control.py:84).

Columns:

- `channel`
- `frequency_hz`
- `vpp_v`
- `rise_time_s`
- `fall_time_s`
- `duty_cycle_pct`

Source:

- All of these are queried directly from the Keysight scope:
  - `:MEASure:FREQuency?`
  - `:MEASure:VPP?`
  - `:MEASure:RISetime?`
  - `:MEASure:FALLtime?`
  - `:MEASure:DUTYcycle?`

Special handling:

- The scope sentinel `9.9E+37` is treated as "measurement unavailable" and converted to `None`.

Assessment:

- This path is instrument-native, not host-derived.
- The host is only packaging the returned values into CSV.

## 3. Signal Analyzer Peak CSV

### `sa_measurements.csv`

Written by `SASession.measure(...)` in [host/dacdemo/siganalyzer_control.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/siganalyzer_control.py:160).

Columns:

- `center_hz`
- `span_hz`
- `rbw_hz`
- `vbw_hz`
- `ref_level_dbm`
- `peak_freq_hz`
- `peak_amp_dbm`

Source:

- The analyzer is configured with the requested center/span/RBW/VBW/reference level.
- Marker 1 is moved to the highest peak in the trace.
- `peak_freq_hz` and `peak_amp_dbm` are then read from marker 1.

Assessment:

- This is a clean one-shot "highest peak in span" measurement.
- No additional host math is involved.

## 4. One-Shot SFDR CSV

### `sa_sfdr.csv`

Written by `SASession.measure_sfdr(...)` in [host/dacdemo/siganalyzer_control.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/siganalyzer_control.py:195) using the analyzer driver's `measure_sfdr()` in [instrument_comms/instruments/keysight_exa.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/instrument_comms/instruments/keysight_exa.py:84).

Columns:

- `mode`
- `center_hz`
- `span_hz`
- `window_span_hz`
- `n_windows`
- `rbw_hz`
- `vbw_hz`
- `ref_level_dbm`
- `fund_freq_hz`
- `fund_amp_dbm`
- `spur_freq_hz`
- `spur_amp_dbm`
- `sfdr_dbc`
- `peak_1_*` through `peak_4_*`

Computation:

1. Marker 1 is moved to the highest peak.
2. Marker 2 is moved to the next lower peak.
3. SFDR is computed as:

```text
sfdr_dbc = fund_amp_dbm - spur_amp_dbm
```

If the analyzer reports no second peak, `spur_*` and `sfdr_dbc` are `NaN`.

Assessment:

- The SFDR definition used here is standard for a marker-based measurement.
- This path does not attempt to determine whether the spur is harmonic, bin-split, or something else; that richer classification is added only in the sweep flows.

## 5. One-Shot SNR CSV

### `sa_snr.csv`

Written by `SASession.measure_snr(...)` in [host/dacdemo/siganalyzer_control.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/siganalyzer_control.py:249), with the actual math in [host/dacdemo/snr_analysis.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/snr_analysis.py:79).

Columns:

- `mode`
- `center_hz`
- `span_hz`
- `rbw_hz`
- `vbw_hz`
- `ref_level_dbm`
- `fund_freq_hz`
- `fund_amp_dbm`
- `noise_freq_hz`
- `noise_left_freq_hz`
- `noise_left_dbm`
- `noise_right_freq_hz`
- `noise_right_dbm`
- `noise_level_dbm`
- `noise_bandwidth_hz`
- `noise_exclusion_hz`
- `noise_method`
- `snr_db`

### Fundamental selection

- The fundamental is taken as the highest peak in the current span:

```text
(fund_freq_hz, fund_amp_dbm) = measure_peak()
```

### Trace frequency axis

The frequency axis for the downloaded trace is reconstructed as:

```text
start_hz = center_hz - span_hz / 2
step_hz = span_hz / (n_points - 1)
freqs[i] = start_hz + i * step_hz
```

### Exclusion region

Bins near the fundamental and the aliased 2nd-5th harmonics are masked out. The exclusion width is:

```text
bin_width_hz = span_hz / (n_points - 1)
noise_exclusion_hz = max(3 * bin_width_hz, 2 * rbw_hz)
```

Expected aliased harmonic locations come from:

```text
alias_to_nyquist(f, fs) = min(f mod fs, fs - (f mod fs))
```

### Noise window search

The code probes symmetric left/right windows around the tone. A candidate window is accepted only if:

- it does not overlap any blocked region
- it has at least 3 finite bins
- its local "spuriness" is not too high

Window statistics:

```text
noise_dbm = median(window_bins_dbm)
spuriness_db = max(window_bins_dbm) - median(window_bins_dbm)
```

Preferred result:

- use a left/right pair if both are valid
- both have `spuriness_db <= 6 dB`
- their median noise estimates agree within `6 dB`

Then:

```text
noise_level_dbm = (noise_left_dbm + noise_right_dbm) / 2
noise_method = "paired_probes"
```

Fallbacks:

- best single-side probe: `noise_method = "single_probe"`
- median of all unblocked trace bins: `noise_method = "masked_median_fallback"`
- otherwise `snr_db = NaN`

### SNR formula

First scale RBW-limited noise to the requested integrated bandwidth:

```text
integrated_noise_dbm = noise_level_dbm + 10 * log10(noise_bw_hz / rbw_hz)
```

Then:

```text
snr_db = fund_amp_dbm - integrated_noise_dbm
```

Assessment:

- The bandwidth-scaling formula is standard.
- Masking the fundamental and aliased harmonics is sensible.
- The overall method is heuristic, not metrology-grade:
  - it uses local median-in-dBm windows rather than averaging power in linear units
  - it depends on trace shape, span, and spur rejection thresholds
  - it estimates noise from selected regions, not by integrating the full spectrum

This is reasonable for comparative sweeps, but it should be treated as an engineering estimate rather than a standards-style SNR measurement.

## 6. SFDR Sweep CSV

### `sa_sfdr_sweep.csv`

Written by `cmd_sa_sfdr_sweep(...)` in [host/dacdemo/cli.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/cli.py:925), with the base SA data coming from `measure_sfdr(...)` or `measure_sfdr_windowed(...)`.

Additional columns beyond the one-shot SFDR file:

- `tone_hz_target`
- `dac_clock_hz`
- `spur_class`
- `sfdr_valid`
- `harmonic_tol_hz`
- `expected_h2_hz` through `expected_h5_hz`

### Requested tone handling

The sweep resolves requested frequencies into coherent in-band tones before measurement:

- fully out-of-range frequencies are skipped
- Nyquist-edge requests may be clipped
- surviving requests are snapped to a coherent in-band prime bin

The actual measured DAC tone is:

```text
tone_hz_actual = coherent_bin_k * dac_clock_hz / num_samples
```

### Standard mode

- One full-span sweep is taken over the Nyquist band.
- Fundamental and spur come from the analyzer marker routine.

### Windowed mode

Implemented in `measure_sfdr_windowed(...)` in [host/dacdemo/siganalyzer_control.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/siganalyzer_control.py:345).

- The Nyquist band is divided into 4 windows.
- One peak is measured per window.
- The two highest-amplitude window peaks are treated as fundamental and spur.

Formula:

```text
window_span_hz = dac_clock_hz / 8
sfdr_dbc = fund_amp_dbm - spur_amp_dbm
```

### Spur classification

After SFDR is measured, the host classifies the spur in [host/dacdemo/sfdr_analysis.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/sfdr_analysis.py:25).

Tolerance:

```text
harmonic_tol_hz = max(3 * sweep_span / 1001, 2 * rbw_hz, dac_clock_hz / num_samples)
```

Classification rules:

- `bin_split` if `abs(spur_hz - fund_hz) < harmonic_tol_hz`
- else `harmonic_N` if the spur is near the aliased `N`th harmonic
- else `other`
- else `unknown` if the spur is not finite

Validity flag:

```text
sfdr_valid = (spur_class != "bin_split")
```

Assessment:

- The marker-based SFDR calculation itself is fine.
- The added classification is useful and the tolerance logic is reasonable.
- Windowed mode improves frequency discrimination, but it does assume the dominant peak in each sub-window is the only relevant candidate from that window.

## 7. SNR Sweep CSV

### `sa_snr_sweep.csv`

Written by `cmd_sa_snr_sweep(...)` in [host/dacdemo/cli.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/cli.py:1060).

Columns:

- `tone_hz_target`
- `dac_clock_hz`
- all one-shot SNR columns

Computation:

- For each resolved coherent tone, the board is reprogrammed.
- A single SA trace is captured.
- The same `estimate_snr_from_trace(...)` logic described above is used.

Assessment:

- This is consistent with the one-shot SNR path.
- It is appropriate for relative SNR-vs-frequency sweeps.

## 8. Comprehensive Sweep CSV

### `sa_comprehensive_sweep.csv`

Written by `cmd_sa_comprehensive_sweep(...)` in [host/dacdemo/cli.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/cli.py:1167), with the core calculations in [host/dacdemo/comprehensive_analysis.py](/C:/Users/nuc-user/OneDrive%20-%20Alphacore,%20Inc/Documents/Program_projects/Testing/DAC_12/dac_cli_framework_v2/host/dacdemo/comprehensive_analysis.py:60).

This is the richest CSV. It includes:

- target and actual tone bookkeeping
- SFDR and spur classification
- predicted and measured harmonic locations
- H2/H3/H4/H5 amplitudes
- THD
- SNR and noise-estimation metadata

### Harmonic prediction

Expected harmonic locations are computed by folding `n * fundamental` into Nyquist:

```text
expected_harmonic_n_hz = alias_to_nyquist(n * fund_freq_hz, dac_clock_hz)
```

### Harmonic search

For each expected harmonic, the trace peak nearest that expected location is selected within:

```text
harmonic_tol_hz = max(3 * bin_width_hz, 2 * rbw_hz, dac_clock_hz / num_samples)
```

Per-harmonic dBc:

```text
hN_dbc = fund_amp_dbm - hN_amp_dbm
```

### Spur and SFDR

The worst spur is found by scanning the full trace while excluding:

- frequencies within `exclusion_hz` of the fundamental
- frequencies near DC within `dc_guard_hz`

where:

```text
bin_width_hz = span_hz / (n_points - 1)
exclusion_hz = max(3 * bin_width_hz, 2 * rbw_hz)
dc_guard_hz = exclusion_hz
sfdr_dbc = fund_amp_dbm - spur_amp_dbm
```

Spur classification uses the same logic as the SFDR sweep.

### THD

The code converts harmonic amplitudes to linear power, sums them, converts back to dBm, then reports the distance below the carrier:

```text
harmonic_power_mw = sum(10^(hN_amp_dbm / 10)) for N = 2..5
harmonic_total_dbm = 10 * log10(harmonic_power_mw)
thd_dbc = fund_amp_dbm - harmonic_total_dbm
```

Interpretation:

- Larger positive `thd_dbc` means lower harmonic distortion.
- If you prefer the more traditional signed-ratio form, it would be:

```text
THD_dBc_signed = harmonic_total_dbm - fund_amp_dbm = -thd_dbc
```

### SNR

SNR is reused directly from `estimate_snr_from_trace(...)`, so the same caveats apply as in the one-shot and sweep SNR paths.

Assessment:

- The harmonic search and THD summation make sense for a practical swept-trace workflow.
- Reporting `THD` as positive dBc-down is internally consistent with `SFDR`, `H2_dBc`, and `H3_dBc`.
- The harmonic search tolerance is intentionally fairly wide to survive coarse SA trace resolution.

## 9. CSV Writer Behavior

### Generic scope CSV writer

`host/dacdemo/scope_control.py` writes:

```text
fieldnames = ["timestamp"] + row.keys()
```

This means the schema is whatever the current row shape is.

### Generic signal analyzer CSV writer

`host/dacdemo/siganalyzer_control.py` supports both inferred and pinned schemas.

When fieldnames are pinned:

- the existing header is checked
- if the schema changed, the old file is archived as `*.legacy-<timestamp>.csv`
- only known columns are written

Assessment:

- This is a good guard against silent CSV corruption after schema changes.

## Verification Summary

### Calculations that look solid

- Marker-based peak and SFDR extraction.
- Noise bandwidth scaling: `noise + 10*log10(BW/RBW)`.
- Harmonic alias prediction into Nyquist.
- Linear-power summation for THD.
- Coherent-tone bookkeeping columns in the sweep CSVs.

### Calculations that are reasonable but heuristic

- SNR estimation from selected trace windows.
- Spur classification tolerance using SA span, RBW, and coherent-bin width.
- Windowed SFDR using one dominant peak per sub-window.

### Things to remember when interpreting the CSVs

- `SNR` here is a trace-based estimate, not a standards-lab integrated-noise measurement.
- `THD`, `H2_dBc`, `H3_dBc`, and `SFDR` are reported as positive "dB down from carrier".
- Sweep results depend strongly on SA span, RBW, trace point density, and harmonic masking assumptions.
