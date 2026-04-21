# host/dacdemo/sfdr_analysis.py
#
# Pure helpers for validating sa-sfdr-sweep results: fold harmonics into the
# Nyquist band, predict where 2nd..5th harmonics of a fundamental should land,
# and classify a measured spur as harmonic / bin-split / other.
#
# No instrument I/O — safe to import and unit-test.

import math


def alias_to_nyquist(f_hz: float, fs_hz: float) -> float:
    """Fold f_hz into [0, fs/2] using standard Nyquist aliasing."""
    if not math.isfinite(f_hz) or not math.isfinite(fs_hz) or fs_hz <= 0:
        return float("nan")
    m = f_hz % fs_hz
    return fs_hz - m if m > fs_hz / 2 else m


def expected_harmonics(fund_hz: float, fs_hz: float, orders=(2, 3, 4, 5)) -> dict:
    """Return {n: aliased_freq_hz} for the requested harmonic orders."""
    return {n: alias_to_nyquist(n * fund_hz, fs_hz) for n in orders}


def classify_spur(
    spur_hz: float,
    fund_hz: float,
    fs_hz: float,
    tol_hz: float,
    orders=(2, 3, 4, 5),
) -> str:
    """
    Classify the measured spur relative to the fundamental:
        'unknown'    — spur or fund is NaN
        'bin_split'  — spur within tol_hz of fundamental (false SFDR from FFT bin split)
        'harmonic_N' — spur within tol_hz of nth folded harmonic (closest order wins)
        'other'      — real peak, but not a predicted harmonic
    Bin-split is checked first; the user explicitly wants it flagged.
    """
    if not (math.isfinite(spur_hz) and math.isfinite(fund_hz)):
        return "unknown"
    if abs(spur_hz - fund_hz) < tol_hz:
        return "bin_split"
    harmonics = expected_harmonics(fund_hz, fs_hz, orders=orders)
    best_n, best_diff = None, float("inf")
    for n, h_hz in harmonics.items():
        d = abs(spur_hz - h_hz)
        if d < tol_hz and d < best_diff:
            best_n, best_diff = n, d
    return f"harmonic_{best_n}" if best_n is not None else "other"
