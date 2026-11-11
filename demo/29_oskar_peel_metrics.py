#!/usr/bin/env python
"""
Measure how much of the simulated sky a subtraction model peeled.

Compares, baseline by baseline, three sets of visibilities:

- D: the data that went into peeling (sky + noise), ``DATA`` of ``--input``
- S: the true sky that was simulated (no noise), ``TRUE_DATA`` of ``--input``
- R: the residual after peeling, ``--column`` of ``--residual``

The model that was actually subtracted is M = D - R. Powers are sums of
|V|^2 over all unflagged cross-correlations, channels and the four
polarisations (so they do not depend on the feed frame), and

- ``peeled_true``  = 1 - |S - M|^2 / |S|^2 : fraction of the true sky's power
  removed; 1 is perfect, it drops for missing sources and for model errors
  (positions, fluxes, beam, ionosphere), and is negative if the subtraction
  adds more power than it removes
- ``model_true``   = |M|^2 / |S|^2 : power of the subtracted model
- ``peeled_data``  = 1 - |R|^2 / |D|^2 : what an observer sees, including noise
- ``noise_data``   = |D - S|^2 / |D|^2 : the noise share of the data power

If the residual was written in the conjugate baseline convention it is
conjugated first (whichever gives the smaller |D - R|).

usage: 29_oskar_peel_metrics.py --input aa2_120s_derot.ms \
           --residual peel/hyp_peel_aa2_120s.ms --label hyperdrive --json out.json
"""

import argparse
import json

import numpy as np
from casacore.tables import table


def image_stats(paths):
    """Print a markdown table of image-plane statistics."""
    from astropy.io import fits

    print("| image | robust rms (mJy/beam) | peak (Jy/beam) | min (Jy/beam) |")
    print("|---|---|---|---|")
    for path in paths:
        data = np.squeeze(fits.getdata(path))
        ny, nx = data.shape
        centre = data[ny // 3 : 2 * ny // 3, nx // 3 : 2 * nx // 3]
        rms = 1.4826 * np.median(np.abs(centre - np.median(centre)))
        print(
            f"| {path.split('/')[-1]} | {1e3 * rms:.2f} | {centre.max():.3f} |"
            f" {centre.min():.3f} |"
        )


def summarise(paths):
    """Print a markdown table, adding up powers of runs that share a label."""
    groups = {}
    for path in paths:
        with open(path) as f:
            m = json.load(f)
        groups.setdefault(m["label"].split(" [")[0], []).append(m)
    print(
        "| run | true-sky power peeled | model / true | data power peeled |"
        " noise share of data |"
    )
    print("|---|---|---|---|---|")
    rows = []
    for label, ms in groups.items():
        if len(ms) > 1:
            rows += [(m["label"], [m]) for m in ms]
        rows.append((label + (" [combined]" if len(ms) > 1 else ""), ms))
    for label, ms in rows:
        s = sum(m["power_true"] for m in ms)
        d = sum(m["power_data"] for m in ms)
        smm = sum((1 - m["peeled_true"]) * m["power_true"] for m in ms)
        mod = sum(m["model_true"] * m["power_true"] for m in ms)
        r = sum(m["power_residual"] for m in ms)
        n = sum(m["noise_data"] * m["power_data"] for m in ms)
        print(
            f"| {label} | {1 - smm / s:.4f} | {mod / s:.4f} | {1 - r / d:.4f} |"
            f" {n / d:.4f} |"
        )


def main():
    """Accumulate the powers chunk by chunk and print/write the metrics."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--input")
    parser.add_argument("--residual")
    parser.add_argument("--column", default="DATA")
    parser.add_argument("--label", default="")
    parser.add_argument("--json")
    parser.add_argument("--rows-per-chunk", type=int, default=50_000)
    parser.add_argument(
        "--summary",
        nargs="+",
        metavar="JSON",
        help="instead, tabulate metrics JSON files; files with the same label"
        " up to a ' [part]' suffix (the two halves of case h) are combined",
    )
    parser.add_argument(
        "--image-stats",
        nargs="+",
        metavar="FITS",
        help="instead, print the robust rms, peak and minimum within the central"
        " facet (the middle third) of these images",
    )
    args = parser.parse_args()
    if args.summary:
        summarise(args.summary)
        return
    if args.image_stats:
        image_stats(args.image_stats)
        return

    ti = table(args.input, ack=False)
    tr = table(args.residual, ack=False)
    if ti.nrows() != tr.nrows():
        raise SystemExit(f"row counts differ: {ti.nrows()} vs {tr.nrows()}")
    acc = dict.fromkeys(
        ["D", "S", "R", "N", "SmM", "SmMc", "M", "Mc", "DmR", "DmRc"], 0.0
    )
    for start in range(0, ti.nrows(), args.rows_per_chunk):
        n = min(args.rows_per_chunk, ti.nrows() - start)
        for col in ("ANTENNA1", "ANTENNA2"):
            if not np.array_equal(ti.getcol(col, start, n), tr.getcol(col, start, n)):
                raise SystemExit(f"{col} differs between input and residual")
        if not np.allclose(ti.getcol("TIME", start, n), tr.getcol("TIME", start, n)):
            raise SystemExit("TIME differs between input and residual")
        d = ti.getcol("DATA", start, n)
        s = ti.getcol("TRUE_DATA", start, n)
        r = tr.getcol(args.column, start, n)
        good = ~(ti.getcol("FLAG", start, n) | tr.getcol("FLAG", start, n))
        good &= (ti.getcol("ANTENNA1", start, n) != ti.getcol("ANTENNA2", start, n))[
            :, None, None
        ]
        d, s, r = d[good], s[good], r[good]
        acc["DmR"] += float(np.sum(np.abs(d - r) ** 2))
        acc["DmRc"] += float(np.sum(np.abs(d - np.conj(r)) ** 2))
        acc["D"] += float(np.sum(np.abs(d) ** 2))
        acc["S"] += float(np.sum(np.abs(s) ** 2))
        acc["N"] += float(np.sum(np.abs(d - s) ** 2))
        # keep both conventions until we know which one applies
        acc["R"] += float(np.sum(np.abs(r) ** 2))
        acc["SmM"] += float(np.sum(np.abs(s - (d - r)) ** 2))
        acc["SmMc"] += float(np.sum(np.abs(s - (d - np.conj(r))) ** 2))
        acc["Mc"] += float(np.sum(np.abs(d - np.conj(r)) ** 2))
    conj = acc["DmRc"] < acc["DmR"]
    smm = acc["SmMc"] if conj else acc["SmM"]
    m = acc["Mc"] if conj else acc["DmR"]
    out = {
        "label": args.label,
        "input": args.input,
        "residual": args.residual,
        "residual_conjugated": bool(conj),
        "power_data": acc["D"],
        "power_true": acc["S"],
        "power_residual": acc["R"],
        "peeled_true": 1 - smm / acc["S"],
        "model_true": m / acc["S"],
        "peeled_data": 1 - acc["R"] / acc["D"],
        "noise_data": acc["N"] / acc["D"],
    }
    print(
        f"{args.label:>12}: peeled_true {out['peeled_true']:.4f}  "
        f"model_true {out['model_true']:.4f}  peeled_data {out['peeled_data']:.4f}  "
        f"noise_data {out['noise_data']:.4f}  conj {conj}"
    )
    if args.json:
        with open(args.json, "w") as f:
            json.dump(out, f, indent=2)


if __name__ == "__main__":
    main()
