from math import sin, pi


def generate_sine_codes(f_out: float, f_sample: float, num_samples: int = 256, full_scale: int = 4095) -> list[int]:
    m = (f_out * num_samples) / f_sample
    amplitude = full_scale / 2.0
    offset = full_scale / 2.0
    return [
        int(round(amplitude * sin(2.0 * pi * m * k / float(num_samples)) + offset))
        for k in range(num_samples)
    ]
