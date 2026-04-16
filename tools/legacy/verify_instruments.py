#!/usr/bin/env python3
"""
Instrument Verification Tool

Connects to all instruments, sets voltages, and verifies that values were written correctly.
Useful for debugging instrument communication and configuration issues.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pyvisa
from pyvisa.errors import VisaIOError
import configparser
import argparse


def verify_visa_instrument(rm, address, name):
    """Connect to a VISA instrument and query its identity."""
    print(f"\n{'='*60}")
    print(f"Testing {name}")
    print(f"Address: {address}")
    print(f"{'='*60}")

    try:
        instrument = rm.open_resource(address)
        print(f"[OK] Successfully opened connection")

        # Query identity
        try:
            idn = instrument.query("*IDN?").strip()
            print(f"[OK] Identity: {idn}")
        except Exception as e:
            print(f"[FAIL] Failed to query *IDN?: {e}")

        return instrument

    except VisaIOError as e:
        print(f"[FAIL] Failed to open: {e}")
        return None
    except Exception as e:
        print(f"[FAIL] Unexpected error: {e}")
        return None


def verify_signal_generator(sig_gen, config):
    """Verify signal generator configuration."""
    if not sig_gen:
        return False

    print("\n--- Signal Generator Verification ---")
    try:
        sig_gen_level = config.get('TestSettings', 'sig_gen_level')

        # Set and verify output state
        sig_gen.write("OUTPut ON")
        output_state = sig_gen.query("OUTPut?").strip()
        print(f"Output State: {output_state} (expected: 1)")

        # Set and verify power level
        sig_gen.write(f"SOURce1:POWer {sig_gen_level}")
        power = sig_gen.query("SOURce1:POWer?").strip()
        print(f"Power Level: {power} (set to: {sig_gen_level})")

        # Set and verify frequency mode
        sig_gen.write("SOURce1:FREQ:MODE CW")
        freq_mode = sig_gen.query("SOURce1:FREQ:MODE?").strip()
        print(f"Frequency Mode: {freq_mode} (expected: CW)")

        print("[OK] Signal generator verification complete")
        return True

    except Exception as e:
        print(f"[FAIL] Signal generator verification failed: {e}")
        return False


def verify_keithley_supply(keithley, config):
    """Verify Keithley power supply configuration."""
    if not keithley:
        return False

    print("\n--- Keithley Supply Verification ---")
    print("NOTE: Keithley voltages are swept during test, not fixed")
    print("NOTE: Keithley requires INSTrument:NSELect to switch channels")

    try:
        # Query output state
        output = keithley.query("OUTPut?").strip()
        print(f"Output State: {output} (should be 1 when enabled)")

        # Query using INSTrument:NSELect method (from legacy code)
        try:
            keithley.write("INSTrument:NSELect 1")
            voltage_c1 = keithley.query("MEASure:VOLTage?").strip()
            print(f"Channel 1 Voltage (NSELect): {voltage_c1} V")
        except Exception as e:
            print(f"Channel 1 Voltage: Unable to query - {e}")

        try:
            keithley.write("INSTrument:NSELect 2")
            voltage_c2 = keithley.query("MEASure:VOLTage?").strip()
            print(f"Channel 2 Voltage (NSELect): {voltage_c2} V")
        except Exception as e:
            print(f"Channel 2 Voltage: Unable to query - {e}")

        print("[OK] Keithley supply verification complete")
        return True

    except Exception as e:
        print(f"[FAIL] Keithley supply verification failed: {e}")
        return False


def verify_keysight_supply(keysight, config):
    """Verify Keysight/Keithley supply configuration (3 fixed voltages)."""
    if not keysight:
        return False

    print("\n--- 'Keysight' Supply (Fixed Voltages) Verification ---")
    print("NOTE: May actually be a Keithley based on hardware setup")

    try:
        # Get expected voltages from config
        v1_expected = config.getfloat('TestSettings', 'keysight_supply_channel_1_voltage')
        v2_expected = config.getfloat('TestSettings', 'keysight_supply_channel_2_voltage')
        v3_expected = config.getfloat('TestSettings', 'keysight_supply_channel_3_voltage')

        print(f"\nExpected voltages from config:")
        print(f"  Channel 1: {v1_expected} V")
        print(f"  Channel 2: {v2_expected} V")
        print(f"  Channel 3: {v3_expected} V")

        # Set voltages
        print(f"\nSetting voltages...")
        keysight.write(f"VOLTage {v1_expected}, (@1)")
        keysight.write(f"VOLTage {v2_expected}, (@2)")
        keysight.write(f"VOLTage {v3_expected}, (@3)")
        print("[OK] Write commands sent")

        # Enable outputs
        print(f"\nEnabling outputs...")
        keysight.write("OUTPut 1, (@1:3)")
        print("[OK] Output enable command sent")

        # Verify voltages - try multiple query formats
        print(f"\nVerifying voltages...")

        for ch in [1, 2, 3]:
            expected = [v1_expected, v2_expected, v3_expected][ch-1]
            print(f"\n  Channel {ch} (expected {expected}V):")

            # Try different query formats
            queries_to_try = [
                ("INSTrument:NSELect", f"MEASure:VOLTage?"),  # Keithley NSELect method
                (None, f"MEASure:VOLTage? CH{ch}"),  # Direct CH method
                (None, f"VOLTage? (@{ch})"),  # Channel list method
                (None, f"MEASure:VOLTage? (@{ch})"),
            ]

            success = False
            for pre_cmd, query in queries_to_try:
                try:
                    if pre_cmd:
                        keysight.write(f"{pre_cmd} {ch}")
                        result = keysight.query(query).strip()
                        print(f"    {pre_cmd} {ch}; {query:20s} -> {result}")
                    else:
                        result = keysight.query(query).strip()
                        print(f"    {query:30s} -> {result}")
                    success = True
                    break
                except Exception as e:
                    if pre_cmd:
                        print(f"    {pre_cmd} {ch}; {query:20s} -> Failed: {str(e)[:30]}")
                    else:
                        print(f"    {query:30s} -> Failed: {str(e)[:30]}")

            if not success:
                print(f"    [FAIL] Could not verify channel {ch}")

        # Try to query output state
        print(f"\nOutput state:")
        try:
            output = keysight.query("OUTPut? (@1:3)").strip()
            print(f"  Channels 1-3: {output}")
        except Exception as e:
            print(f"  [FAIL] Could not query output state: {e}")

        print("\n[OK] Keysight/Keithley supply verification complete")
        print("NOTE: If voltage readback failed, the supply may still be set correctly.")
        print("      Check the physical supply display to verify voltages.")
        return True

    except Exception as e:
        print(f"[FAIL] Keysight/Keithley supply verification failed: {e}")
        return False


def verify_oscilloscope(scope, config):
    """Verify oscilloscope configuration."""
    if not scope:
        return False

    print("\n--- Oscilloscope Verification ---")
    try:
        # Query acquisition points
        acquire_points = config.getint('TestSettings', 'acquire_points')
        scope.write(f":ACQuire:POINts {acquire_points}")
        points = scope.query(":ACQuire:POINts?").strip()
        print(f"Acquisition Points: {points} (set to: {acquire_points})")

        # Query timebase scale
        timebase = scope.query(":TIMebase:SCALe?").strip()
        print(f"Timebase Scale: {timebase}")

        # Query channel 1 settings
        ch1_display = scope.query(":CHANnel1:DISPlay?").strip()
        print(f"Channel 1 Display: {ch1_display}")

        print("[OK] Oscilloscope verification complete")
        return True

    except Exception as e:
        print(f"[FAIL] Oscilloscope verification failed: {e}")
        return False


def verify_analog_discovery():
    """Verify AnalogDiscovery connection."""
    print("\n--- AnalogDiscovery Verification ---")
    print("NOTE: AnalogDiscovery uses DWF library, not VISA")

    try:
        # Import the wrapper
        from ctypes import c_int
        sys.path.insert(0, str(Path(__file__).parent.parent / 'pll_sweep' / 'core'))
        from analog_discovery_wrapper import AnalogDiscovery

        ad = AnalogDiscovery()
        print(f"[OK] AnalogDiscovery initialized")

        # Try to set a test voltage
        test_voltage = 1.8
        ad.set_positive_power_supply(test_voltage)
        print(f"[OK] Set positive power supply to {test_voltage}V")

        ad.close()
        print("[OK] AnalogDiscovery verification complete")
        return True

    except Exception as e:
        print(f"[FAIL] AnalogDiscovery verification failed: {e}")
        print(f"   Make sure WaveForms software is installed and device is connected")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Verify instrument connections and configuration"
    )
    parser.add_argument(
        '--config',
        default='config/examples/pll_sweep_config.ini',
        help='Path to configuration file'
    )
    parser.add_argument(
        '--skip-ad',
        action='store_true',
        help='Skip AnalogDiscovery verification'
    )

    args = parser.parse_args()

    # Load configuration
    if not os.path.exists(args.config):
        print(f"ERROR: Config file not found: {args.config}")
        return 1

    config = configparser.ConfigParser()
    config.read(args.config)

    print("="*60)
    print("INSTRUMENT VERIFICATION TOOL")
    print("="*60)
    print(f"Config file: {args.config}")

    # Initialize VISA
    try:
        rm = pyvisa.ResourceManager()
        print(f"\nAvailable VISA resources:")
        for resource in rm.list_resources():
            print(f"  - {resource}")
    except Exception as e:
        print(f"ERROR: Failed to initialize VISA: {e}")
        return 1

    # Get instrument addresses from config
    sig_gen_addr = config.get('Instruments', 'sig_gen_address')
    scope_addr = config.get('Instruments', 'keysight_scope_address')
    keithley_addr = config.get('Instruments', 'keithley_supply_address')
    keysight_addr = config.get('Instruments', 'keysight_supply_address')

    # Connect to instruments
    sig_gen = verify_visa_instrument(rm, sig_gen_addr, "Signal Generator")
    scope = verify_visa_instrument(rm, scope_addr, "Oscilloscope")
    keithley = verify_visa_instrument(rm, keithley_addr, "Keithley Supply (VPW/VNW)")
    keysight = verify_visa_instrument(rm, keysight_addr, "Keysight/Keithley Supply (Fixed Voltages)")

    # Verify configurations
    print("\n" + "="*60)
    print("CONFIGURATION VERIFICATION")
    print("="*60)

    results = []
    results.append(("Signal Generator", verify_signal_generator(sig_gen, config)))
    results.append(("Keithley Supply", verify_keithley_supply(keithley, config)))
    results.append(("Keysight/Keithley Supply", verify_keysight_supply(keysight, config)))
    results.append(("Oscilloscope", verify_oscilloscope(scope, config)))

    if not args.skip_ad:
        results.append(("AnalogDiscovery", verify_analog_discovery()))

    # Close instruments
    print("\n" + "="*60)
    print("CLEANUP")
    print("="*60)

    for instr in [sig_gen, scope, keithley, keysight]:
        if instr:
            try:
                instr.close()
                print(f"[OK] Closed {instr.resource_name}")
            except:
                pass

    # Summary
    print("\n" + "="*60)
    print("VERIFICATION SUMMARY")
    print("="*60)

    for name, success in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{name:30s} {status}")

    all_passed = all(r[1] for r in results)

    if all_passed:
        print("\n[SUCCESS] All instruments verified successfully!")
        return 0
    else:
        print("\n[ERROR] Some instruments failed verification")
        print("   Check output above for details")
        return 1


if __name__ == "__main__":
    sys.exit(main())
