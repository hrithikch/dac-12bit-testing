# host/dacdemo/siggen_control.py
#
# Thin wrapper around instrument_comms/instruments/rs_siggen.py for DAC clock use.
# The signal generator drives f_sample — the DAC's SPI sample clock.
#
# instrument_comms is imported via sys.path relative to the repo root.

import sys
from pathlib import Path

# Resolve instrument_comms from repo root regardless of where the package is installed
_REPO_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT / "instrument_comms"))

import pyvisa
from instruments.rs_siggen import RohdeAndSchwarzSignalGenerator


class SiggenSession:
    """
    Open session to the R&S SMA100B for DAC sample clock control.

    Usage:
        with SiggenSession(addr) as sg:
            sg.set_clock(5.24288e9, level="700 mV")
    """

    def __init__(self, addr: str, timeout_ms: int = 50_000) -> None:
        self._rm = pyvisa.ResourceManager()
        resource = self._rm.open_resource(addr)
        resource.timeout = timeout_ms
        self._sg = RohdeAndSchwarzSignalGenerator(resource)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def set_clock(self, freq_hz: float, level: str = "700 mV") -> None:
        """
        Configure the signal generator as a fixed-frequency DAC sample clock.

        Sets CW mode, applies frequency and power level, then enables RF output.
        freq_hz : DAC sample clock frequency in Hz (e.g. 5.24288e9)
        level   : output level string with units, e.g. "0 dBm" or "700 mV"
        """
        self._sg.set_continuous_wave_mode()
        self._sg.set_frequency(freq_hz)
        self._sg.set_level(level)
        self._sg.turn_rf_on()
        print(f"Siggen: {freq_hz / 1e9:.6f} GHz  {level}  RF ON")

    def rf_off(self) -> None:
        """Disable RF output without closing the VISA connection."""
        self._sg.turn_rf_off()
        print("Siggen: RF OFF")

    def close(self) -> None:
        self._rm.close()
