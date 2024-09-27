#!/usr/bin/env python

# identify RFI using ssins
# details: https://github.com/mwilensky768/SSINS

from pyuvdata import UVData
from SSINS import SS, INS, MF
import os
from os.path import splitext, dirname
import matplotlib as mpl
from matplotlib import pyplot as plt
import numpy as np
from astropy.time import Time
import argparse
from itertools import groupby
import re

from matplotlib.axis import Axis


def get_parser():
    parser = argparse.ArgumentParser()
    # arguments for SS.read()
    group_read = parser.add_argument_group("SS.read")
    group_read.add_argument(
        "files",
        nargs="+",
        help="raw .fits (with .metafits), .uvfits supported",
    )
    group_read.add_argument(
        "--no-diff",
        default=False,
        action="store_true",
        help="don't difference visibilities in time (sky-subtract)",
    )
    group_read.add_argument(
        "--no-flag-init",
        default=False,
        action="store_true",
        help="skip flagging of edge channels, quack time",
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
    group_read.add_argument(
        "--include-flagged-ants",
        default=False,
        action="store_true",
        help="Include flagged antenna when reading raw files",
    )
    group_read.add_argument(
        "--flag-choice",
        default=None,
        nargs=1,
        choices=["original"],
        help="original = apply flags from visibilities before running ssins (not recommended)",
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

    group_sel.add_argument(
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


def group_by_filetype(paths):
    def filetype_classifier(path):
        _, ext = splitext(path)
        return ext

    return {
        k: [*v]
        for k, v in groupby(
            sorted(paths, key=filetype_classifier), key=filetype_classifier
        )
    }


def group_raw_by_channel(metafits, raw_fits):
    __import__("sys").path.insert(0, dirname(__file__))
    mwalib_tools = __import__("03_mwalib")
    ctx = mwalib_tools.MetafitsContext(metafits)
    df_ch = mwalib_tools.get_channel_df(ctx)

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
    from mwalib import CorrelatorContext

    gps_times = []
    with CorrelatorContext(metafits, raw_fits) as corr_ctx:
        timestep_idxs = (
            corr_ctx.common_good_timestep_indices
            if good
            else corr_ctx.common_timestep_indices
        )
        for time_idx in timestep_idxs:
            gps_times.append(corr_ctx.timesteps[time_idx].gps_time_ms / 1000.0)
    times = Time(gps_times, format="gps", scale="utc")
    int_time = times[1] - times[0]
    times -= int_time / 2.0
    return times


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

    file_groups = group_by_filetype(args.files)

    print(f"reading from {file_groups=}")
    # sky-subtract https://ssins.readthedocs.io/en/latest/sky_subtract.html
    ss = SS()
    read_kwargs = {
        "diff": (not args.no_diff),  # difference timesteps
        "remove_coarse_band": args.remove_coarse_band,  # does not work with low freq res
        "correct_van_vleck": args.correct_van_vleck,  # slow
        "remove_flagged_ants": (not args.include_flagged_ants),  # remove flagged ants
        "flag_init": (not args.no_flag_init),
        "ant_str": args.spectrum_type,
        "flag_choice": args.flag_choice,
    }

    # output name is basename of metafits, first uvfits or first ms if provided
    base = None
    # metafits and mwaf flag files only used if raw fits supplied
    metafits = None
    raw_fits = None
    if ".fits" in file_groups:
        if ".metafits" not in file_groups:
            raise UserWarning(f"fits supplied, but no metafits in {args.files}")
        if len(file_groups[".metafits"]) > 1:
            raise UserWarning(f"multiple metafits supplied in {args.files}")
        metafits = file_groups[".metafits"][0]
        base, _ = splitext(metafits)
        raw_fits = file_groups[".fits"]
        if len(raw_fits) > 1:
            times = mwalib_get_common_times(metafits, raw_fits)
            time_array = times.jd.astype(float)
            # group and read raw by channel to save memory
            raw_channel_groups = group_raw_by_channel(metafits, raw_fits)
            for ch in sorted([*raw_channel_groups.keys()]):
                ss_ = type(ss)()
                ss_.read(
                    [metafits, *raw_channel_groups[ch]],
                    read_data=True,
                    times=time_array,
                    **read_kwargs,
                )
                if ss.data_array is None:
                    ss = ss_
                else:
                    ss.__add__(ss_, inplace=True)
        else:
            ss.read([metafits, *raw_fits], read_data=True, **read_kwargs)
    elif ".uvfits" in file_groups and ".ms" in file_groups:
        raise UserWarning(f"both ms and uvfits in {args.files}")
    elif ".uvfits" in file_groups or ".ms" in file_groups:
        vis = file_groups.get(".uvfits", []) + file_groups.get(".ms", [])
        base, _ = os.path.splitext(vis[0])
        ss.read(vis, read_data=True, **read_kwargs)
    else:
        parser.print_usage()
        exit(1)

    unflagged_ants = get_unflagged_ants(ss, args)

    select_kwargs = {}
    if args.sel_pols:
        select_kwargs["polarizations"] = args.sel_pols
    ss.select(inplace=True, **select_kwargs)
    ss.apply_flags(flag_choice=args.flag_choice)

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
