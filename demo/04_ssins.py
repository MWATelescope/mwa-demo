#!/usr/bin/env python
from pyuvdata import UVData
from SSINS import SS, INS, MF
import os
import matplotlib as mpl
from matplotlib import pyplot as plt
import numpy as np
from astropy.time import Time
import argparse

from matplotlib.axis import Axis


def get_parser():
    parser = argparse.ArgumentParser()
    # arguments for UVData.read()
    group_uvd_read = parser.add_argument_group("UVData.read")
    group_uvd_read.add_argument("files", nargs="+")
    group_uvd_read.add_argument(
        "--no-diff",
        default=False,
        action="store_true",
        help="don't difference visibilities in time (sky-subtract)",
    )
    group_uvd_read.add_argument(
        "--no-flag-init",
        default=False,
        action="store_true",
        help="skip flagging of edge channels, quack time",
    )

    # arguments for UVData.select()
    group_uvd_sel = parser.add_argument_group("UVData.select")
    group_mutex = group_uvd_sel.add_mutually_exclusive_group()
    group_mutex.add_argument(
        "--sel-ants",
        default=[],
        nargs="*",
        type=str,
        help="antenna names to select, default: all unflagged",
    )
    group_mutex.add_argument(
        "--skip-ants",
        default=[],
        nargs="*",
        type=str,
        help="antenna names to skip, default: none",
    )

    group_uvd_sel.add_argument(
        "--sel-pols",
        default=[],
        nargs="*",
        type=str,
        help="polarizations to select, default: all",
    )

    # arguments for SSINS.INS
    parser.add_argument(
        "--spectrum-type",
        default="auto",
        choices=["auto", "cross"],
        help="analyse auto-correlations or cross-correlations. default: auto",
    )

    parser.add_argument(
        "--crosses",
        action="store_const",
        const="cross",
        dest="spectrum_type",
        help="shorthand for --spectrum-type=cross",
    )

    parser.add_argument(
        "--sigchain",
        default=False,
        action="store_true",
        help="analyse z-scores for each tile and sum",
    )

    # arguments for SSINS.MF
    parser.add_argument(
        "--threshold",
        default=5,
        type=float,
        help="match filter significance threshold. 0 disables match filter",
    )
    parser.add_argument(
        "--no-narrow",
        default=False,
        help="Don't look for narroband RFI",
    )

    # other

    parser.add_argument(
        "--suffix",
        default="",
        type=str,
        help="additional text to add to filename",
    )

    parser.add_argument("--fontsize", default=8, help="plot font size")
    return parser


def get_unflagged_ants(ss: UVData, args):
    all_ant_nums = np.array(ss.antenna_numbers)
    all_ant_names = np.array(ss.antenna_names)
    present_ant_nums = np.unique(ss.ant_1_array)
    present_ant_mask = np.where(np.isin(all_ant_nums, present_ant_nums))[0]
    present_ant_names = np.array([*map(str.upper, all_ant_names[present_ant_mask])])
    assert len(present_ant_nums) == len(present_ant_names)

    if args.sel_ants:
        sel_ants = np.array([*map(str.upper, args.sel_ants)])
        return present_ant_nums[np.where(np.isin(present_ant_names, sel_ants))[0]]
    elif args.skip_ants:
        skip_ants = np.array([*map(str.upper, args.skip_ants)])
        return present_ant_nums[np.where(~np.isin(present_ant_names, skip_ants))[0]]

    return present_ant_nums


def get_gps_times(uvd: UVData):
    return [*Time(np.unique(uvd.time_array), format="jd").gps]


def get_suffix(args):
    suffix = args.suffix
    suffix = f".{args.spectrum_type}{suffix}"
    if not args.no_diff:
        suffix = f".diff{suffix}"
    if len(args.sel_ants) == 1:
        suffix = f"{suffix}.{args.sel_ants[0]}"
    elif len(args.skip_ants) == 1:
        suffix = f"{suffix}.no{args.skip_ants[0]}"
    if len(args.sel_pols) == 1:
        suffix = f"{suffix}.{args.sel_pols[0]}"
    return suffix


def get_match_filter(ss, args):
    """
    https://ssins.readthedocs.io/en/latest/match_filter.html
    """
    return MF(ss.freq_array, args.threshold, streak=True, narrow=(not args.no_narrow))


# #### #
# PLOT #
# #### #


def plot_sigchain(ss, args, obsname, suffix, cmap):
    mf = get_match_filter(ss, args)

    unflagged_ants = get_unflagged_ants(ss, args)
    ant_mask = np.where(np.isin(ss.antenna_numbers, unflagged_ants))[0]
    ant_numbers = np.array(ss.antenna_numbers)[ant_mask]
    ant_names = np.array(ss.antenna_names)[ant_mask]
    pols = ss.get_pols()
    gps_times = get_gps_times(ss)
    freqs_mhz = (ss.freq_array) / 1e6

    # pad names
    name_len = max(len(name) for name in ant_names)
    ant_labels = [f"{name: <{name_len}}" for name in ant_names]

    # build a scores array for each signal chain
    scores = np.zeros((len(unflagged_ants), ss.Ntimes, ss.Nfreqs, ss.Npols))
    for ant_idx, (ant_num, ant_name) in enumerate(zip(ant_numbers, ant_names)):
        if ant_num not in unflagged_ants:
            continue
        # select only the auto-correlation for this antenna
        ssa = ss.select(antenna_nums=[(ant_num, ant_num)], inplace=False)
        ins = INS(ssa, spectrum_type=args.spectrum_type)
        mf.apply_match_test(ins)
        ins.sig_array[~np.isfinite(ins.sig_array)] = 0
        scores[ant_idx] = ins.sig_array

    subplots = plt.subplots(
        2,
        len(pols),
        height_ratios=[len(unflagged_ants), ss.Nfreqs],
    )[1].reshape((2, len(pols)))

    def slice(scores, axis):
        return np.sqrt(np.sum(scores**2, axis=axis))

    for i, pol in enumerate(pols):
        # by signal chain: [ant, time]
        ax_signal: Axis = subplots[0, i]
        ax_signal.set_title(f"{obsname} zscore{suffix} {pol if len(pols) > 1 else ''}")
        if i == 0:
            ax_signal.set_ylabel("Antenna")

        signal_pscore = slice(scores[..., i], axis=-1)

        ax_signal.imshow(
            signal_pscore,
            aspect="auto",
            interpolation="none",
            cmap=cmap,
            extent=[
                np.min(gps_times),
                np.max(gps_times),
                len(ant_labels) - 0.5,
                -0.5,
            ],
        )
        ax_signal.set_yticks(np.arange(len(unflagged_ants)))
        ax_signal.tick_params(pad=True)
        ax_signal.set_yticklabels(
            ant_labels, fontsize=args.fontsize, fontfamily="monospace"
        )

        # by spectrum: [freq, time]
        ax_spectrum: Axis = subplots[1, i]
        ax_spectrum.set_xlabel("GPS Time [s]")
        if i == 0:
            ax_spectrum.set_ylabel("Frequency channel [MHz]")

        spectrum_pscore = slice(scores[..., i].transpose(2, 1, 0), axis=-1)

        ax_spectrum.tick_params(pad=True)
        ax_spectrum.imshow(
            spectrum_pscore,
            aspect="auto",
            interpolation="none",
            cmap=cmap,
            extent=[
                np.min(gps_times),
                np.max(gps_times),
                np.max(freqs_mhz),
                np.min(freqs_mhz),
            ],
        )


def plot_spectrum(ss, args, obsname, suffix, cmap):
    # incoherent noise spectrum https://ssins.readthedocs.io/en/latest/incoherent_noise_spectrum.html
    ins = INS(ss, spectrum_type=args.spectrum_type)

    mf = get_match_filter(ss, args)
    mf.apply_match_test(ins)
    ins.sig_array[~np.isfinite(ins.sig_array)] = 0

    pols = ss.get_pols()
    gps_times = get_gps_times(ss)
    freqs_mhz = (ss.freq_array) / 1e6

    subplots = plt.subplots(
        2,
        len(pols),
        sharex=True,
        sharey=True,
    )[
        1
    ].reshape((2, len(pols)))

    for i, pol in enumerate(pols):
        # axis for metric being plotted
        ax_met: Axis = subplots[0, i]

        ax_met.set_title(f"{obsname} vis amps{suffix} {pol if len(pols) > 1 else ''}")
        ax_met.imshow(
            ins.metric_array[..., i],
            aspect="auto",
            interpolation="none",
            cmap=cmap,
            extent=[
                np.min(freqs_mhz),
                np.max(freqs_mhz),
                np.max(gps_times),
                np.min(gps_times),
            ],
        )

        # axis for significance
        ax_sig: Axis = subplots[1, i]
        ax_sig.set_title(f"{obsname} z-score{suffix} {pol if len(pols) > 1 else ''}")
        ax_sig.imshow(
            ins.sig_array[..., i],
            aspect="auto",
            interpolation="none",
            cmap=cmap,
            extent=[
                np.min(freqs_mhz),
                np.max(freqs_mhz),
                np.max(gps_times),
                np.min(gps_times),
            ],
        )
        if i == 0:
            ax_met.set_ylabel("GPS Time [s]")
            ax_sig.set_ylabel("GPS Time [s]")

        ax_sig.set_xlabel("Frequency channel [MHz]")


def main():
    parser = get_parser()
    args = parser.parse_args()
    print(f"{args=}")

    if len(args.files) > 1 and args.files[-1].endswith(".fits"):
        metafits = args.files[0]
        # output name is basename of metafits, or uvfits if provided
        base, _ = os.path.splitext(metafits)
    elif len(args.files) == 1:
        vis = args.files[-1]
        base, _ = os.path.splitext(vis)
    else:
        parser.print_usage()
        exit(1)

    print(f"reading from {args.files=}")
    # sky-subtract https://ssins.readthedocs.io/en/latest/sky_subtract.html
    ss = SS()
    ss.read(
        args.files,
        read_data=True,
        diff=(not args.no_diff),  # difference timesteps
        remove_coarse_band=False,  # does not work with low freq res
        correct_van_vleck=False,  # slow
        remove_flagged_ants=True,  # remove flagged antennas
        flag_init=(not args.no_flag_init),
    )

    unflagged_ants = get_unflagged_ants(ss, args)

    select_kwargs = {
        "inplace": False,
    }
    if args.spectrum_type == "cross":
        select_kwargs["bls"] = [
            (a, b)
            for (a, b) in ss.get_antpairs()
            if a != b and (b in unflagged_ants or a in unflagged_ants)
        ]
    else:
        select_kwargs["bls"] = [
            (a, b) for (a, b) in ss.get_antpairs() if a == b and a in unflagged_ants
        ]
    if args.sel_pols:
        select_kwargs["polarizations"] = args.sel_pols

    ss = ss.select(**select_kwargs)
    ss.apply_flags(flag_choice="original")

    plt.style.use("dark_background")
    cmap = mpl.colormaps.get_cmap("viridis")
    cmap.set_bad(color="#00000000")

    suffix = get_suffix(args)

    pols = ss.get_pols()
    obsname = base.split("/")[-1]
    plt.suptitle(f"{obsname}{suffix}")
    if args.sigchain:
        plot_sigchain(ss, args, obsname, suffix, cmap)
        plt.gcf().set_size_inches(
            8 * len(pols), (len(unflagged_ants) + ss.Nfreqs) * args.fontsize / 72
        )
        figname = f"{base}{suffix}.sigchain.png"
    else:
        plot_spectrum(ss, args, obsname, suffix, cmap)
        plt.gcf().set_size_inches(8 * len(pols), 16)
        figname = f"{base}{suffix}.spectrum.png"

    plt.savefig(figname, bbox_inches="tight")
    print(f"wrote {figname}")


if __name__ == "__main__":
    main()
