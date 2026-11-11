#!/usr/bin/env python
"""
Keep the noise-free visibilities, add thermal noise, and set the weights.

OSKAR writes the noise-free sky into DATA. This script copies it to a new
column TRUE_DATA (the "true sky" that the peeling metrics compare against),
then adds Gaussian noise to DATA with, per baseline (i, j), polarisation and
real/imaginary part,

    sigma_ij = sqrt(SEFD_i * SEFD_j) / sqrt(2 * channel_width * integration)

and writes SIGMA = sigma_ij and WEIGHT (and WEIGHT_SPECTRUM, if present) =
1 / sigma_ij^2, so that a joint image of AA2 and MWA baselines weights them
correctly. The station type comes from the number of elements in PHASED_ARRAY:
256 (AA2) or 16 (MWA tile).

With ``--flag-cross-array`` (case h, "incoherent") the baselines between an AA2
station and an MWA tile are flagged: the two arrays share a sky, a time and a
phase centre but are not cross-correlated.

usage: 24_oskar_noise.py vis/aa2_120s.ms [--flag-cross-array]
"""

import argparse

import numpy as np
from casacore.tables import makearrcoldesc, table

K_B = 1380.649  # Boltzmann's constant in Jy m^2 / K


def main():
    """Add noise (and flags) in place."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ms")
    parser.add_argument(
        "--aeff-tsys-aa2",
        type=float,
        default=0.75,
        help="AA2 station A_eff/T_sys at 150 MHz [m^2/K]",
    )
    parser.add_argument(
        "--aeff-tsys-mwa",
        type=float,
        default=0.086,
        help="MWA tile A_eff/T_sys at 150 MHz [m^2/K] (21.5 m^2 / 250 K)",
    )
    parser.add_argument("--flag-cross-array", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--rows-per-chunk", type=int, default=100_000)
    args = parser.parse_args()

    pa = table(f"{args.ms}/PHASED_ARRAY", ack=False)
    n_elem = np.array(
        [pa.getcell("ELEMENT_OFFSET", i).shape[-1] for i in range(pa.nrows())]
    )
    is_aa2 = n_elem > 16
    sefd = np.where(is_aa2, 2 * K_B / args.aeff_tsys_aa2, 2 * K_B / args.aeff_tsys_mwa)
    spw = table(f"{args.ms}/SPECTRAL_WINDOW", ack=False)
    chan_width = spw.getcol("CHAN_WIDTH")[0, 0]

    t = table(args.ms, readonly=False, ack=False)
    if "TRUE_DATA" in t.colnames():
        raise SystemExit("TRUE_DATA exists: noise was already added")
    dminfo = t.getdminfo("DATA")
    dminfo["NAME"] = "TiledTrueData"
    shape = t.getcoldesc("DATA")["shape"]
    t.addcols(makearrcoldesc("TRUE_DATA", 0j, valuetype="complex", shape=shape), dminfo)
    integration = t.getcell("EXPOSURE", 0)
    print(
        f"SEFD AA2 {2 * K_B / args.aeff_tsys_aa2:.0f} Jy, "
        f"MWA {2 * K_B / args.aeff_tsys_mwa:.0f} Jy; "
        f"{is_aa2.sum()} AA2 stations, {(~is_aa2).sum()} MWA tiles; "
        f"{chan_width / 1e3:.1f} kHz x {integration:.1f} s"
    )

    rng = np.random.default_rng(args.seed)
    n_flagged = 0
    for start in range(0, t.nrows(), args.rows_per_chunk):
        n = min(args.rows_per_chunk, t.nrows() - start)
        data = t.getcol("DATA", start, n)
        a1 = t.getcol("ANTENNA1", start, n)
        a2 = t.getcol("ANTENNA2", start, n)
        t.putcol("TRUE_DATA", data, start, n)
        sigma = np.sqrt(sefd[a1] * sefd[a2] / (2 * chan_width * integration))
        noise = rng.normal(size=data.shape) + 1j * rng.normal(size=data.shape)
        data = data + (sigma[:, None, None] * noise).astype(data.dtype)
        t.putcol("DATA", data, start, n)
        npol = data.shape[-1]
        t.putcol("SIGMA", np.repeat(sigma[:, None], npol, 1).astype("f4"), start, n)
        t.putcol(
            "WEIGHT", np.repeat(sigma[:, None] ** -2, npol, 1).astype("f4"), start, n
        )
        if args.flag_cross_array:
            cross = is_aa2[a1] != is_aa2[a2]
            flags = t.getcol("FLAG", start, n)
            flags[cross] = True
            t.putcol("FLAG", flags, start, n)
            t.putcol("FLAG_ROW", cross | t.getcol("FLAG_ROW", start, n), start, n)
            n_flagged += cross.sum()
        if "WEIGHT_SPECTRUM" in t.colnames():
            # e.g. after 23_oskar_concat.sh: wsclean prefers it over WEIGHT
            flags = t.getcol("FLAG", start, n)
            spec = np.broadcast_to(sigma[:, None, None] ** -2, flags.shape) * ~flags
            t.putcol("WEIGHT_SPECTRUM", spec.astype("f4"), start, n)
    t.close()
    if args.flag_cross_array:
        print(f"flagged {n_flagged} AA2 x MWA rows")
    print(f"added noise to {args.ms}")


if __name__ == "__main__":
    main()
