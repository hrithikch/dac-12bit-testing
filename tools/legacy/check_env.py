#!/usr/bin/env python3
"""
Environment checker for PLL Sweep Automation.

Validates that all required dependencies and instruments are available.
"""

import sys
import os
import importlib
from pathlib import Path
from typing import Any

# Symbols that work across platforms
CHECK = "[OK]"
WARN = "[!!]"
FAIL = "[XX]"
INFO = "[i]"


def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def check_python():
    """Check Python version and executable."""
    print_section("Python Environment")
    print(f"{CHECK} Python executable: {sys.executable}")

    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    print(f"{CHECK} Python version: {version_str}")

    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"{WARN} WARNING: Python 3.8+ recommended (you have {version_str})")
        return False
    return True


def check_venv():
    """Check if running in virtual environment."""
    print_section("Virtual Environment")

    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)

    if in_venv:
        print(f"[OK] Running in virtual environment")
        print(f"  Path: {sys.prefix}")
        return True
    else:
        print(f"[!!] WARNING: Not in virtual environment")
        print(f"  Current prefix: {sys.prefix}")
        print(f"  Recommend: .venv/Scripts/activate (Windows) or source .venv/bin/activate (Linux/Mac)")
        return False


def check_package(name, required=True):
    """Check if a Python package is installed."""
    try:
        module = importlib.import_module(name)
        version = getattr(module, "__version__", "unknown")
        print(f"[OK] {name:20s} version: {version}")
        return True
    except ImportError:
        if required:
            print(f"[XX] {name:20s} NOT INSTALLED (required)")
        else:
            print(f"[!!] {name:20s} not installed (optional)")
        return not required


def check_required_packages():
    """Check all required Python packages."""
    print_section("Required Packages")

    required = [
        "pyvisa",
        "pandas",
        "numpy",
    ]

    all_ok = True
    for pkg in required:
        if not check_package(pkg, required=True):
            all_ok = False

    return all_ok


def check_optional_packages():
    """Check optional development packages."""
    print_section("Development Packages (Optional)")

    optional = [
        "black",
        "ruff",
        "mypy",
        "pytest",
        "pre_commit",
    ]

    for pkg in optional:
        check_package(pkg, required=False)


def check_visa():
    """Check VISA library and list available instruments."""
    print_section("VISA / Instrument Communication")

    try:
        import pyvisa
        rm = pyvisa.ResourceManager()

        print(f"[OK] VISA library loaded: {rm.visalib}")

        # List available instruments
        resources = rm.list_resources()
        if resources:
            print(f"\n[OK] Found {len(resources)} instrument(s):")
            for addr in resources:
                print(f"    • {addr}")
        else:
            print(f"\n[!!] No instruments detected")
            print(f"  Check:")
            print(f"    - Instruments are powered on")
            print(f"    - USB/Network connections")
            print(f"    - NI-VISA or VISA backend installed")

        return True

    except Exception as e:
        print(f"[XX] ERROR loading VISA: {e}")
        print(f"\n  Install NI-VISA from: https://www.ni.com/en-us/support/downloads/drivers/download.ni-visa.html")
        return False


def check_visa_drivers():
    """Check for VISA driver DLLs (Windows)."""
    if sys.platform != 'win32':
        return True

    print_section("VISA Drivers (Windows)")

    windir = os.environ.get("WINDIR", "C:\\Windows")
    visa_dll = Path(windir) / "System32" / "visa32.dll"

    if visa_dll.exists():
        print(f"[OK] visa32.dll found: {visa_dll}")
        return True
    else:
        print(f"[!!] visa32.dll not found at: {visa_dll}")
        print(f"  NI-VISA may not be installed properly")
        return False


def check_project_structure():
    """Check that project directories exist."""
    print_section("Project Structure")

    # Assume script is in tools/ directory
    project_root = Path(__file__).parent.parent

    required_dirs = [
        "bin",
        "pll_sweep",
        "config",
        "docs",
    ]

    all_ok = True
    for dir_name in required_dirs:
        dir_path = project_root / dir_name
        if dir_path.exists():
            print(f"[OK] {dir_name:15s} directory exists")
        else:
            print(f"[XX] {dir_name:15s} directory MISSING")
            all_ok = False

    # Check for workspace directory (created at runtime)
    workspace = project_root / "workspace"
    if workspace.exists():
        print(f"[OK] workspace        directory exists")
    else:
        print(f"[i] workspace        directory not yet created (normal)")

    return all_ok


def check_cli_tools():
    """Check that CLI tools are accessible."""
    print_section("CLI Tools")

    project_root = Path(__file__).parent.parent
    bin_dir = project_root / "bin"

    tools = [
        "pll_sweep",
        "pll_measure",
        "pll_parse",
        "pll_clean",
    ]

    all_ok = True
    for tool in tools:
        tool_path = bin_dir / tool
        if tool_path.exists():
            print(f"[OK] {tool:15s} found")
        else:
            print(f"[XX] {tool:15s} MISSING")
            all_ok = False

    return all_ok


def main():
    """Run all environment checks."""
    print("\n" + "="*60)
    print("  PLL Sweep Automation - Environment Check")
    print("="*60)

    results = {
        "Python": check_python(),
        "Virtual Environment": check_venv(),
        "Required Packages": check_required_packages(),
        "VISA": check_visa(),
        "VISA Drivers": check_visa_drivers(),
        "Project Structure": check_project_structure(),
        "CLI Tools": check_cli_tools(),
    }

    # Optional packages don't affect pass/fail
    check_optional_packages()

    # Summary
    print_section("Summary")

    all_passed = all(results.values())

    for check, passed in results.items():
        status = "[OK] PASS" if passed else "[XX] FAIL"
        print(f"{status:8s} {check}")

    print()
    if all_passed:
        print("[OK] All checks passed! Ready to run sweeps.")
        return 0
    else:
        print("[!!] Some checks failed. Please resolve issues before running sweeps.")
        print("\nFor help:")
        print("  • Install dependencies: .venv/Scripts/pip install -r requirements.txt")
        print("  • Activate venv: .venv/Scripts/activate (Windows)")
        print("  • Install NI-VISA: https://www.ni.com/en-us/support/downloads/drivers/download.ni-visa.html")
        return 1


if __name__ == "__main__":
    sys.exit(main())
