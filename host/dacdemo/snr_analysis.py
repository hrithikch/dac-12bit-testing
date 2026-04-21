# host/dacdemo/snr_analysis.py
#
# Pure helpers for estimating SNR from a swept spectrum trace. The workflow is:
#   1. Find the fundamental elsewhere.
#   2. Probe left/right nearby noise windows, skipping the tone and harmonics.
#   3. Convert the measured noise in RBW to the requested integrated BW.
#
# No instrument I/O - safe to import and smoke-test locally.

import math
import statistics

from dacdemo.sfdr_analysis import expected_harmonics


def trace_frequencies(center_hz: float, span_hz: float, n_points: int) -> list[float]:
    """Return the frequency axis for an equally-spaced zero-span trace."""
    if (
        not math.isfinite(center_hz)
        or not math.isfinite(span_hz)
        or span_hz <= 0
        or n_points <= 0
    ):
        return []
    if n_points == 1:
        return [center_hz]
    start_hz = center_hz - span_hz / 2
    step_hz = span_hz / (n_points - 1)
    return [start_hz + i * step_hz for i in range(n_points)]


def integrated_noise_dbm(noise_level_dbm: float, noise_bw_hz: float, rbw_hz: float) -> float:
    """Scale a noise measurement made in RBW to an integrated bandwidth."""
    if not (
        math.isfinite(noise_level_dbm)
        and math.isfinite(noise_bw_hz)
        and math.isfinite(rbw_hz)
        and noise_bw_hz > 0
        and rbw_hz > 0
    ):
        return float("nan")
    return noise_level_dbm + 10 * math.log10(noise_bw_hz / rbw_hz)


def calculate_snr_db(fund_amp_dbm: float, noise_level_dbm: float, noise_bw_hz: float, rbw_hz: float) -> float:
    """Compute SNR in dB from signal power and an RBW-limited noise reading."""
    noise_total_dbm = integrated_noise_dbm(noise_level_dbm, noise_bw_hz, rbw_hz)
    if not (math.isfinite(fund_amp_dbm) and math.isfinite(noise_total_dbm)):
        return float("nan")
    return fund_amp_dbm - noise_total_dbm


def _window_stats(
    trace_dbm: list[float],
    freqs_hz: list[float],
    blocked: list[bool],
    center_idx: int,
    half_window_bins: int,
) -> dict | None:
    start = max(0, center_idx - half_window_bins)
    stop = min(len(trace_dbm), center_idx + half_window_bins + 1)
    if start >= stop:
        return None
    if any(blocked[start:stop]):
        return None
    values = [v for v in trace_dbm[start:stop] if math.isfinite(v)]
    if len(values) < 3:
        return None
    median_dbm = statistics.median(values)
    return {
        "freq_hz": freqs_hz[center_idx],
        "noise_dbm": median_dbm,
        "peak_dbm": max(values),
        "min_dbm": min(values),
        "spuriness_db": max(values) - median_dbm,
    }


def estimate_snr_from_trace(
    trace_dbm: list[float],
    center_hz: float,
    span_hz: float,
    rbw_hz: float,
    fund_freq_hz: float,
    fund_amp_dbm: float,
    noise_bw_hz: float,
    dac_clock_hz: float | None = None,
    harmonic_orders=(2, 3, 4, 5),
) -> dict:
    """
    Estimate SNR from a trace by probing symmetric windows around the signal.

    The preferred result comes from a left/right pair at the same offset from
    the fundamental. Each probe window is rejected if it overlaps the
    fundamental, a predicted harmonic, or looks spur-dominated. If no suitable
    pair is found, the best single-side probe is used; if that fails too, fall
    back to the median of all allowed bins.
    """
    freqs_hz = trace_frequencies(center_hz, span_hz, len(trace_dbm))
    if not freqs_hz or not math.isfinite(fund_freq_hz):
        return {
            "noise_freq_hz": float("nan"),
            "noise_left_freq_hz": float("nan"),
            "noise_left_dbm": float("nan"),
            "noise_right_freq_hz": float("nan"),
            "noise_right_dbm": float("nan"),
            "noise_level_dbm": float("nan"),
            "noise_bandwidth_hz": noise_bw_hz,
            "noise_method": "invalid_trace",
            "noise_exclusion_hz": float("nan"),
            "snr_db": float("nan"),
        }

    bin_width_hz = span_hz / max(len(trace_dbm) - 1, 1)
    exclusion_hz = max(3 * bin_width_hz, 2 * rbw_hz)
    half_window_bins = max(1, math.ceil(max(rbw_hz, 5 * bin_width_hz) / (2 * bin_width_hz)))
    trace_start_hz = freqs_hz[0]
    trace_stop_hz = freqs_hz[-1]

    blocked_freqs = [fund_freq_hz]
    if dac_clock_hz is not None and math.isfinite(dac_clock_hz) and dac_clock_hz > 0:
        blocked_freqs.extend(expected_harmonics(fund_freq_hz, dac_clock_hz, orders=harmonic_orders).values())

    blocked = []
    for freq_hz in freqs_hz:
        blocked.append(any(abs(freq_hz - blocked_hz) <= exclusion_hz for blocked_hz in blocked_freqs))

    base_offset_hz = max(5 * exclusion_hz, 0.02 * span_hz)
    step_hz = max(2 * exclusion_hz, 0.01 * span_hz)
    max_offset_hz = max(0.0, span_hz / 2 - exclusion_hz)
    offsets_hz = []
    offset_hz = base_offset_hz
    while offset_hz <= max_offset_hz:
        offsets_hz.append(offset_hz)
        offset_hz += step_hz

    best_single = None
    for offset_hz in offsets_hz:
        left_hz = fund_freq_hz - offset_hz
        right_hz = fund_freq_hz + offset_hz
        pair = []
        for side, probe_hz in (("left", left_hz), ("right", right_hz)):
            if probe_hz < trace_start_hz or probe_hz > trace_stop_hz:
                pair.append(None)
                continue
            center_idx = min(range(len(freqs_hz)), key=lambda i: abs(freqs_hz[i] - probe_hz))
            stats = _window_stats(trace_dbm, freqs_hz, blocked, center_idx, half_window_bins)
            if stats is not None:
                stats["side"] = side
            pair.append(stats)

        valid = [p for p in pair if p is not None]
        for candidate in valid:
            if candidate["spuriness_db"] <= 6.0:
                if best_single is None or candidate["noise_dbm"] < best_single["noise_dbm"]:
                    best_single = candidate

        left_stats, right_stats = pair
        if (
            left_stats is not None
            and right_stats is not None
            and left_stats["spuriness_db"] <= 6.0
            and right_stats["spuriness_db"] <= 6.0
            and abs(left_stats["noise_dbm"] - right_stats["noise_dbm"]) <= 6.0
        ):
            noise_level_dbm = (left_stats["noise_dbm"] + right_stats["noise_dbm"]) / 2
            return {
                "noise_freq_hz": (left_stats["freq_hz"] + right_stats["freq_hz"]) / 2,
                "noise_left_freq_hz": left_stats["freq_hz"],
                "noise_left_dbm": left_stats["noise_dbm"],
                "noise_right_freq_hz": right_stats["freq_hz"],
                "noise_right_dbm": right_stats["noise_dbm"],
                "noise_level_dbm": noise_level_dbm,
                "noise_bandwidth_hz": noise_bw_hz,
                "noise_method": "paired_probes",
                "noise_exclusion_hz": exclusion_hz,
                "snr_db": calculate_snr_db(
                    fund_amp_dbm=fund_amp_dbm,
                    noise_level_dbm=noise_level_dbm,
                    noise_bw_hz=noise_bw_hz,
                    rbw_hz=rbw_hz,
                ),
            }

    if best_single is not None:
        noise_level_dbm = best_single["noise_dbm"]
        return {
            "noise_freq_hz": best_single["freq_hz"],
            "noise_left_freq_hz": best_single["freq_hz"] if best_single["side"] == "left" else float("nan"),
            "noise_left_dbm": best_single["noise_dbm"] if best_single["side"] == "left" else float("nan"),
            "noise_right_freq_hz": best_single["freq_hz"] if best_single["side"] == "right" else float("nan"),
            "noise_right_dbm": best_single["noise_dbm"] if best_single["side"] == "right" else float("nan"),
            "noise_level_dbm": noise_level_dbm,
            "noise_bandwidth_hz": noise_bw_hz,
            "noise_method": "single_probe",
            "noise_exclusion_hz": exclusion_hz,
            "snr_db": calculate_snr_db(
                fund_amp_dbm=fund_amp_dbm,
                noise_level_dbm=noise_level_dbm,
                noise_bw_hz=noise_bw_hz,
                rbw_hz=rbw_hz,
            ),
        }

    fallback = [v for v, blocked_bin in zip(trace_dbm, blocked) if not blocked_bin and math.isfinite(v)]
    if fallback:
        noise_level_dbm = statistics.median(fallback)
        return {
            "noise_freq_hz": float("nan"),
            "noise_left_freq_hz": float("nan"),
            "noise_left_dbm": float("nan"),
            "noise_right_freq_hz": float("nan"),
            "noise_right_dbm": float("nan"),
            "noise_level_dbm": noise_level_dbm,
            "noise_bandwidth_hz": noise_bw_hz,
            "noise_method": "masked_median_fallback",
            "noise_exclusion_hz": exclusion_hz,
            "snr_db": calculate_snr_db(
                fund_amp_dbm=fund_amp_dbm,
                noise_level_dbm=noise_level_dbm,
                noise_bw_hz=noise_bw_hz,
                rbw_hz=rbw_hz,
            ),
        }

    return {
        "noise_freq_hz": float("nan"),
        "noise_left_freq_hz": float("nan"),
        "noise_left_dbm": float("nan"),
        "noise_right_freq_hz": float("nan"),
        "noise_right_dbm": float("nan"),
        "noise_level_dbm": float("nan"),
        "noise_bandwidth_hz": noise_bw_hz,
        "noise_method": "no_noise_region",
        "noise_exclusion_hz": exclusion_hz,
        "snr_db": float("nan"),
    }
