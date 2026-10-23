#!/usr/bin/env python
"""
Flag every baseline to one tile in a uvfits file, in place.

The file is written to a temporary name beside it, then renamed over the
original, so an interrupted run never leaves it half-written.

Usage:
demo/88_uvflag.py demo/data/1341914000/cal/hyp_cal_1341914000.uvfits \
    --tile HexE11 --pol xx
"""

import argparse
import os

import numpy as np
from pyuvdata import UVData

POL_NUMBERS = {"xx": -5, "yy": -6}


def flag_tile(uv, tile, pol="all"):
    """
    Flag the baselines to `tile` in `uv`, for one polarisation or all of them.

    Returns the number of baseline-times flagged.
    """
    # hyperdrive pads antenna names with spaces
    names = [name.strip() for name in uv.antenna_names]
    if tile not in names:
        raise SystemExit(f"{tile} not in this file's antenna table")
    num = uv.antenna_numbers[names.index(tile)]
    rows = (uv.ant_1_array == num) | (uv.ant_2_array == num)

    if pol == "all":
        uv.flag_array[rows] = True
    else:
        pol_idx = np.where(uv.polarization_array == POL_NUMBERS[pol])[0]
        if len(pol_idx) == 0:
            raise SystemExit(f"no {pol} polarisation in this file")
        uv.flag_array[np.ix_(np.where(rows)[0], np.arange(uv.Nfreqs), pol_idx)] = True
    return int(rows.sum())


def main():
    """Run the main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Flag every baseline to one tile in a uvfits file, in place."
    )
    parser.add_argument("uvfits", help="uvfits file to flag (overwritten)")
    parser.add_argument("--tile", default="HexE11", help="tile name to flag")
    parser.add_argument(
        "--pol",
        choices=["all", *POL_NUMBERS],
        default="all",
        help="polarisation to flag, e.g. xx keeps yy",
    )
    args = parser.parse_args()

    uv = UVData()
    # run_check=False: pyuvdata >= 3 rejects hyperdrive uvfits (pol_convention set
    # with vis_units "uncalib"), so leave the metadata exactly as it is
    uv.read(args.uvfits, file_type="uvfits", run_check=False)
    n_flagged = flag_tile(uv, args.tile, args.pol)

    tmp = args.uvfits + ".flagtmp.uvfits"
    uv.write_uvfits(tmp, run_check=False)
    os.replace(tmp, args.uvfits)
    print(
        f"flagged {args.tile} ({args.pol}) on {n_flagged} of {uv.Nblts}"
        f" baseline-times in {args.uvfits}"
    )


if __name__ == "__main__":
    main()
