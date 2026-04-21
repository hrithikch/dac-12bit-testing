from dataclasses import dataclass
from math import log10

# Fixed scaling factor — not a user parameter.
# Encodes the MATLAB 2.^(10.*log10(x)/3) convention used in the original design.
# With fs_app in the range of thousands, fs_actual = fs_app * 2^20.
_MULTIPLIER = 1e6


def _is_prime(v: int) -> bool:
    if v < 2:
        return False
    if v % 2 == 0:
        return v == 2
    d = 3
    while d * d <= v:
        if v % d == 0:
            return False
        d += 2
    return True


@dataclass
class CoherentTonePlan:
    fs_app: float
    fs_actual: float    # DAC sample clock frequency (Hz) — written to [dac] f_sample
    n: int              # number of samples (from [dac] num_samples)
    x_seed: int
    fin: str            # "low" or "high"
    prime_bins: list[int]
    fin_low: float
    fin_high: float
    f_out: float        # selected output frequency — written to [dac] f_out


def matlab_equivalent_fs_actual(fs_app: float) -> float:
    return fs_app * 2 ** (10 * (log10(_MULTIPLIER) / 3))


def nearest_prime_bins(x_seed: int) -> list[int]:
    lower = x_seed
    upper = x_seed
    while True:
        if _is_prime(lower) and _is_prime(upper):
            out = sorted(set([lower, upper]))
            return out
        if not _is_prime(lower):
            lower -= 1
        if not _is_prime(upper):
            upper += 1


def build_plan(fs_app: float, n: int, x_seed: int, fin: str = "low") -> CoherentTonePlan:
    fs_actual = matlab_equivalent_fs_actual(fs_app)
    bins = nearest_prime_bins(x_seed)
    fin_low  = bins[0]  * (fs_actual / n)
    fin_high = bins[-1] * (fs_actual / n)
    f_out = fin_low if fin == "low" else fin_high
    return CoherentTonePlan(
        fs_app=fs_app,
        fs_actual=fs_actual,
        n=n,
        x_seed=x_seed,
        fin=fin,
        prime_bins=bins,
        fin_low=fin_low,
        fin_high=fin_high,
        f_out=f_out,
    )


def find_coherent_bin(f_out_target: float, f_sample: float, n: int) -> tuple[int, str]:
    """
    Back-calculate x_seed and fin from a desired output frequency.

    Finds the prime bin b closest to the ideal (f_out_target * n / f_sample),
    returning (x_seed, fin) such that build_plan(..., x_seed=x_seed, fin=fin)
    produces f_out as close as possible to f_out_target.

    Since the returned x_seed is itself prime, nearest_prime_bins(x_seed)
    returns [x_seed] and fin="low" always selects it — but fin is returned
    accurately in case the caller wants to log it.
    """
    b_ideal = f_out_target * n / f_sample
    b_seed = max(2, round(b_ideal))
    bins = nearest_prime_bins(b_seed)
    b_low, b_high = bins[0], bins[-1]
    if abs(b_low - b_ideal) <= abs(b_high - b_ideal):
        return b_low, "low"
    else:
        return b_high, "high"


def find_coherent_inband_bin(f_out_target: float, f_sample: float, n: int) -> tuple[int, str, float]:
    """
    Clip the requested tone to Nyquist, then return the nearest coherent prime
    bin whose generated tone remains in-band (<= f_sample / 2).

    Returns:
        (prime_bin, fin, clipped_target_hz)
    """
    nyquist_hz = f_sample / 2
    clipped_target_hz = min(max(f_out_target, 0.0), nyquist_hz)
    max_bin = max(2, int(n // 2))
    b_ideal = clipped_target_hz * n / f_sample
    b_seed = min(max(2, round(b_ideal)), max_bin)

    best_bin = None
    best_diff = float("inf")
    max_radius = max(b_seed - 2, max_bin - b_seed)
    for radius in range(max_radius + 1):
        candidates = []
        lower = b_seed - radius
        upper = b_seed + radius
        if 2 <= lower <= max_bin:
            candidates.append(lower)
        if upper != lower and 2 <= upper <= max_bin:
            candidates.append(upper)
        for candidate in candidates:
            if not _is_prime(candidate):
                continue
            diff = abs(candidate - b_ideal)
            if diff < best_diff or (diff == best_diff and candidate > best_bin):
                best_bin = candidate
                best_diff = diff
        if best_bin is not None and radius > best_diff:
            break

    if best_bin is None:
        best_bin = 2
    return best_bin, "low", clipped_target_hz
