# Pin map decisions

## Persistent framework decision
The DAC pin map from `sine_din_h.ino` is treated as authoritative.

### DAC signals
- `SPI_DOUT = 10`
- `DIN_PAT = 9`
- `SPI_SCK_PAT = 1`
- `SPI_SCAN = 12`
- `EN_PAT = 7`
- `WR_PAT = 13`
- `SPI_CP = 11`
- `SEL_EXT_DIN = 5`

## Rail-control chip selects retained from Arduino_DAC_control_sketch.ino
- `CS1 = 15`
- `CS2 = 16`
- `CS3 = 17`
- `CS4 = 18`
- `CS5 = 19`

## User clarification applied
The pins in `Arduino_DAC_control_sketch.ino` that overlap the DAC control path were setup defaults only and were not the real operating map for DAC playback. The `sine_din_h.ino` assignments overwrite that earlier map during actual use, so the unified framework keeps the `sine_din_h.ino` DAC mapping.
