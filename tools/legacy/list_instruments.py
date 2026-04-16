#!/usr/bin/env python3
"""
List all available VISA instruments.

Scans for connected instruments and displays their VISA addresses.
Useful for configuring instrument addresses in config files.
"""

import sys
from typing import Any


def list_visa_instruments():
    """List all available VISA instruments."""
    try:
        import pyvisa
    except ImportError:
        print("ERROR: pyvisa not installed")
        print("Install with: pip install pyvisa")
        return False

    try:
        rm = pyvisa.ResourceManager()
        print("\n" + "="*60)
        print("  Available VISA Instruments")
        print("="*60)
        print(f"\nVISA Library: {rm.visalib}")

        resources = rm.list_resources()

        if not resources:
            print("\n[!!] No instruments detected\n")
            print("Troubleshooting:")
            print("  1. Check that instruments are powered on")
            print("  2. Verify USB/Network connections")
            print("  3. Ensure NI-VISA or compatible backend is installed")
            print("  4. For network instruments, verify IP addresses")
            return False

        print(f"\nFound {len(resources)} instrument(s):\n")

        for i, addr in enumerate(resources, 1):
            print(f"{i}. {addr}")

            # Try to get instrument identity
            try:
                inst: Any = rm.open_resource(addr)  # Type hint as Any - pyvisa type stubs incomplete
                inst.timeout = 2000  # 2 second timeout
                idn = inst.query("*IDN?").strip()
                print(f"   ID: {idn}")
                inst.close()
            except Exception as e:
                print(f"   (Could not query identity: {e})")

            print()

        # Show configuration format
        print("="*60)
        print("  Configuration File Format")
        print("="*60)
        print("\n[Instruments]")

        instrument_names = [
            ("sig_gen_address", "Signal Generator"),
            ("keysight_scope_address", "Keysight Oscilloscope"),
            ("keithley_supply_address", "Keithley Power Supply"),
            ("keysight_supply_address", "Keysight Power Supply"),
        ]

        print("\n# Copy addresses from above and paste here:")
        for name, description in instrument_names:
            print(f"{name} = INSTRUMENT_ADDRESS_HERE  # {description}")

        print("\n" + "="*60)
        return True

    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nMake sure VISA backend is installed:")
        print("  • NI-VISA: https://www.ni.com/en-us/support/downloads/drivers/download.ni-visa.html")
        print("  • Or pyvisa-py: pip install pyvisa-py")
        return False


def main():
    """Main entry point."""
    success = list_visa_instruments()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
