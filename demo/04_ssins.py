#!/usr/bin/env python

"""
Identifies RFI using SSINS.

Supports various file formats such as .fits, .uvfits, .uvh5, and .ms,
and provides options for plotting and exporting results.
"""

# identify RFI using ssins
# details: https://github.com/mwilensky768/SSINS
# takes any format supported by pyuvdata https://github.com/RadioAstronomySoftwareGroup/pyuvdata
# although measurement set support is not as good as uvfits or uvh5

# tip: you can use this script to apply the ssins mask:
# https://raw.githubusercontent.com/MWATelescope/MWAEoR-Pipeline/refs/heads/main/templates/ssins_apply.py

import os
import re
import sys
import time
import traceback
from argparse import SUPPRESS, ArgumentParser, BooleanOptionalAction
from itertools import chain, groupby
from os.path import basename, dirname, splitext
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pandas as pd
from astropy import units as u
from astropy.time import Time
from matplotlib import pyplot as plt
from matplotlib.axis import Axis
from pyuvdata import UVData

# from SSINS import EAVILS_INS as INS
from SSINS import INS, MF, SS


def get_parser_common(diff=True, spectrum="cross"):
    """Parser for read and select (common)."""
    parser = ArgumentParser()
    # arguments for SS.read()
    group_read = parser.add_argument_group("SS.read")
    group_read.add_argument(
        "files",
        nargs="+",
        help="Raw .fits (with .metafits), .uvfits, .uvh5, .ms supported",
    )
    group_read.add_argument(
        "--diff",
        default=diff,
        help=f"Difference visibilities in time (sky-subtract). default: {diff}",
        action=BooleanOptionalAction,
    )
    group_read.add_argument(
        "--flag-init",
        default=True,
        help="Flagging of quack time, edge channels, default: True",
        action=BooleanOptionalAction,
    )
    group_read.add_argument(
        "--remove-coarse-band",
        default=False,
        action="store_true",
        help="Correct coarse PFB passband (resolution must be > 10kHz)",
    )
    group_read.add_argument(
        "--correct-van-vleck",
        default=False,
        action="store_true",
        help="Correct van vleck quantization artifacts in legacy correlator. slow!",
    )
    group_mutex = group_read.add_mutually_exclusive_group()
    group_mutex.add_argument("--remove-flagged-ants", default=True, help=SUPPRESS)
    group_mutex.add_argument(
        "--include-flagged-ants",
        action="store_false",
        dest="remove_flagged_ants",
        help="Include flagged antenna when reading raw files",
    )
    group_read.add_argument(
        "--flag-choice",
        default=None,
        choices=["original"],
        type=str,
        help=(
            "original = apply flags from visibilities before running ssins "
            "(only recommended for --plot-type=flags)"
        ),
    )

    # arguments for SS.select()
    group_sel = parser.add_argument_group("SS.select")
    group_mutex = group_sel.add_mutually_exclusive_group()
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
    group_mutex.add_argument(
        "--sel-rxs",
        default=[],
        nargs="*",
        type=str,
        help="receiver numbers to select, default: all",
    )
    group_mutex.add_argument(
        "--skip-rxs",
        default=[],
        nargs="*",
        type=str,
        help="receiver numbers to skip, default: none",
    )

    group_sel.add_argument(
        "--sel-pols",
        default=[],
        nargs="*",
        type=str,
        help="polarizations to select, default: all",
    )

    group_sel.add_argument(
        "--freq-range",
        default=None,
        nargs=2,
        metavar="Hz",
        help="frequency start and end [Hz] to filter on, default: all",
    )

    group_sel.add_argument(
        "--time-limit",
        default=None,
        type=int,
        metavar="N",
        help="limit to reading N times, default: all",
    )

    # common
    parser.add_argument(
        "--suffix",
        default="",
        type=str,
        help="additional text to add to output filenames",
    )
    parser.add_argument(
        "--debug",
        default=True,
        help="Extra debugging information in plot",
        action=BooleanOptionalAction,
    )

    group_plot = parser.add_argument_group("plotting")
    group_plot.add_argument(
        "--cmap",
        default="viridis",
        help="matplotlib.colormaps.get_cmap, default: viridis",
    )

    # arguments for SSINS.INS
    group_ins = parser.add_argument_group("SSINS.INS")
    group_ins.add_argument(
        "--order",
        default=0,
        type=int,
        help=("order of polynomial fit for each frequency channel"
              " during mean-subtraction."),
    )
    group_ins.add_argument(
        "--spectrum-type",
        default=spectrum,
        choices=["all", "auto", "cross"],
        help=f"analyse auto-correlations or cross-correlations. default: {spectrum}",
    )
    group_ins.add_argument(
        "--all",
        action="store_const",
        const="all",
        dest="spectrum_type",
        help="shorthand for --spectrum-type=all",
    )
    group_ins.add_argument(
        "--crosses",
        action="store_const",
        const="cross",
        dest="spectrum_type",
        help="shorthand for --spectrum-type=cross",
    )
    group_ins.add_argument(
        "--autos",
        action="store_const",
        const="auto",
        dest="spectrum_type",
        help="shorthand for --spectrum-type=auto",
    )
    return parser


def get_parser():
    """Parser ssins specific arguments."""
    parser = get_parser_common(diff=True)

    # arguments for SSINS.MF
    group_mf = parser.add_argument_group("SSINS.MF")
    group_mf.add_argument(
        "--threshold",
        default=5,
        type=float,
        help=(
            "match filter significance threshold for shapes except narrow and streak. "
            "0=disable"
        ),
    )
    group_mutex = group_mf.add_mutually_exclusive_group()
    group_mutex.add_argument(
        "--narrow",
        default=7,
        type=float,
        help="match filter significance threshold for narrowband RFI. 0=disable",
    )
    group_mutex.add_argument(
        "--no-narrow",
        action="store_const",
        dest="narrow",
        const=0,
        help="Don't look for narrowband RFI",
    )
    group_mutex = group_mf.add_mutually_exclusive_group()
    group_mutex.add_argument(
        "--streak",
        default=8,
        type=float,
        help="match filter significance threshold for streak RFI. 0=disable",
    )
    group_mutex.add_argument(
        "--no-streak",
        action="store_const",
        dest="streak",
        const=0,
        help="Don't look for streak RFI",
    )
    group_mf.add_argument(
        "--tb-aggro",
        default=0.6,
        type=float,
        help=(
            "Threshold for flagging an entire channel, "
            "fraction of unflagged data remaining. "
            "0=disable time broadcast"
        ),
    )

    # plotting
    group_plot = parser.add_argument_group("plotting")
    group_plot.add_argument(
        "--plot-type", default="spectrum", choices=["spectrum", "sigchain", "flags"]
    )
    group_plot.add_argument(
        "--spectrum",
        action="store_const",
        const="spectrum",
        dest="plot_type",
        help="analyse incoherent noise spectrum",
    )
    group_plot.add_argument(
        "--sigchain",
        action="store_const",
        const="sigchain",
        dest="plot_type",
        help="analyse z-scores for each tile and sum",
    )
    group_plot.add_argument(
        "--flags",
        action="store_const",
        const="flags",
        dest="plot_type",
        help="analyse flag occupancy",
    )

    group_plot.add_argument("--fontsize", default=8, help="plot tick label font size")

    parser.add_argument(
        "--export-tsv", default=False, action="store_true", help="export values to TSV"
    )

    return parser


def group_by_filetype(paths):
    """Given paths, group them by filetype."""

    def filetype_classifier(path):
        _, ext = splitext(path)
        return ext

    return {
        k: [*v]
        for k, v in groupby(
            sorted(paths, key=filetype_classifier), key=filetype_classifier
        )
    }


def file_group_by_obsid(groups):
    """Given a group of paths, group them by obsid."""

    def obsid_classifier(path):
        return splitext(basename(path))[0].split("_")[0]

    return {
        k: group_by_filetype(v)
        for k, v in groupby(
            sorted(chain(*groups.values()), key=obsid_classifier), key=obsid_classifier
        )
    }


def group_raw_by_channel(metafits, raw_fits):
    """Given metafits and raw_fits, group them by channel."""
    __import__("sys").path.insert(0, dirname(__file__))
    mwalib_tools = __import__("03_mwalib")

    if isinstance(metafits, str):
        metafits = [metafits]
    df_ch = None
    for mf in metafits:
        ctx = mwalib_tools.MetafitsContext(mf)
        if df_ch is None:
            df_ch = mwalib_tools.get_channel_df(ctx)
        else:
            df_ch_ = mwalib_tools.get_channel_df(ctx)
            assert df_ch.equals(df_ch_)

    def channel_classifier(path):
        ch_token = path.split("_")[-2]
        if match := re.match(r"gpubox(\d+)", ch_token):
            channel = df_ch[df_ch["gpubox_number"] == int(match[1])]
            if len(channel) == 0:
                raise UserWarning(f"no match of gpubox{match[1]} in {df_ch}")
            return int(channel.rec_chan_number.iloc[0])
        elif match := re.match(r"ch(\d+)", ch_token):
            return match[1]
        else:
            raise UserWarning(f"unknown channel token {ch_token}")

    return {
        k: sorted([*v])
        for k, v in groupby(
            sorted(raw_fits, key=channel_classifier), key=channel_classifier
        )
    }


def mwalib_get_common_times(metafits, raw_fits, good=True):
    """
    Get times that are common to all channels in raw fits.

    Optionally only return good times.
    """
    from mwalib import CorrelatorContext

    def get_indices(ctx: CorrelatorContext):
        return ctx.common_good_timestep_indices if good else ctx.common_timestep_indices

    gps_times = []
    # check if metafits is a string or a list
    if isinstance(metafits, str):
        metafits = [metafits]
    fg_by_id = file_group_by_obsid(group_by_filetype([*metafits, *raw_fits]))
    for obsid, obs_groups in fg_by_id.items():
        if ".fits" not in obs_groups or ".metafits" not in obs_groups:
            raise UserWarning(
                f"obsid {obsid} has no metafits or fits files in {obs_groups}"
            )
        metafits_, raw_fits = obs_groups[".metafits"][0], obs_groups[".fits"]
        with CorrelatorContext(metafits_, raw_fits) as corr_ctx:
            for time_idx in get_indices(corr_ctx):
                gps_times.append(corr_ctx.timesteps[time_idx].gps_time_ms / 1000.0)
    times = Time(gps_times, format="gps", scale="utc")
    int_time = np.median(np.diff(times.gps.astype(float)))
    times += (int_time / 2.0) * u.s
    return times


def get_unflagged_ants(ss: UVData, args):
    """
    Get antenna numbers of all unflagged antennas.

    if args.sel_rxs or skip_rxs provided, gets rx numbers from metafits.
    """
    all_ant_nums = np.array(ss.antenna_numbers)
    all_ant_names = np.array(ss.antenna_names)
    present_ant_nums = np.unique(ss.ant_1_array)
    present_ant_mask = np.where(np.isin(all_ant_nums, present_ant_nums))[0]

    def sanitize(s: str):
        return s.upper().strip()

    present_ant_names = np.array([*map(sanitize, all_ant_names[present_ant_mask])])
    assert len(present_ant_nums) == len(present_ant_names)

    if args.sel_ants:
        sel_ants = np.array([*map(sanitize, args.sel_ants)])
        if not set(present_ant_names).intersection(sel_ants):
            print(f"no intersection between {sel_ants=} and {present_ant_names=}")
        return present_ant_nums[np.where(np.isin(present_ant_names, sel_ants))[0]]
    elif args.skip_ants:
        skip_ants = np.array([*map(sanitize, args.skip_ants)])
        return present_ant_nums[np.where(~np.isin(present_ant_names, skip_ants))[0]]
    elif args.sel_rxs or args.skip_rxs:
        __import__("sys").path.insert(0, dirname(__file__))
        mwalib_tools = __import__("03_mwalib")
        metafits = group_by_filetype(args.files)[".metafits"]
        if len(metafits) == 0:
            raise UserWarning("can't determine rx numbers without metafits")
        df_ant = None
        for mf in metafits if isinstance(metafits, list) else [metafits]:
            ctx = mwalib_tools.MetafitsContext(mf)
            if df_ant is None:
                df_ant = mwalib_tools.get_antenna_df(ctx)
            else:
                df_ant_ = mwalib_tools.get_antenna_df(ctx)
                assert df_ant.equals(df_ant_)
        present_rx_nums = np.array(
            [*map(int, df_ant.rec_number[df_ant.tile_id.isin(present_ant_nums)])]
        )
        if args.sel_rxs:
            sel_rxs = np.array([*map(int, args.sel_rxs)])
            if not set(sel_rxs).issubset(df_ant.rec_number):
                print(f"no intersection between {sel_rxs=} and {df_ant.rec_number=}")
            return present_ant_nums[np.where(np.isin(present_rx_nums, sel_rxs))[0]]
        elif args.skip_rxs:
            skip_rxs = np.array([*map(int, args.skip_rxs)])
            if not set(skip_rxs).issubset(df_ant.rec_number):
                print(f"no intersection between {skip_rxs=} and {df_ant.rec_number=}")
            return present_ant_nums[np.where(~np.isin(present_rx_nums, skip_rxs))[0]]

    return present_ant_nums


def get_gps_times(uvd: UVData):
    """Get GPS times of all times in uvd.time_array."""
    return [*Time(np.unique(uvd.time_array), format="jd").gps]


def get_suffix(args):
    """Get suffix for output files based on arguments."""
    suffix = args.suffix
    if "spectrum_type" in vars(args) and args.spectrum_type != "all":
        suffix = f".{args.spectrum_type}{suffix}"
    if args.diff:
        suffix = f".diff{suffix}"
    if len(args.sel_ants) == 1:
        suffix += f".{args.sel_ants[0]}"
    elif len(args.skip_ants) == 1:
        suffix += f".no{args.skip_ants[0]}"
    if len(args.sel_rxs) == 1:
        suffix += f".rx{args.sel_rxs[0]}"
    elif len(args.skip_rxs) == 1:
        suffix += f".norx{args.skip_rxs[0]}"
    if len(args.sel_pols) == 1:
        suffix += f".{args.sel_pols[0]}"
    return suffix


def get_match_filter(freq_array, args):
    """https://ssins.readthedocs.io/en/latest/match_filter.html."""
    # guard width is half the fine channel width
    gw = np.median(np.diff(freq_array)) / 2
    shape_dict = {
        # from https://www.acma.gov.au/sites/default/files/2024-09/General%20Information.pdf
        "TV-6": [174e6 - gw, 181e6 + gw],
        "TV-7": [181e6 - gw, 188e6 + gw],
        "TV-8": [188e6 - gw, 195e6 + gw],
        "TV-9": [195e6 - gw, 202e6 + gw],
        "TV-9A": [202e6 - gw, 209e6 + gw],
        "TV-10": [209e6 - gw, 216e6 + gw],
        "TV-11": [216e6 - gw, 223e6 + gw],
        "TV-12": [223e6 - gw, 230e6 + gw],
        # starlink
        "SL-175": [174.997e6 - gw, 175.003e6 + gw],  # 3kHz doppler shift
    }
    sig_thresh = dict.fromkeys(shape_dict, args.threshold)
    mf_args = {"streak": (args.streak > 0), "narrow": (args.narrow > 0)}
    if mf_args["narrow"]:
        sig_thresh["narrow"] = args.narrow
    if mf_args["streak"]:
        sig_thresh["streak"] = args.streak
    if args.tb_aggro > 0:
        mf_args["tb_aggro"] = args.tb_aggro
    return MF(
        freq_array=freq_array, sig_thresh=sig_thresh, shape_dict=shape_dict, **mf_args
    )


def preapply_flags(ss: SS, ins: INS, args):
    """
    Optionally Apply flags to INS based on SS before MF if flag_choice is original.

    set the INS sig_array and metric_array to nan
    where ss.flag_array is True for all baselines
    or sig_array is not finite
    """
    if args.flag_choice == "original":
        flag_array = ss.flag_array.reshape(ss.Nbls, ss.Ntimes, ss.Nfreqs, ss.Npols)
        all_flagged = np.all(flag_array, axis=0)
        ins.sig_array[all_flagged] = np.nan
        ins.metric_array[all_flagged] = np.nan
        ins.sig_array[~np.isfinite(ins.sig_array)] = np.nan
        ins.metric_array[~np.isfinite(ins.sig_array)] = np.nan


def apply_match_test(mf: MF, ins: INS, args):
    """Use ins.apply_match_test() to apply the match filter."""
    match_test_args = {}
    if args.tb_aggro > 0:
        match_test_args["time_broadcast"] = True
    mf.apply_match_test(ins, **match_test_args)


# #### #
# PLOT #
# #### #
def plot_sigchain(ss, args, obsname, suffix, cmap):
    """Plot signal chain z-scores."""
    mf = get_match_filter(ss.freq_array, args)
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
    for ant_idx, (ant_num, _) in enumerate(zip(ant_numbers, ant_names)):
        if ant_num not in unflagged_ants:
            continue
        # select only baselines or autos with this antenna
        ssa = ss.select(ant_str=f"{ant_num}", inplace=False)
        with np.errstate(invalid="ignore"):
            ins = INS(ssa, spectrum_type=args.spectrum_type, order=args.order)
        preapply_flags(ssa, ins, args)
        apply_match_test(mf, ins, args)
        scores[ant_idx] = ins.sig_array

    subplots = plt.subplots(
        2, len(pols), height_ratios=[len(unflagged_ants), ss.Nfreqs]
    )[1].reshape((2, len(pols)))

    def slice_(scores, axis):
        return np.sqrt(np.nansum(scores**2, axis=axis))

    for i, pol in enumerate(pols):
        # by signal chain: [ant, time]
        ax_signal: Axis = subplots[0, i]
        ax_signal.set_title(f"{obsname} zscore{suffix} {pol if len(pols) > 1 else ''}")
        if i == 0:
            try:
                ax_signal.yaxis.set_label("Antenna")
            except RuntimeError as e:
                print(f"WARN: matplotlib breaking api change: {e}")

        signal_pscore = slice_(scores[..., i], axis=-1)
        signal_pscore[signal_pscore == 0] = np.nan

        ax_signal.imshow(
            signal_pscore,
            aspect="auto",
            interpolation="none",
            cmap=cmap,
            extent=[np.min(gps_times), np.max(gps_times), len(ant_labels) - 0.5, -0.5],
        )

        try:
            ax_signal.yaxis.set_ticks(np.arange(len(unflagged_ants)))
            ax_signal.yaxis.set_tick_params(pad=True)
            ax_signal.yaxis.set_ticklabels(
                ant_labels, fontsize=args.fontsize, fontfamily="monospace"
            )
        except RuntimeError as e:
            print(f"WARN: matplotlib breaking api change: {e}")

        # by spectrum: [freq, time]
        ax_spectrum: Axis = subplots[1, i]
        try:
            ax_spectrum.xaxis.set_label("GPS Time [s]")
            if i == 0:
                ax_spectrum.yaxis.set_label("Frequency channel [MHz]")
        except RuntimeError as e:
            print(f"WARN: matplotlib breaking api change: {e}")

        spectrum_pscore = slice_(scores[..., i].transpose(2, 1, 0), axis=-1)
        spectrum_pscore[spectrum_pscore == 0] = np.nan

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

    plt.gcf().set_size_inches(
        8 * len(pols), (np.min([
            ((len(unflagged_ants) + ss.Nfreqs) * args.fontsize / 72),
            ((2 ** 15) / 300),
        ]))
    )


def plot_spectrum(ss, args, obsname, suffix, cmap):
    """Plot the spectrum z-scores."""
    # incoherent noise spectrum https://ssins.readthedocs.io/en/latest/incoherent_noise_spectrum.html
    mf = get_match_filter(ss.freq_array, args)
    with np.errstate(invalid="ignore"):
        ins = INS(ss, spectrum_type=args.spectrum_type, order=args.order)
    apply_match_test(mf, ins, args)
    pols = ss.get_pols()

    gps_times = get_gps_times(ss)
    freqs_mhz = (ss.freq_array) / 1e6
    channames = [f"{ch: 8.4f}" for ch in freqs_mhz]

    subplots = plt.subplots(2, len(pols), sharex=True, sharey=True)[1]
    subplots = subplots.reshape((2, len(pols)))

    for i, pol in enumerate(pols):
        ax_mets = [
            ("vis_amps", ins.metric_array[..., i]),
            ("z_score", ins.sig_array[..., i]),
        ]

        for a, (name, metric) in enumerate(ax_mets):
            ax: Axis = subplots[a, i]
            ax.set_title(f"{obsname} {name}{suffix} {pol if len(pols) > 1 else ''}")
            ax.imshow(
                metric,
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
                ax.set_ylabel("GPS Time [s]")

            if a == len(ax_mets) - 1:
                ax.set_xlabel("Frequency channel [MHz]")

            if args.export_tsv:
                df = pd.DataFrame(metric, columns=channames, index=gps_times)
                df.to_csv(
                    p := f"{obsname}.{name}{suffix}.{pol}.tsv",
                    index_label="gps_time",
                    float_format="%.3f",
                    sep="\t",
                )
                print(p)

    plt.gcf().set_size_inches(8 * len(pols), 16)

    return ins


def plot_flags(ss: UVData, args, obsname, suffix, cmap):
    """Plot the flag occupancy."""
    pols = ss.get_pols()
    gps_times = get_gps_times(ss)
    freqs_mhz = (ss.freq_array) / 1e6

    occupancy = np.nansum(
        ss.flag_array.reshape(ss.Ntimes, ss.Nbls, ss.Nspws, ss.Nfreqs, len(pols)),
        axis=(1, 2, 4),
    ).astype(np.float64)
    full_occupancy_value = ss.Nbls * ss.Nspws * len(pols)
    occupancy[occupancy == full_occupancy_value] = np.nan
    max_occupancy = np.nanmax(occupancy)
    print(f"{max_occupancy=} {full_occupancy_value=}")
    # clip at half occupancy
    # occupancy[occupancy >= full_occupancy_value / 2] = full_occupancy_value / 2

    occupancy /= full_occupancy_value

    plt.suptitle(f"{obsname} occupancy{suffix} {pols[0] if len(pols) == 1 else ''}")
    plt.imshow(
        occupancy[...],
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

    # add a color bar
    cbar = plt.colorbar()
    cbar.set_label("Flag occupancy")

    plt.ylabel("GPS Time [s]")
    plt.xlabel("Frequency channel [MHz]")

    plt.gcf().set_size_inches(16, np.min([9, 4 * len(pols)]))


def du_bs(path: Path, bs=1024 * 1024):
    """Get disk usage from stat in number of blocks of a given size."""
    if path.is_file():
        return path.stat().st_size / bs
    return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file()) / bs


def display_time(t: Time):
    """Display the iso time, gps, unix and jd all on a single line."""
    return f"({t.isot} gps={t.gps:13.2f} unix={t.unix:13.2f} jd={t.jd:14.6f})"


def compare_time(ta: Time, tb: Time):
    """Smallest mwax resolution is 0.25s."""
    return np.abs(ta.gps - tb.gps) < 0.25


def compare_channel_times(segment, common_times, channel_times, time_descriptor=""):
    """Compare the overlap between two sets of times."""
    print(
        f"{segment} - found {len(channel_times)}{time_descriptor} times "
        f"from {display_time(channel_times[0])} to {display_time(channel_times[-1])}"
    )
    if not compare_time(channel_times[0], common_times[0]):
        print(
            f"WARN: {segment} - starts at {display_time(channel_times[0])} "
            f"but common is {display_time(common_times[0])}"
        )
    if not compare_time(channel_times[-1], common_times[-1]):
        print(
            f"WARN: {segment} - ends at   {display_time(channel_times[-1])} "
            f"but common is {display_time(common_times[-1])}"
        )


def read_raw(uvd: UVData, metafits, raw_fits, read_kwargs):
    """Read raw files into uvd one channel at a time."""
    file_sizes_mb = {f: du_bs(Path(f)) for f in raw_fits}
    total_size_mb = sum(file_sizes_mb.values())
    print(f"reading {int(total_size_mb)}MB of raw files")

    start = time.time()
    if len(raw_fits) <= 1:
        uvd.read([metafits, *raw_fits], read_data=True, **read_kwargs)
        read_time = time.time() - start
        print(f"read took {int(read_time)}s. {int(total_size_mb / read_time)} MB/s")
        return uvd

    # group and read raw by channel to save memory
    raw_channel_groups = group_raw_by_channel(metafits, raw_fits)
    # channels not always aligned in time
    good = False
    times = mwalib_get_common_times(metafits, raw_fits, good)
    time_array = times.jd.astype(float)
    good_descriptor = " good" if good else ""
    print(
        f"mwalib found {len(times)}{good_descriptor}  "
        f"times from {display_time(times[0])} to {display_time(times[-1])}"
    )

    n_chs = len(raw_channel_groups)
    for ch_idx, ch in enumerate(sorted([*raw_channel_groups.keys()])):
        if uvd.data_array is None:
            # first time around, read into existing UVData object
            uvd_ = uvd
        else:
            # otherwise make a new UVData object, the same type as uvd
            uvd_ = type(uvd)()

        channel_raw_fits = raw_channel_groups[ch]
        if len(channel_raw_fits) == 0:
            raise UserWarning(f"no raw files for channel {ch}")
        mwalib_channel_times = mwalib_get_common_times(metafits, channel_raw_fits, good)

        compare_channel_times(
            f"channel {ch}",
            times,
            mwalib_channel_times,
            (" mwalib good" if good else " mwalib"),
        )

        channel_size_mb = sum([file_sizes_mb[f] for f in channel_raw_fits])
        print(
            f"reading channel {ch}: {int(channel_size_mb)}MB of raw files"
            f" ({ch_idx + 1} of {n_chs})"
        )
        ch_start = time.time()
        # initial read: no data, just get time array
        uvd_.read([metafits, *channel_raw_fits], read_data=False)
        uv_channel_times = Time(np.unique(uvd_.time_array), format="jd")
        compare_channel_times(f"channel {ch}", times, uv_channel_times, " uv")

        try:
            uvd_.read(
                [metafits, *channel_raw_fits],
                read_data=True,
                times=time_array,
                **read_kwargs,
            )
        except ValueError as exc:
            traceback.print_exception(exc)
            exit(1)
        read_time = time.time() - ch_start
        print(
            f"reading channel {ch} took {int(read_time)}s. "
            f"{int(channel_size_mb / read_time)} MB/s"
        )
        # if not first time around, add uvd_ into uvd
        if uvd_ != uvd:
            uvd.__add__(uvd_, inplace=True)

    read_time = time.time() - start
    print(f"read took {int(read_time)}s. {int(total_size_mb / read_time)} MB/s")


def read_select(ss: SS, args):
    """Read provided files into ss and select data."""
    file_groups = group_by_filetype(args.files)

    print(f"reading from {file_groups=}")

    read_kwargs = {
        "diff": args.diff,  # difference timesteps
        "remove_coarse_band": args.remove_coarse_band,  # doesn't work with low freq res
        "correct_van_vleck": args.correct_van_vleck,  # slow
        "remove_flagged_ants": args.remove_flagged_ants,  # remove flagged ants
        "flag_init": args.flag_init,
        "flag_choice": args.flag_choice,
        "run_check": False,
    }
    if "spectrum_type" in vars(args) and args.spectrum_type != "all":
        read_kwargs["ant_str"] = args.spectrum_type
    select_kwargs = {"run_check": False}

    # output name is basename of metafits, first uvfits or first ms if provided
    base = None
    # metafits and mwaf flag files only used if raw fits supplied
    other_types = set(file_groups.keys()) - {".fits", ".metafits"}
    if ".fits" in file_groups:
        if ".metafits" not in file_groups:
            raise UserWarning(f"fits supplied, but no metafits in {args.files}")
        total_size_mb = sum(
            du_bs(Path(f)) for f in file_groups[".fits"] + file_groups[".metafits"]
        )
        metafits = sorted(file_groups[".metafits"])[0]
        base, _ = splitext(metafits)
        fg_by_id = file_group_by_obsid(file_groups)
        # fg_by_id = {"AAA": file_groups}
        print(fg_by_id)
        if len(fg_by_id) == 1:
            read_raw(ss, file_groups[".metafits"][0], file_groups[".fits"], read_kwargs)
        else:
            print(f"multiple obsids supplied for {base}: {[*fg_by_id.keys()]}")
            for _idx, obsid in enumerate(sorted([*fg_by_id.keys()])):
                obs_groups = fg_by_id[obsid]
                if ".fits" not in file_groups or ".metafits" not in file_groups:
                    raise UserWarning(
                        f"obsid {obsid} has no metafits or fits files in {obs_groups}"
                    )
                metafits_, raw_fits = obs_groups[".metafits"][0], obs_groups[".fits"]
                if ss.data_array is None:
                    # first time around, read into existing object
                    ss_ = ss
                else:
                    # otherwise make a new object, the same type as ss
                    ss_ = type(ss)()
                ss_ = ss
                read_raw(ss_, metafits_, raw_fits, read_kwargs)
                # if not first time around, add uvd_ into uvd
                if ss_ != ss:
                    ss.__add__(ss_, inplace=True)
                ss_times = Time(np.unique(ss.time_array), format="jd")
                print(
                    f"obsid {obsid} - found {len(ss_times)} times "
                    f"from {display_time(ss_times[0])} to {display_time(ss_times[-1])}"
                )

                print(f"{ss.data_array.shape=} {ss_.data_array.shape=}")
            ss_times = Time(np.unique(ss.time_array), format="jd")
            print(
                f"all obsids - found {len(ss_times)} times "
                f"from {display_time(ss_times[0])} to {display_time(ss_times[-1])}"
            )

    elif len(other_types) > 1:
        raise UserWarning(f"multiple file types found ({[*other_types]}) {args.files}")
    elif len(other_types.intersection([".ms"])) == 1:
        vis = file_groups.get(".ms", [])
        base, _ = os.path.splitext(vis[0])
        total_size_mb = sum(du_bs(Path(f)) for f in vis)
        print(f"reading total {int(total_size_mb)}MB")
        start = time.time()
        if len(vis) > 0:
            print("not supported by pyuvdata")
        if args.diff:
            read_kwargs["run_check"] = False
            select_kwargs["run_check"] = False
        ss.read(vis, **read_kwargs)
        ss.scan_number_array = None  # these are not handled correctly
        read_time = time.time() - start
        print(f"read took {int(read_time)}s. {int(total_size_mb / read_time)} MB/s")
    elif len(other_types.intersection([".uvfits", ".uvh5"])) == 1:
        vis = sum(
            [file_groups.get(".uvfits", []), file_groups.get(".uvh5", [])], start=[]
        )
        base, _ = os.path.splitext(vis[0])

        total_size_mb = sum(du_bs(Path(f)) for f in vis)
        print(f"reading total {int(total_size_mb)}MB")
        start = time.time()
        ss.read(vis, read_data=True, **read_kwargs)
        read_time = time.time() - start
        print(f"read took {int(read_time)}s. {int(total_size_mb / read_time)} MB/s")
    else:
        raise ValueError(f"could not determine visibility file type {file_groups}")

    if args.sel_pols:
        select_kwargs["polarizations"] = args.sel_pols
    if args.freq_range:
        fmin, fmax = map(float, args.freq_range)
        select_kwargs["frequencies"] = ss.freq_array[
            np.where(np.logical_and(ss.freq_array >= fmin, ss.freq_array <= fmax))
        ]
        if len(select_kwargs["frequencies"]) == 0:
            raise ValueError(
                f"could not find frequencies within bounds {(fmin, fmax)} "
                f"in {ss.freq_array}"
            )
    if args.time_limit is not None and args.time_limit > 0:
        select_kwargs["times"] = [np.unique(ss.time_array)[: args.time_limit]]

    ss.history = ss.history or ""

    start = time.time()
    unflagged_ants = get_unflagged_ants(ss, args)
    if len(unflagged_ants) != len(ss.antenna_numbers):
        select_kwargs["antenna_nums"] = unflagged_ants
    ss.select(inplace=True, **select_kwargs)
    select_time = time.time() - start
    select_message = ""
    if int(select_time) >= 1:
        select_message = f"select took {int(select_time)}s. "
    print(f"select took {int(select_time)}s. {select_message}")
    print("history:", ss.history)

    if args.flag_choice is not None:
        ss.apply_flags(flag_choice=args.flag_choice)

    return base


def main():  # noqa: D103
    parser = get_parser()
    args = parser.parse_args()
    print(f"{args=}")

    if args.plot_type == "flags" and args.diff:
        raise UserWarning("diff not supported for flags plot")

    # sky-subtract https://ssins.readthedocs.io/en/latest/sky_subtract.html
    ss = SS()

    try:
        base = read_select(ss, args)
    except ValueError as exc:
        traceback.print_exception(exc)
        parser.print_usage()
        exit(1)

    plt.style.use("dark_background")
    cmap = mpl.colormaps.get_cmap(args.cmap)
    cmap.set_bad(color="#00000000")

    suffix = get_suffix(args)
    obsname = base.split("/")[-1]
    plt.suptitle(f"{obsname}{suffix}")
    if args.plot_type == "sigchain":
        plot_sigchain(ss, args, obsname, suffix, cmap)
    elif args.plot_type == "spectrum":
        ins = plot_spectrum(ss, args, obsname, suffix, cmap)
        maskname = f"{base}{suffix}"
        ins.write(f"{base}{suffix}", output_type="mask", clobber=True)
        print(f"wrote {maskname}_SSINS_mask.h5")

    elif args.plot_type == "flags":
        plot_flags(ss, args, obsname, suffix, cmap)

    if args.debug:
        plt.subplots_adjust(top=0.95, bottom=0.05, left=0.05, right=0.95)
        # put text box in global coordinates
        endl = "\n"
        plt.text(
            0.5,
            0.5,
            f"{endl.join(sys.argv)}",
            horizontalalignment="center",
            verticalalignment="center",
            transform=plt.gca().transAxes,
        )
    figname = f"{base}{suffix}.{args.plot_type}.png"
    plt.savefig(figname, bbox_inches="tight")
    print(f"wrote {figname}")


if __name__ == "__main__":
    main()

# isolated example:
"""
export outdir= ... # e.g. /data , which has adequate space
export obsid=1418228256
giant-squid submit-vis -w $obsid
docker run --rm -it -v ${outdir:=$PWD}:${outdir} -v $PWD:$PWD \
    $([ -d /demo ] && echo " -v /demo:/demo") \
    -w ${outdir} -e obsid -e outdir \
    --entrypoint /demo/04_ssins.py \
    mwatelescope/mwa-demo:latest \
    $(cd $outdir; ls -1 ${obsid}*fits)
"""
# (default)                     = plot diff spectrum
# --no-diff                     = don't difference visibilities in time (sky-subtract)
# --sigchain --no-diff --autos  = per-auto z-scores
# --flags                       = flag occupancy
