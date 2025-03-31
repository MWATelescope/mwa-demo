#!/usr/bin/env python

import json
import os
from argparse import ArgumentParser

import numpy as np


def sanitize_json(jstr):
    return jstr.replace("null", "NaN")


def get_parser():
    parser = ArgumentParser(description="render TEC plot for offsets.")

    parser.add_argument("--srclist", help="source list file (yaml)")
    parser.add_argument("--offsets", help="offset file (json|yaml)")
    parser.add_argument("--obsid", default=0, type=int)
    parser.add_argument(
        "--time-res", default=8, type=int, help="time resolution (seconds)"
    )
    parser.add_argument(
        "--time_offset",
        default=0,
        type=int,
        help="offset from obsid to first timestep (seconds)",
    )
    plot_group = parser.add_argument_group("OUTPUT OPTIONS")
    plot_group.add_argument("--reg", help="Name of output ds9 region", default=None)
    plot_group.add_argument(
        "--average", action="store_true", default=False, help="Average offsets together"
    )

    return parser


def main():
    parser = get_parser()

    args = parser.parse_args()

    ras = []
    decs = []
    src_names = []
    offsets_base, ext = os.path.splitext(args.offsets)
    if ext == ".json":
        with open(args.offsets) as h:
            iono_consts = json.loads(sanitize_json(h.read()))
        alphas = []
        betas = []
        for src_name, consts in iono_consts.items():
            pos = consts["weighted_catalogue_pos_j2000"]
            ras.append(pos["ra"])
            decs.append(pos["dec"])
            alphas.append(consts["alphas"])
            betas.append(consts["betas"])
            src_names.append(src_name)

        alphas = np.array(alphas)
        betas = np.array(betas)
        ras = np.array(ras)
        decs = np.array(decs)
        ras[np.where(ras > 180)] -= 360

    reg_file = f"{offsets_base}.reg"
    if args.reg is not None:
        reg_file = args.reg
    print(
        f"{ras, decs, src_names, alphas[:, args.time_offset], betas[:, args.time_offset]=}"
    )
    with open(reg_file, "w") as h:
        h.write("J2000;\n")
        for ra, dec, src_name, alpha, beta in zip(
            ras,
            decs,
            src_names,
            alphas[:, args.time_offset],
            betas[:, args.time_offset],
        ):
            angle = np.arctan2(beta, alpha) * 180 / np.pi
            length = np.sqrt(alpha**2 + beta**2)
            h.write(
                f"vector {ra}d {dec}d {length * 1000}d {angle}d # text={{{src_name}}}\n"
            )
    print(f"Wrote {reg_file}")


if __name__ == "__main__":
    main()
