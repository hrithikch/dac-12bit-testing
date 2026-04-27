# host/dacdemo/comprehensive_analysis.py
#
# Pure helpers for deriving comprehensive RF metrics from a single SA trace:
# SNR, SFDR, harmonic amplitudes (2H..5H), and THD.

import math

from dacdemo.sfdr_analysis import classify_spur, expected_harmonics
from dacdemo.snr_analysis import estimate_snr_from_trace, trace_frequencies


def _dbm_to_mw(dbm: float) -> float:
    if not math.isfinite(dbm):
        return 0.0
    return 10 ** (dbm / 10)


def _mw_to_dbm(mw: float) -> float:
    if mw <= 0:
        return float("nan")
    return 10 * math.log10(mw)


def _peak_near_frequency(trace_dbm: list[float], freqs_hz: list[float], target_hz: float, tol_hz: float) -> tuple[float, float]:
    best_amp = float("nan")
    best_freq = float("nan")
    for freq_hz, amp_dbm in zip(freqs_hz, trace_dbm):
        if not math.isfinite(amp_dbm):
            continue
        if abs(freq_hz - target_hz) > tol_hz:
            continue
        if not math.isfinite(best_amp) or amp_dbm > best_amp:
            best_amp = amp_dbm
            best_freq = freq_hz
    return best_freq, best_amp


def _find_worst_spur(
    trace_dbm: list[float],
    freqs_hz: list[float],
    fund_freq_hz: float,
    exclusion_hz: float,
    dc_guard_hz: float = 0.0,
) -> tuple[float, float]:
    best_amp = float("nan")
    best_freq = float("nan")
    for freq_hz, amp_dbm in zip(freqs_hz, trace_dbm):
        if not math.isfinite(amp_dbm):
            continue
        if abs(freq_hz) <= dc_guard_hz:
            continue
        if abs(freq_hz - fund_freq_hz) <= exclusion_hz:
            continue
        if not math.isfinite(best_amp) or amp_dbm > best_amp:
            best_amp = amp_dbm
            best_freq = freq_hz
    return best_freq, best_amp


def analyze_trace_metrics(
    trace_dbm: list[float],
    center_hz: float,
    span_hz: float,
    rbw_hz: float,
    vbw_hz: float,
    ref_level_dbm: float,
    fund_freq_hz: float,
    fund_amp_dbm: float,
    dac_clock_hz: float,
    noise_bw_hz: float,
    num_samples: int,
    harmonic_orders=(2, 3, 4, 5),
) -> dict:
    freqs_hz = trace_frequencies(center_hz, span_hz, len(trace_dbm))
    bin_width_hz = span_hz / max(len(trace_dbm) - 1, 1)
    harmonic_tol_hz = max(3 * bin_width_hz, 2 * rbw_hz, dac_clock_hz / num_samples)
    exclusion_hz = max(3 * bin_width_hz, 2 * rbw_hz)
    dc_guard_hz = exclusion_hz

    expected = expected_harmonics(fund_freq_hz, dac_clock_hz, orders=harmonic_orders)
    harmonic_results = {}
    for order, expected_hz in expected.items():
        peak_freq_hz, peak_amp_dbm = _peak_near_frequency(
            trace_dbm=trace_dbm,
            freqs_hz=freqs_hz,
            target_hz=expected_hz,
            tol_hz=harmonic_tol_hz,
        )
        harmonic_results[order] = {
            "expected_hz": expected_hz,
            "freq_hz": peak_freq_hz,
            "amp_dbm": peak_amp_dbm,
            "dbc": fund_amp_dbm - peak_amp_dbm if math.isfinite(peak_amp_dbm) else float("nan"),
        }

    spur_freq_hz, spur_amp_dbm = _find_worst_spur(
        trace_dbm=trace_dbm,
        freqs_hz=freqs_hz,
        fund_freq_hz=fund_freq_hz,
        exclusion_hz=exclusion_hz,
        dc_guard_hz=dc_guard_hz,
    )
    sfdr_dbc = fund_amp_dbm - spur_amp_dbm if math.isfinite(spur_amp_dbm) else float("nan")
    spur_class = classify_spur(
        spur_hz=spur_freq_hz,
        fund_hz=fund_freq_hz,
        fs_hz=dac_clock_hz,
        tol_hz=harmonic_tol_hz,
        orders=harmonic_orders,
    )

    noise = estimate_snr_from_trace(
        trace_dbm=trace_dbm,
        center_hz=center_hz,
        span_hz=span_hz,
        rbw_hz=rbw_hz,
        fund_freq_hz=fund_freq_hz,
        fund_amp_dbm=fund_amp_dbm,
        noise_bw_hz=noise_bw_hz,
        dac_clock_hz=dac_clock_hz,
        harmonic_orders=harmonic_orders,
    )

    harmonic_power_mw = sum(_dbm_to_mw(harmonic_results[order]["amp_dbm"]) for order in harmonic_orders)
    thd_dbc = fund_amp_dbm - _mw_to_dbm(harmonic_power_mw) if harmonic_power_mw > 0 else float("nan")

    return {
        "mode": "single",
        "center_hz": center_hz,
        "span_hz": span_hz,
        "rbw_hz": rbw_hz,
        "vbw_hz": vbw_hz,
        "ref_level_dbm": ref_level_dbm,
        "fund_freq_hz": fund_freq_hz,
        "fund_amp_dbm": fund_amp_dbm,
        "spur_freq_hz": spur_freq_hz,
        "spur_amp_dbm": spur_amp_dbm,
        "sfdr_dbc": sfdr_dbc,
        "spur_class": spur_class,
        "sfdr_valid": spur_class != "bin_split",
        "harmonic_tol_hz": harmonic_tol_hz,
        "expected_h2_hz": harmonic_results[2]["expected_hz"],
        "expected_h3_hz": harmonic_results[3]["expected_hz"],
        "expected_h4_hz": harmonic_results[4]["expected_hz"],
        "expected_h5_hz": harmonic_results[5]["expected_hz"],
        "h2_freq_hz": harmonic_results[2]["freq_hz"],
        "h2_amp_dbm": harmonic_results[2]["amp_dbm"],
        "h2_dbc": harmonic_results[2]["dbc"],
        "h3_freq_hz": harmonic_results[3]["freq_hz"],
        "h3_amp_dbm": harmonic_results[3]["amp_dbm"],
        "h3_dbc": harmonic_results[3]["dbc"],
        "h4_freq_hz": harmonic_results[4]["freq_hz"],
        "h4_amp_dbm": harmonic_results[4]["amp_dbm"],
        "h5_freq_hz": harmonic_results[5]["freq_hz"],
        "h5_amp_dbm": harmonic_results[5]["amp_dbm"],
        "thd_dbc": thd_dbc,
        **noise,
    }
