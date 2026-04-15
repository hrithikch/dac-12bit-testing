# tools/capture_validate.py
#
# Standalone runner: arms AD3, triggers the DAC demo, decodes and validates
# the captured SPI signals from the ItsyBitsy.
#
# Core logic lives in host/dacdemo/ad3_capture.py.
# This script is a thin wrapper that loads config and calls run().
#
# AD3 connections (see ad3_capture.py for full wiring table):
#   DIO 0 <- SPI_SCK_PAT  DIO 1 <- SPI_SCAN  DIO 4 <- DIN_PAT
#   DIO 5 <- WR_PAT        DIO 6 <- EN_PAT    DIO 7 <- I2C SDA
#
# Run from repo root with venv active:
#   python tools/capture_validate.py

from pathlib import Path
from dacdemo import config as cfg_mod
from dacdemo.ad3_capture import run

if __name__ == "__main__":
    cfg = cfg_mod.load()
    run(
        port=cfg["hardware"]["port"],
        baudrate=cfg["hardware"]["baudrate"],
        f_out=cfg["dac"]["f_out"],
        f_sample=cfg["dac"]["f_sample"],
        output_dir=Path("data/captures"),
        validate=True,
    )
