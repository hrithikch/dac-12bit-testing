from dataclasses import dataclass
from math import log10

# Fixed scaling factor — not a user parameter.
# Encodes the MATLAB 2.^(10.*log10(x)/3) convention used in the original design.
# With fs_app in the range of thousands, fs_actual = fs_app * 2^20.
_MULTIPLIER = 1e6


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
    def is_prime(v: int) -> bool:
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

    lower = x_seed
    upper = x_seed
    while True:
        if is_prime(lower) and is_prime(upper):
            out = sorted(set([lower, upper]))
            return out
        if not is_prime(lower):
            lower -= 1
        if not is_prime(upper):
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
