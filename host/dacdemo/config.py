import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # pip install tomli

_DEFAULT_CONFIG_PATH = Path(__file__).parents[2] / "config" / "dacdemo.toml"


def load(path: Path = _DEFAULT_CONFIG_PATH) -> dict:
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    sweep_name = cfg.get("sweep", {}).get("config", "default")
    sweep_path = path.parent / "sweeps" / f"{sweep_name}.toml"
    if sweep_path.exists():
        with open(sweep_path, "rb") as f:
            cfg["sweep"].update(tomllib.load(f))
    return cfg


def set_port(port: str, path: Path = _DEFAULT_CONFIG_PATH) -> None:
    """Replace the port value in the TOML file in-place, preserving all comments."""
    text = path.read_text(encoding="utf-8")
    updated = re.sub(
        r'^(port\s*=\s*)".+"',
        rf'\g<1>"{port}"',
        text,
        flags=re.MULTILINE,
    )
    path.write_text(updated, encoding="utf-8")


def set_dac_freq(f_out: float, f_sample: float, path: Path = _DEFAULT_CONFIG_PATH) -> None:
    """Write f_out and f_sample back into [dac] in the TOML file in-place."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r'^(f_out\s*=\s*)[\S]+',
        rf'\g<1>{f_out!r}',
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r'^(f_sample\s*=\s*)[\S]+',
        rf'\g<1>{f_sample!r}',
        text,
        flags=re.MULTILINE,
    )
    path.write_text(text, encoding="utf-8")


def set_f_sample(f_sample: float, path: Path = _DEFAULT_CONFIG_PATH) -> None:
    """Update only f_sample in [dac] in-place, leaving f_out unchanged."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r'^(f_sample\s*=\s*)[\S]+',
        rf'\g<1>{f_sample!r}',
        text,
        flags=re.MULTILINE,
    )
    path.write_text(text, encoding="utf-8")


def set_fs_app(fs_app: float, path: Path = _DEFAULT_CONFIG_PATH) -> None:
    """Update fs_app in [coherent_tone] in-place."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r'^(fs_app\s*=\s*)[\S]+',
        rf'\g<1>{fs_app!r}',
        text,
        flags=re.MULTILINE,
    )
    path.write_text(text, encoding="utf-8")


def set_siggen_addr(addr: str, path: Path = _DEFAULT_CONFIG_PATH) -> None:
    """Replace siggen_addr in [instruments] in-place, preserving all comments."""
    text = path.read_text(encoding="utf-8")
    updated = re.sub(
        r'^(siggen_addr\s*=\s*)".+"',
        rf'\g<1>"{addr}"',
        text,
        flags=re.MULTILINE,
    )
    path.write_text(updated, encoding="utf-8")


def set_sa_addr(addr: str, path: Path = _DEFAULT_CONFIG_PATH) -> None:
    """Replace sa_addr in [instruments] in-place, preserving all comments."""
    text = path.read_text(encoding="utf-8")
    updated = re.sub(
        r'^(sa_addr\s*=\s*)".+"',
        rf'\g<1>"{addr}"',
        text,
        flags=re.MULTILINE,
    )
    path.write_text(updated, encoding="utf-8")


def set_scope_addr(addr: str, path: Path = _DEFAULT_CONFIG_PATH) -> None:
    """Replace scope_addr in [instruments] in-place, preserving all comments."""
    text = path.read_text(encoding="utf-8")
    updated = re.sub(
        r'^(scope_addr\s*=\s*)".+"',
        rf'\g<1>"{addr}"',
        text,
        flags=re.MULTILINE,
    )
    path.write_text(updated, encoding="utf-8")


def set_sweep_frequencies(frequencies: list, path: Path = _DEFAULT_CONFIG_PATH) -> None:
    """Write frequencies to the currently active sweep config file."""
    with open(path, "rb") as f:
        cfg = tomllib.load(f)
    sweep_name = cfg.get("sweep", {}).get("config", "default")
    sweep_path = path.parent / "sweeps" / f"{sweep_name}.toml"
    sweep_path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "# Sweep frequencies (Hz) — snapped to coherent prime bins\n"
        "frequencies = [\n"
        + "".join(f"    {f},\n" for f in frequencies)
        + "]\n"
    )
    sweep_path.write_text(content, encoding="utf-8")


def set_sweep_config(name: str, path: Path = _DEFAULT_CONFIG_PATH) -> None:
    """Update the active sweep config name in [sweep] config."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r'^(config\s*=\s*)".+"',
        rf'\g<1>"{name}"',
        text,
        flags=re.MULTILINE,
    )
    path.write_text(text, encoding="utf-8")


def set_coherent_params(x_seed: int, fin: str, path: Path = _DEFAULT_CONFIG_PATH) -> None:
    """Update x_seed and fin in [coherent_tone] in-place."""
    text = path.read_text(encoding="utf-8")
    text = re.sub(
        r'^(x_seed\s*=\s*)\S+',
        rf'\g<1>{x_seed}',
        text,
        flags=re.MULTILINE,
    )
    text = re.sub(
        r'^(fin\s*=\s*)"[^"]+"',
        rf'\g<1>"{fin}"',
        text,
        flags=re.MULTILINE,
    )
    path.write_text(text, encoding="utf-8")
