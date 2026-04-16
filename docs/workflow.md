# Workflow

## Normal use
1. Flash `firmware/Arduino_DAC_framework/Arduino_DAC_framework.ino` once with Arduino CLI.
2. Use the Python CLI from a terminal for bench work.
3. For repeatable demos, use `run-demo`.

## Why this structure
- The Arduino behaves like a persistent device controller. Flash it once and leave it.
- Python owns sequencing, repeatability, and future instrument automation.
- The original source files are preserved under `legacy/` for reference.

## Current end-to-end demo sequence
1. Open serial port
2. Initialize compliance
3. Bias rails
4. Read back rail voltages
5. Compute or choose sine parameters on host
6. Command the firmware to generate and load the sine pattern
7. Enable playback
8. Set signal generator to DAC sample clock frequency
9. Capture and validate SPI signals via AD3 logic analyzer
10. Measure analog output on oscilloscope
11. Measure RF spectrum on signal analyzer
