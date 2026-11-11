#!/usr/bin/env python
"""
Split one sub-array (a contiguous range of stations) out of an OSKAR MS.

OSKAR computes every baseline independently, so the AA2 x AA2 or MWA x MWA
baselines of the case (h) simulation are the same visibilities that an AA2-only
or MWA-only simulation of the same sky, screen and time would give. This copies
the rows whose two stations are both in ``[first, last]``, keeps the
ANTENNA, FEED and PHASED_ARRAY rows for those stations, and renumbers them
from 0.

usage: 23_oskar_split.py aa2_mwa256t_120s.ms mwa256t_120s.ms --first 68 --last 323
"""

import argparse
import shutil

from casacore.tables import table, taql


def main():
    """Copy the selected rows and subtables."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ms_in")
    parser.add_argument("ms_out")
    parser.add_argument("--first", type=int, required=True)
    parser.add_argument("--last", type=int, required=True)
    args = parser.parse_args()
    lo, hi = args.first, args.last

    shutil.rmtree(args.ms_out, ignore_errors=True)
    t = table(args.ms_in, ack=False)
    sel = taql(
        f"select from $t where ANTENNA1 >= {lo} && ANTENNA1 <= {hi}"
        f" && ANTENNA2 >= {lo} && ANTENNA2 <= {hi}"
    )
    sel.copy(args.ms_out, deep=True, valuecopy=True)
    sel.close()
    t.close()

    out = table(args.ms_out, readonly=False, ack=False)
    out.putcol("ANTENNA1", out.getcol("ANTENNA1") - lo)
    out.putcol("ANTENNA2", out.getcol("ANTENNA2") - lo)
    nrows = out.nrows()
    out.close()
    for sub, id_col in [
        ("ANTENNA", None),
        ("FEED", "ANTENNA_ID"),
        ("PHASED_ARRAY", "ANTENNA_ID"),
    ]:
        st = table(f"{args.ms_out}/{sub}", readonly=False, ack=False)
        keep = range(lo, hi + 1)
        st.removerows([i for i in range(st.nrows()) if i not in keep])
        if id_col:
            st.putcol(id_col, st.getcol(id_col) - lo)
        st.close()
    print(f"wrote {args.ms_out}: stations {lo}-{hi}, {nrows} rows")


if __name__ == "__main__":
    main()
