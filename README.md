# DAC demo and experimentation framework

Bench control and signal generation for the DAC test board. One Arduino firmware handles rail biasing, power monitoring, and DAC pattern loading. A Python CLI drives everything over serial and controls bench instruments over LAN.

## Layout

```
config/                         TOML config (port, rail voltages, DAC params, instrument addresses)
docs/                           quickstart.md, command_reference.md, setup_and_testing.md
firmware/Arduino_DAC_framework/ Arduino firmware — flash once, leave in place
host/                           Python package (dacdemo) and entry point
instrument_comms/               Reusable instrument drivers (R&S siggen, Keysight scope, AD2, supplies)
legacy/                         Original sketches preserved for reference
lib/Ina219Rails/                Arduino library source — copy to your Arduino libraries folder
tools/                          Standalone utilities (capture_validate.py)
```

## Prerequisites

**Arduino side**
- Arduino CLI
- Adafruit SAMD core: `adafruit:samd`
- `Ina219Rails` library in your Arduino libraries folder (source in `lib/Ina219Rails/`)
- `Adafruit_DotStar` library

**Python side**
- Python 3.9+
- `pyvisa` — for LAN instrument control (signal generator, scope)
- NI-VISA backend — required on Windows for pyvisa LAN instruments (download from ni.com/visa)
- Digilent WaveForms — required for AD3 digital capture (installs `dwf.dll`)

## Setup

```bash
# Install Python package (run once from repo root)
pip install -e host/

# Detect board port and save to config
dacdemo detect-port
```

Update instrument IP addresses in `config/dacdemo.toml` `[instruments]` before using `set-siggen`, `scope-measure`, or `sa-measure`.

See `docs/setup_and_testing.md` for firmware flash instructions and step-by-step bring-up.

## Normal workflow

```bash
# Compute coherent tone plan — derives f_sample and f_out, writes them to [dac] in config
dacdemo calc

# Push sample clock frequency to R&S SMA100B signal generator over LAN
dacdemo set-siggen

# Bias rails and enable DAC sine output
dacdemo run-demo --initialize-compliance

# Capture and decode SPI signals from ItsyBitsy via AD3 logic analyzer
dacdemo capture

# Measure DAC analog output via Keysight MSOS054A scope
dacdemo scope-measure

# Measure DAC RF output via Keysight N9010B EXA Signal Analyzer
dacdemo sa-measure
```

See `docs/quickstart.md` for the full command sequence with short explanations.

## Coherent tone config

`[coherent_tone]` in `config/dacdemo.toml` is the source of truth for frequency planning.
`[dac] f_sample` and `[dac] f_out` are always derived — run `dacdemo calc` after any change.

| Key | Role |
|---|---|
| `fs_app` | Sets sample clock: `f_sample = fs_app × 2^20` |
| `x_seed` | Prime bin search seed → selects output frequency |
| `fin` | `"low"` or `"high"` — which prime bin becomes `f_out` |

```bash
dacdemo calc --from-fout 61.44e6   # back-calculate x_seed + fin from a desired f_out
```

## Serial commands (firmware)

Rail and board control:
`INITIALIZE_COMPLIANCE`, `SET_VOLTAGE`, `SET_COMPLIANCE`, `READ_ADC`, `READ_VOLTAGE`, `READ_SHUNTV`, `READ_CURRENT`, `READ_POWER`, `LDO_WRITE`, `DIO_ON`, `DIO_OFF`, `ON`, `OFF`

DAC pattern control:
`DAC_LOAD_SINE,f_out,f_sample`, `DAC_PLAY_SINE,f_out,f_sample`, `DAC_ENABLE_PATTERN`, `DAC_DISABLE_PATTERN`
