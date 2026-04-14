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

## 2. No-hardware checks (run any time)

```
dacdemo list-ports
```
Lists all serial ports visible to the OS. Confirm your board's port appears.

```
dacdemo calc
```
Computes coherent tone frequencies from `config/dacdemo.toml` `[coherent_tone]` settings.
Saves result to `data/coherent_tone_plan.json`. No hardware needed.

```
dacdemo gen-sine
```
Generates the sine code table from `[dac]` settings.
Saves to `data/generated_patterns/sine_codes.json`. No hardware needed.

---

## 3. Board connected — serial link test (no chip required)

```
dacdemo detect-port
```
Run again to confirm port is correct after connecting.

```python
python -c "from dacdemo.board_control import BoardSession; s=BoardSession.open('COM5'); print(s.led_on()); print(s.led_off()); s.close()"
```
Toggles the onboard LED on and off. Confirms serial link is alive and firmware is responding.
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
Generate the pattern first (or skip if already done).

```python
python -c "from dacdemo.board_control import BoardSession; s=BoardSession.open('COM5'); print(s.dac_load_sine(266.24e6, 5.24288e9)); s.close()"
```
Sends f_out and f_sample to firmware, which computes and loads the sine pattern into the DAC buffer.

```python
python -c "from dacdemo.board_control import BoardSession; s=BoardSession.open('COM5'); print(s.dac_enable_pattern()); s.close()"
```
Enables DAC pattern playback. Check the output signal on the Analog Discovery.

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
