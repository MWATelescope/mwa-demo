#!/usr/bin/env python
"""
Undo the per-station feed rotation of SKA-Low stations in an OSKAR MS.

Each AA2 station is rotated on the ground, and OSKAR rotates its dipoles with
it (``FEED/RECEPTOR_ANGLE``). An unpolarised source then appears in XX and YY
scaled by cos(theta_i - theta_j) and leaks into XY/YX, differently on every
baseline. wsclean forms Stokes I as (XX + YY) / 2, so an AA2 image made from
the raw visibilities averages cos(theta_i - theta_j) over baselines and loses
most of the sky, and hyperdrive's sky-model prediction assumes all tiles share
one feed orientation (the MWA case). So before imaging and peeling we rotate
every station's feeds back to the common orientation:

    V'_ij = R(-theta_i) V_ij R(-theta_j)^T,  R(t) = [[cos t, -sin t],
                                                   [sin t,  cos t]]

with theta_i = RECEPTOR_ANGLE_X - 90 deg (0 for an unrotated MWA tile). The
transform is unitary per baseline, so visibility power, and hence the peeling
metrics, are the same in either frame. Within the station main lobe the
rotated dipole response is a rotation of the unrotated one, so this is exact
at the phase centre and a good approximation over the AA2 main lobe.

DATA and TRUE_DATA (if present) are rotated, in place or into a copy of the
MS, whose FEED/RECEPTOR_ANGLE and PHASED_ARRAY/COORDINATE_AXES then describe
unrotated stations (the element positions are unchanged), so that EveryBeam
models the derotated data too. Running it twice is harmless: the second time
every rotation is zero.

usage: 24_oskar_derotate.py in.ms [out.ms]
"""

import argparse
import shutil

import numpy as np
from casacore.tables import table


def rot(theta):
    """Return rotation matrices for an array of angles, shape (n, 2, 2)."""
    c, s = np.cos(theta), np.sin(theta)
    return np.stack([np.stack([c, -s], -1), np.stack([s, c], -1)], -2)


def main():
    """Rotate the visibilities of every station back to angle 0."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ms_in")
    parser.add_argument("ms_out", nargs="?", help="default: in place")
    parser.add_argument(
        "--sign",
        type=float,
        default=1.0,
        help="flip to -1 for the opposite rotation sense",
    )
    parser.add_argument("--rows-per-chunk", type=int, default=50_000)
    args = parser.parse_args()

    if args.ms_out and args.ms_out != args.ms_in:
        shutil.rmtree(args.ms_out, ignore_errors=True)
        shutil.copytree(args.ms_in, args.ms_out)
    else:
        args.ms_out = args.ms_in
    theta = table(f"{args.ms_out}/FEED", ack=False).getcol("RECEPTOR_ANGLE")[:, 0]
    theta = args.sign * (theta - np.pi / 2)
    print(
        f"feed rotations: {np.degrees(theta).min():.1f} to "
        f"{np.degrees(theta).max():.1f} deg"
    )
    r_inv = rot(-theta)

    # every station now has the feeds of an unrotated one
    feed = table(f"{args.ms_out}/FEED", readonly=False, ack=False)
    angles = feed.getcol("RECEPTOR_ANGLE")
    angles[:, 0], angles[:, 1] = np.pi / 2, 0.0
    feed.putcol("RECEPTOR_ANGLE", angles)
    feed.close()
    pa = table(f"{args.ms_out}/PHASED_ARRAY", readonly=False, ack=False)
    axes = pa.getcol("COORDINATE_AXES")
    for i, pos in enumerate(pa.getcol("POSITION")):
        # columns P, Q, R = local East, North, Up (geocentric normal is close
        # enough: the element offsets themselves are not changed)
        lon = np.arctan2(pos[1], pos[0])
        lat = np.arctan2(pos[2], np.hypot(pos[0], pos[1]) * (1 - 0.00669438))
        east = [-np.sin(lon), np.cos(lon), 0.0]
        north = [-np.sin(lat) * np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat)]
        up = [np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)]
        # python-casacore returns OSKAR's row-major pqr_to_ecef transposed
        axes[i] = np.array([east, north, up])
    pa.putcol("COORDINATE_AXES", axes)
    pa.close()

    t = table(args.ms_out, readonly=False, ack=False)
    cols = [c for c in ("DATA", "TRUE_DATA") if c in t.colnames()]
    for start in range(0, t.nrows(), args.rows_per_chunk):
        n = min(args.rows_per_chunk, t.nrows() - start)
        a1 = t.getcol("ANTENNA1", start, n)
        a2 = t.getcol("ANTENNA2", start, n)
        for col in cols:
            v = t.getcol(col, start, n)
            shape = v.shape
            v = v.reshape(n, shape[1], 2, 2)
            v = np.einsum("bij,bfjk,blk->bfil", r_inv[a1], v, r_inv[a2])
            t.putcol(col, v.reshape(shape).astype(np.complex64), start, n)
    t.close()
    print(f"wrote {args.ms_out} ({', '.join(cols)} derotated)")


if __name__ == "__main__":
    main()
