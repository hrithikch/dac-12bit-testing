# Setup and testing

## 1. Arduino library dependency

The firmware depends on `Ina219Rails`. The library source is included in this repo at `lib/Ina219Rails/`.
Copy that folder into your Arduino libraries directory before compiling:

- Windows: `Documents\Arduino\libraries\Ina219Rails\`
- Mac/Linux: `~/Arduino/libraries/Ina219Rails/`

You also need `Adafruit_DotStar`, available through the Arduino IDE library manager or arduino-cli:

```
arduino-cli lib install "Adafruit DotStar"
```

## 2. Flash the firmware

```bash
# Install Adafruit SAMD core (one time)
arduino-cli config add board_manager.additional_urls https://adafruit.github.io/arduino-board-index/package_adafruit_index.json
arduino-cli core update-index
arduino-cli core install adafruit:samd

# Confirm your board and port
arduino-cli board list

# Compile and upload
arduino-cli compile --fqbn adafruit:samd:adafruit_itsybitsy_m0 firmware/Arduino_DAC_framework
arduino-cli upload  --fqbn adafruit:samd:adafruit_itsybitsy_m0 --port COM3 firmware/Arduino_DAC_framework
```

Replace `COM3` with the port shown by `arduino-cli board list`. Or use `dacdemo flash` after configuring `config/dacdemo.toml`.

## 3. Install the Python package

```bash
# From repo root
pip install -e host/
```

## 4. Detect and save the board port

```bash
dacdemo detect-port
```

Finds the Adafruit board by USB VID and writes the port to `config/dacdemo.toml`. Re-run any time you change USB ports.

## 5. Test incrementally (safest order)

**No board needed — verify Python install:**
```bash
dacdemo list-ports
dacdemo calc
dacdemo gen-sine
```

**Board connected — simplest round-trip (confirms serial link and firmware):**
```python
python -c "from dacdemo.board_control import BoardSession; s=BoardSession.open('COM5'); print(s.led_on()); print(s.led_off()); s.close()"
```

**Read-only rail check (no chip in socket required):**
```bash
dacdemo health
```

**Set rail voltages:**
```bash
dacdemo bias --initialize-compliance
```

**Load sine pattern without enabling output:**
```python
python -c "from dacdemo.board_control import BoardSession; s=BoardSession.open('COM5'); print(s.dac_load_sine(266.24e6, 5.24288e9)); s.close()"
```

**Enable pattern output:**
```python
python -c "from dacdemo.board_control import BoardSession; s=BoardSession.open('COM5'); print(s.dac_enable_pattern()); s.close()"
```

**Or load and enable in one command:**
```bash
dacdemo play-sine
```

**Full demo sequence:**
```bash
dacdemo run-demo --initialize-compliance
```

The ordering matters: LED first (simplest), then rail reads (read-only), then bias (writes voltages), then DAC load, then enable. Each step validates one more layer.
