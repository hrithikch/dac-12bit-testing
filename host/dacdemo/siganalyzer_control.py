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
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "instrument_comms"))

import pyvisa
from dacdemo.comprehensive_analysis import analyze_trace_metrics
from instruments.keysight_exa import KeysightEXA
from dacdemo.snr_analysis import estimate_snr_from_trace


# Canonical column order for sa-sfdr-sweep CSV output. Both single and windowed
# modes write rows with these exact keys so the file shape stays consistent.
SFDR_SWEEP_FIELDNAMES = [
    "timestamp",
    "mode",
    "tone_hz_target",
    "dac_clock_hz",
    "center_hz",
    "span_hz",
    "window_span_hz",
    "n_windows",
    "rbw_hz",
    "vbw_hz",
    "ref_level_dbm",
    "fund_freq_hz",
    "fund_amp_dbm",
    "spur_freq_hz",
    "spur_amp_dbm",
    "sfdr_dbc",
    "spur_class",
    "sfdr_valid",
    "harmonic_tol_hz",
    "expected_h2_hz",
    "expected_h3_hz",
    "expected_h4_hz",
    "expected_h5_hz",
    "peak_1_freq_hz", "peak_1_amp_dbm",
    "peak_2_freq_hz", "peak_2_amp_dbm",
    "peak_3_freq_hz", "peak_3_amp_dbm",
    "peak_4_freq_hz", "peak_4_amp_dbm",
]

SNR_SWEEP_FIELDNAMES = [
    "timestamp",
    "mode",
    "tone_hz_target",
    "dac_clock_hz",
    "center_hz",
    "span_hz",
    "rbw_hz",
    "vbw_hz",
    "ref_level_dbm",
    "fund_freq_hz",
    "fund_amp_dbm",
    "noise_freq_hz",
    "noise_left_freq_hz",
    "noise_left_dbm",
    "noise_right_freq_hz",
    "noise_right_dbm",
    "noise_level_dbm",
    "noise_bandwidth_hz",
    "noise_exclusion_hz",
    "noise_method",
    "snr_db",
]

COMPREHENSIVE_SWEEP_FIELDNAMES = [
    "timestamp",
    "mode",
    "tone_hz_target",
    "tone_hz_clipped",
    "tone_hz_actual",
    "coherent_bin_k",
    "dac_clock_hz",
    "center_hz",
    "span_hz",
    "rbw_hz",
    "vbw_hz",
    "ref_level_dbm",
    "fund_freq_hz",
    "fund_amp_dbm",
    "spur_freq_hz",
    "spur_amp_dbm",
    "sfdr_dbc",
    "spur_class",
    "sfdr_valid",
    "harmonic_tol_hz",
    "expected_h2_hz",
    "expected_h3_hz",
    "expected_h4_hz",
    "expected_h5_hz",
    "h2_freq_hz",
    "h2_amp_dbm",
    "h2_dbc",
    "h3_freq_hz",
    "h3_amp_dbm",
    "h3_dbc",
    "h4_freq_hz",
    "h4_amp_dbm",
    "h5_freq_hz",
    "h5_amp_dbm",
    "thd_dbc",
    "noise_freq_hz",
    "noise_left_freq_hz",
    "noise_left_dbm",
    "noise_right_freq_hz",
    "noise_right_dbm",
    "noise_level_dbm",
    "noise_bandwidth_hz",
    "noise_exclusion_hz",
    "noise_method",
    "snr_db",
]


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

    def measure_sfdr(
        self,
        center_hz: float,
        span_hz: float,
        rbw_hz: float = 10e3,
        vbw_hz: float = 10e3,
        ref_level_dbm: float = 0.0,
        sa_settle_s: float = 0.0,
    ) -> dict:
        """
        Configure the analyzer, run one sweep, place two markers (fundamental
        and worst spur), and return SFDR results.

        sa_settle_s: delay between configure and sweep trigger to let the SA
        trace stabilize on the new window settings (default 0 = no delay).

        Returns a dict shaped to SFDR_SWEEP_FIELDNAMES (peak_1 = fund marker,
        peak_2 = spur marker, peak_3/4 = NaN since single mode uses 2 markers).
        """
        self._drv.configure_spectrum_view(
            center_hz=center_hz,
            span_hz=span_hz,
            rbw_hz=rbw_hz,
            vbw_hz=vbw_hz,
            ref_level_dbm=ref_level_dbm,
        )
        if sa_settle_s > 0:
            time.sleep(sa_settle_s)
        self._drv.single_sweep()
        result = self._drv.measure_sfdr()
        return {
            "mode":           "single",
            "center_hz":      center_hz,
            "span_hz":        span_hz,
            "window_span_hz": float("nan"),
            "n_windows":      1,
            "rbw_hz":         rbw_hz,
            "vbw_hz":         vbw_hz,
            "ref_level_dbm":  ref_level_dbm,
            "fund_freq_hz":   result["fund_freq_hz"],
            "fund_amp_dbm":   result["fund_amp_dbm"],
            "spur_freq_hz":   result["spur_freq_hz"],
            "spur_amp_dbm":   result["spur_amp_dbm"],
            "sfdr_dbc":       result["sfdr_dbc"],
            "peak_1_freq_hz": result["fund_freq_hz"],
            "peak_1_amp_dbm": result["fund_amp_dbm"],
            "peak_2_freq_hz": result["spur_freq_hz"],
            "peak_2_amp_dbm": result["spur_amp_dbm"],
            "peak_3_freq_hz": float("nan"),
            "peak_3_amp_dbm": float("nan"),
            "peak_4_freq_hz": float("nan"),
            "peak_4_amp_dbm": float("nan"),
        }

    def measure_snr(
        self,
        center_hz: float,
        span_hz: float,
        rbw_hz: float = 10e3,
        vbw_hz: float = 10e3,
        ref_level_dbm: float = 0.0,
        noise_bw_hz: float | None = None,
        dac_clock_hz: float | None = None,
        sa_settle_s: float = 0.0,
    ) -> dict:
        """
        Configure the analyzer, run one sweep, and estimate SNR from the trace.

        The signal is the highest peak in the current span. Noise is estimated
        from nearby left/right trace windows while avoiding the tone and
        expected harmonics.
        """
        if noise_bw_hz is None:
            noise_bw_hz = span_hz
        self._drv.configure_spectrum_view(
            center_hz=center_hz,
            span_hz=span_hz,
            rbw_hz=rbw_hz,
            vbw_hz=vbw_hz,
            ref_level_dbm=ref_level_dbm,
        )
        if sa_settle_s > 0:
            time.sleep(sa_settle_s)
        self._drv.single_sweep()
        fund_freq_hz, fund_amp_dbm = self._drv.measure_peak()
        trace_dbm = self._drv.get_trace_ascii()
        noise = estimate_snr_from_trace(
            trace_dbm=trace_dbm,
            center_hz=center_hz,
            span_hz=span_hz,
            rbw_hz=rbw_hz,
            fund_freq_hz=fund_freq_hz,
            fund_amp_dbm=fund_amp_dbm,
            noise_bw_hz=noise_bw_hz,
            dac_clock_hz=dac_clock_hz,
        )
        return {
            "mode": "single",
            "center_hz": center_hz,
            "span_hz": span_hz,
            "rbw_hz": rbw_hz,
            "vbw_hz": vbw_hz,
            "ref_level_dbm": ref_level_dbm,
            "fund_freq_hz": fund_freq_hz,
            "fund_amp_dbm": fund_amp_dbm,
            **noise,
        }

    def measure_comprehensive(
        self,
        center_hz: float,
        span_hz: float,
        rbw_hz: float,
        vbw_hz: float,
        ref_level_dbm: float,
        noise_bw_hz: float,
        dac_clock_hz: float,
        num_samples: int,
        sa_settle_s: float = 0.0,
    ) -> dict:
        """
        Configure the analyzer, run one sweep, and derive comprehensive RF
        metrics from a single trace: SFDR, SNR, THD, and harmonics up to 5H.
        """
        self._drv.configure_spectrum_view(
            center_hz=center_hz,
            span_hz=span_hz,
            rbw_hz=rbw_hz,
            vbw_hz=vbw_hz,
            ref_level_dbm=ref_level_dbm,
        )
        if sa_settle_s > 0:
            time.sleep(sa_settle_s)
        self._drv.single_sweep()
        fund_freq_hz, fund_amp_dbm = self._drv.measure_peak()
        trace_dbm = self._drv.get_trace_ascii()
        return analyze_trace_metrics(
            trace_dbm=trace_dbm,
            center_hz=center_hz,
            span_hz=span_hz,
            rbw_hz=rbw_hz,
            vbw_hz=vbw_hz,
            ref_level_dbm=ref_level_dbm,
            fund_freq_hz=fund_freq_hz,
            fund_amp_dbm=fund_amp_dbm,
            dac_clock_hz=dac_clock_hz,
            noise_bw_hz=noise_bw_hz,
            num_samples=num_samples,
        )

    def measure_sfdr_windowed(
        self,
        dac_clock_hz: float,
        rbw_hz: float = 100e3,
        vbw_hz: float = 10e3,
        ref_level_dbm: float = 0.0,
        sa_settle_s: float = 1.0,
    ) -> dict:
        """
        Divide the Nyquist band (0 to dac_clock_hz/2) into 4 equal windows,
        find the highest peak in each, then compute SFDR from the two highest
        peaks across all windows.

        Narrower span per window (dac_clock_hz/8) gives 4x better frequency
        resolution than a single full-band sweep at the same RBW.

        Returns a dict shaped to SFDR_SWEEP_FIELDNAMES; peak_1..peak_4 are the
        per-window peaks in window order (peak_1 = lowest center, peak_4 = highest).
        """
        window_span = dac_clock_hz / 8
        window_centers = [(2 * i + 1) * dac_clock_hz / 16 for i in range(4)]
        window_peaks = []  # (freq, amp) per window, in window order
        for center in window_centers:
            self._drv.configure_spectrum_view(
                center_hz=center,
                span_hz=window_span,
                rbw_hz=rbw_hz,
                vbw_hz=vbw_hz,
                ref_level_dbm=ref_level_dbm,
            )
            if sa_settle_s > 0:
                time.sleep(sa_settle_s)
            self._drv.single_sweep()
            window_peaks.append(self._drv.measure_peak())

        ranked = sorted(window_peaks, key=lambda p: p[1], reverse=True)
        fund_freq, fund_amp = ranked[0]
        spur_freq, spur_amp = ranked[1]
        return {
            "mode":           "windowed",
            "center_hz":      dac_clock_hz / 4,
            "span_hz":        dac_clock_hz / 2,
            "window_span_hz": window_span,
            "n_windows":      4,
            "rbw_hz":         rbw_hz,
            "vbw_hz":         vbw_hz,
            "ref_level_dbm":  ref_level_dbm,
            "fund_freq_hz":   fund_freq,
            "fund_amp_dbm":   fund_amp,
            "spur_freq_hz":   spur_freq,
            "spur_amp_dbm":   spur_amp,
            "sfdr_dbc":       fund_amp - spur_amp,
            "peak_1_freq_hz": window_peaks[0][0], "peak_1_amp_dbm": window_peaks[0][1],
            "peak_2_freq_hz": window_peaks[1][0], "peak_2_amp_dbm": window_peaks[1][1],
            "peak_3_freq_hz": window_peaks[2][0], "peak_3_amp_dbm": window_peaks[2][1],
            "peak_4_freq_hz": window_peaks[3][0], "peak_4_amp_dbm": window_peaks[3][1],
        }

    def screenshot(self, path: Path) -> None:
        """Capture a PNG screenshot from the analyzer display and write it to disk."""
        self._drv.save_screen_image_to_file(path)

    def idn(self) -> str:
        return self._drv.do_query_string("*IDN?").strip()

    def close(self) -> None:
        self._rm.close()


def save_measurements_csv(row: dict, path: Path, fieldnames: list | None = None) -> None:
    """
    Append a measurement row to a CSV file.

    If fieldnames is provided, it pins the column order. When the existing file's
    header does not match, the old file is auto-renamed to
    <stem>.legacy-<YYYYMMDDTHHMMSS>.csv so the new schema can start fresh
    without silently misaligning columns.

    If fieldnames is None, the legacy behavior applies (fieldnames inferred
    from the row's keys with a leading "timestamp" column).
    """
    import datetime
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now()

    if fieldnames is None:
        fieldnames = ["timestamp"] + list(row.keys())
    else:
        fieldnames = list(fieldnames)

    if path.exists():
        with open(path, "r", newline="") as f:
            existing_header = next(csv.reader(f), [])
        if existing_header != fieldnames:
            stamp = now.strftime("%Y%m%dT%H%M%S")
            archive = path.with_name(f"{path.stem}.legacy-{stamp}{path.suffix}")
            # Collision guard: bump with a counter if the same-second name exists.
            counter = 1
            while archive.exists():
                archive = path.with_name(
                    f"{path.stem}.legacy-{stamp}-{counter}{path.suffix}"
                )
                counter += 1
            path.rename(archive)
            print(f"[csv] schema changed - archived old file -> {archive.name}")

    write_header = not path.exists()
    out_row = {"timestamp": now.isoformat(), **row}
    # Drop unknown keys when fieldnames is pinned to avoid DictWriter raising.
    out_row = {k: out_row.get(k, "") for k in fieldnames}
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if write_header:
            w.writeheader()
        w.writerow(out_row)
    print(f"Measurements -> {path}")
