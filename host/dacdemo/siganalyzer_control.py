# host/dacdemo/siganalyzer_control.py
#
# Keysight N9010B EXA Signal Analyzer wrapper for the DAC demo CLI.
#
# Mirrors scope_control.py in structure — thin session class on top of
# instrument_comms/instruments/keysight_exa.py.
#
# Connection string examples:
#   HiSLIP (preferred): "TCPIP0::<ip>::hislip0::INSTR"
#   VXI-11:             "TCPIP0::<ip>::inst0::INSTR"

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "instrument_comms"))

import pyvisa
from instruments.keysight_exa import KeysightEXA


class SASession:
    """
    Open session to a Keysight N9010B EXA Signal Analyzer.

    Configures a spectrum view, runs a single sweep, and reads peak marker
    measurements. Designed to mirror ScopeSession so CLI integration is uniform.

    Usage:
        with SASession(addr) as sa:
            measurements = sa.measure(center_hz=12.288e6, span_hz=2e6)
            sa.screenshot(Path("sa_screen.png"))
    """

    def __init__(self, addr: str, timeout_ms: int = 60_000) -> None:
        self._rm = pyvisa.ResourceManager()
        self._res = self._rm.open_resource(addr)
        self._res.timeout = timeout_ms
        self._drv = KeysightEXA(self._res)
        self._init()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _init(self) -> None:
        self._res.clear()
        self._drv.clear_status()
        self._drv.turn_off_system_header()

    def measure(
        self,
        center_hz: float,
        span_hz: float,
        rbw_hz: float = 10e3,
        vbw_hz: float = 10e3,
        ref_level_dbm: float = 0.0,
    ) -> dict:
        """
        Configure the analyzer, run one sweep, and return peak marker results.

        Returns a dict with keys:
            center_hz, span_hz, rbw_hz, vbw_hz, ref_level_dbm,
            peak_freq_hz, peak_amp_dbm
        """
        self._drv.configure_spectrum_view(
            center_hz=center_hz,
            span_hz=span_hz,
            rbw_hz=rbw_hz,
            vbw_hz=vbw_hz,
            ref_level_dbm=ref_level_dbm,
        )
        self._drv.single_sweep()
        self._drv.move_marker_to_peak()

        return {
            "center_hz":     center_hz,
            "span_hz":       span_hz,
            "rbw_hz":        rbw_hz,
            "vbw_hz":        vbw_hz,
            "ref_level_dbm": ref_level_dbm,
            "peak_freq_hz":  self._drv.get_marker_frequency_hz(),
            "peak_amp_dbm":  self._drv.get_marker_amplitude_dbm(),
        }

    def screenshot(self, path: Path) -> None:
        """Capture a PNG screenshot from the analyzer display and write it to disk."""
        self._drv.save_screen_image_to_file(path)

    def idn(self) -> str:
        return self._drv.do_query_string("*IDN?").strip()

    def close(self) -> None:
        self._rm.close()


def save_measurements_csv(row: dict, path: Path) -> None:
    """Append a measurement row to a CSV file (creates with header if new)."""
    import datetime
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["timestamp"] + list(row.keys())
    write_header = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        w.writerow({"timestamp": datetime.datetime.now().isoformat(), **row})
    print(f"Measurements -> {path}")
