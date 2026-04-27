# DAC demo and experimentation framework

Bench control and signal generation for the DAC test board. One Arduino firmware handles rail biasing, power monitoring, and DAC pattern loading. A Python CLI drives everything over serial and controls bench instruments over LAN.

## Layout

```
config/                         TOML config (port, rail voltages, DAC params, instrument addresses)
docs/                           quickstart.md, command_reference.md, measurement_calculations.md, sa_scpi_validated.md
firmware/Arduino_DAC_framework/ Arduino firmware — flash once, leave in place
host/                           Python package (dacdemo) and entry point
instrument_comms/               Reusable instrument drivers (R&S siggen, Keysight scope, AD3, supplies)
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

## Documentation

- [`docs/quickstart.md`](docs/quickstart.md) — first-time setup, typical workflow, every CLI command with examples
- [`docs/command_reference.md`](docs/command_reference.md) — complete flag listings, config ownership table, legacy migration guide
- [`docs/measurement_calculations.md`](docs/measurement_calculations.md) — CSV schemas, formulas, and measurement methodology for all SA and scope paths
- [`docs/sa_scpi_validated.md`](docs/sa_scpi_validated.md) — validated SCPI command sequences for the Keysight N9010B

## Setup

```bash
pip install -e host/         # install Python package (once, from repo root)
.venv\Scripts\activate       # activate venv
dacdemo detect-port          # find board USB port, save to config
```

See `docs/quickstart.md` for the full bring-up sequence, including firmware flash, instrument detection, and the first sweep.

## Config files

`config/dacdemo.toml` is the main config file. Edit it before running commands:

| Section | Purpose |
|---|---|
| `[hardware]` | COM port (written by `detect-port`) and baud rate |
| `[dac]` | `f_out` and `f_sample` — always written by `dacdemo calc`; do not edit by hand |
| `[rails]` | Target rail voltages for `bias` / `run-demo` |
| `[coherent_tone]` | Frequency planning inputs — edit `fs_app`, `x_seed`, or `fin`, then run `dacdemo calc` |
| `[instruments]` | VISA addresses — run `dacdemo detect-instruments` to auto-fill, or set manually |
| `[psu]` | Bench PSU channel, voltage, and current limit |
| `[sweep]` | Active sweep file: `config = "default"` → `config/sweeps/default.toml` |

Sweep frequency lists live under `config/sweeps/`. Each file is a TOML with a `frequencies` array (Hz). Create named files for different test plans and switch between them by changing `[sweep] config` in `dacdemo.toml`.

## Serial commands (firmware)

Rail and board control:
`INITIALIZE_COMPLIANCE`, `SET_VOLTAGE`, `SET_COMPLIANCE`, `READ_ADC`, `READ_VOLTAGE`, `READ_SHUNTV`, `READ_CURRENT`, `READ_POWER`, `LDO_WRITE`, `DIO_ON`, `DIO_OFF`, `ON`, `OFF`

DAC pattern control:
`DAC_LOAD_SINE,f_out,f_sample`, `DAC_PLAY_SINE,f_out,f_sample`, `DAC_ENABLE_PATTERN`, `DAC_DISABLE_PATTERN`
