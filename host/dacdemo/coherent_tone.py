from dataclasses import dataclass
from math import log10


@dataclass
class CoherentTonePlan:
    fs_app: float
    multiplier: float
    fs_actual: float
    n: int
    x_seed: int
    prime_bins: list[int]
    fin_low: float
    fin_high: float


def matlab_equivalent_fs_actual(fs_app: float = 1000.0, multiplier: float = 1e6) -> float:
    return fs_app * 2 ** (10 * (log10(multiplier) / 3))


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


def build_plan(fs_app: float = 1000.0, multiplier: float = 1e6, n: int = 256, x_seed: int = 4) -> CoherentTonePlan:
    fs_actual = matlab_equivalent_fs_actual(fs_app=fs_app, multiplier=multiplier)
    bins = nearest_prime_bins(x_seed)
    fin_low = bins[0] * (fs_actual / n)
    fin_high = bins[-1] * (fs_actual / n)
    return CoherentTonePlan(
        fs_app=fs_app,
        multiplier=multiplier,
        fs_actual=fs_actual,
        n=n,
        x_seed=x_seed,
        prime_bins=bins,
        fin_low=fin_low,
        fin_high=fin_high,
    )


