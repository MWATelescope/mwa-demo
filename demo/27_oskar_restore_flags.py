#!/usr/bin/env python
"""
Copy FLAG and WEIGHT from the MS that went into hyperdrive to its output.

hyperdrive 0.8.1 (feat/conventions) writes the peeled visibilities of every
channel, but on a MeasurementSet without MWA coarse channels (416 x 48 kHz
here) it flags every channel except the first four in its output. The data in
the flagged channels are correctly peeled, so we put the input flags back.

usage: 27_oskar_restore_flags.py input.ms peeled.ms
"""

import argparse

import numpy as np
from casacore.tables import table


def main():
    """Restore the input flags and weights."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ms_in")
    parser.add_argument("ms_out")
    args = parser.parse_args()

    src = table(args.ms_in, ack=False)
    dst = table(args.ms_out, readonly=False, ack=False)
    if src.nrows() != dst.nrows():
        raise SystemExit("row counts differ")
    before = dst.getcol("FLAG").mean()
    flag = src.getcol("FLAG")
    weight = src.getcol("WEIGHT")
    dst.putcol("FLAG", flag)
    dst.putcol("WEIGHT", weight)
    if "WEIGHT_SPECTRUM" in dst.colnames():
        spec = np.broadcast_to(weight[:, None, :], flag.shape) * ~flag
        dst.putcol("WEIGHT_SPECTRUM", spec.astype("f4"))
    dst.close()
    print(f"{args.ms_out}: flagged fraction {before:.4f} -> {flag.mean():.4f}")


if __name__ == "__main__":
    main()
