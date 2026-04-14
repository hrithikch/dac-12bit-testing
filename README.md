# DAC demo and experimentation framework

Bench control and signal generation for the DAC test board. One Arduino firmware handles rail biasing, power monitoring, and DAC pattern loading. A Python CLI drives everything over serial.

## Layout

```
config/                         TOML config (port, rail voltages, DAC params)
docs/                           Setup, workflow, and command reference
firmware/Arduino_DAC_framework/ Arduino firmware — flash once, leave in place
host/                           Python package (dacdemo) and entry point
legacy/                         Original sketches preserved for reference
lib/Ina219Rails/                Arduino library source — copy to your Arduino libraries folder
tools/                          Offline utilities (capture validation, etc.)
```

## Prerequisites

**Arduino side**
- Arduino CLI installed
- Adafruit SAMD core: `adafruit:samd`
- `Ina219Rails` library installed in your Arduino libraries folder (source in `lib/Ina219Rails/`)
- `Adafruit_DotStar` library installed

**Python side**
- Python 3.9+

## Setup

```bash
# Install Python package (run once from repo root)
pip install -e host/

# Detect board port and save to config
dacdemo detect-port
```

See `docs/setup_and_testing.md` for firmware flash instructions and step-by-step board bring-up.

## Normal workflow

```bash
# Flash firmware (one time, or after firmware changes)
dacdemo flash

# Set rail voltages from config
dacdemo bias --initialize-compliance

# Read rail health
dacdemo health

# Load and start sine output
dacdemo play-sine

# Full sequence in one command
dacdemo run-demo --initialize-compliance
```

All parameters default to `config/dacdemo.toml`. Pass `--port`, `--f-out`, etc. to override.

## Serial commands (firmware)

Rail and board control (preserved from original sketch):
`INITIALIZE_COMPLIANCE`, `SET_VOLTAGE`, `SET_COMPLIANCE`, `READ_ADC`, `READ_VOLTAGE`, `READ_SHUNTV`, `READ_CURRENT`, `READ_POWER`, `LDO_WRITE`, `DIO_ON`, `DIO_OFF`, `ON`, `OFF`

DAC pattern control (new in this framework):
`DAC_LOAD_SINE,f_out,f_sample`, `DAC_PLAY_SINE,f_out,f_sample`, `DAC_ENABLE_PATTERN`, `DAC_DISABLE_PATTERN`

## Next extension point

The natural next layer is instrument control under `host/dacdemo/instruments/` for signal generator setup, oscilloscope capture, and one-command automated demo runs.
