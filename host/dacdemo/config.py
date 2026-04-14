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
        return tomllib.load(f)


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
