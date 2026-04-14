# Pin map analysis

## Physical pin assignments across all three sketches

| Physical pin | Phase 1 name | dir | Phase 3 name | dir | Unified name | dir |
|---|---|---|---|---|---|---|
| 1 | `DIN_PAT` | OUT | `SPI_SCK_PAT` | OUT | `SPI_SCK_PAT` | OUT |
| 5 | `SPI_SCAN` | OUT | `SEL_EXT_DIN` | OUT | `SEL_EXT_DIN` | OUT |
| 7 | `EN_PAT` | OUT | `EN_PAT` | OUT | `EN_PAT` | OUT |
| 9 | `CLK_PAT` | OUT | `DIN_PAT` | OUT | `DIN_PAT` | OUT |
| **10** | **`SPI_CP`** | **OUT** | **`SPI_DOUT`** | **IN_PULLDOWN** | **`SPI_DOUT`** | **IN_PULLDOWN** |
| 11 | `SEL_EXT_DIN` | OUT | `SPI_CP` | OUT | `SPI_CP` | OUT |
| 12 | `WR_PAT` | OUT | `SPI_SCAN` | OUT | `SPI_SCAN` | OUT |
| 13 | `SPI_DOUT` | OUT | `WR_PAT` | OUT | `WR_PAT` | OUT |
| 15–19 | CS1–CS5 | OUT | *(not set)* | — | CS1–CS5 | OUT |

Phase 1 = `Arduino_DAC_control_sketch.ino`, Phase 3 = `sine_din_h.ino`, Unified = `firmware/Arduino_DAC_framework/Arduino_DAC_framework.ino`.

## Signal name remapping

The two legacy sketches used the same 8 physical pins but assigned entirely different signal names to most of them. The unified firmware adopted Phase 3's mapping as authoritative. Phase 3 was the sketch actually performing DAC pattern operations, so its mapping reflects real hardware connections.

## Pin 10 direction conflict

Pin 10 is the only pin with a direction difference across sketches. Phase 1 declared it `SPI_CP` (OUTPUT), Phase 3 and the unified firmware declare it `SPI_DOUT` (INPUT_PULLDOWN). Phase 1 set it LOW at startup and never drove it during any serial command, so the idle state is safe and there is no damage risk from the unified firmware's use of INPUT_PULLDOWN.

## CS pins do not overlap DAC pins

The rail-control chip selects (CS1–CS5, pins 15–19) have no physical overlap with the DAC signal pins (1, 5, 7, 9–13). The "overlap not verified" concern from the backlog is resolved — there is no conflicting overlap.

## setup() behavior vs legacy

Each legacy sketch only configured pins relevant to its own function. The unified `setup()` initializes all pins regardless of which operation will follow. In practice this is safe: DAC pins idle LOW, CS pins idle HIGH. No operation drives pins that belong to the other phase.
