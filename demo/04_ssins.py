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
from argparse import ArgumentParser, SUPPRESS
from itertools import groupby
import re
import time
import traceback
from pathlib import Path
import pandas as pd

from matplotlib.axis import Axis


def get_parser():
    parser = ArgumentParser()
    # arguments for SS.read()
    group_read = parser.add_argument_group("SS.read")
    group_read.add_argument(
        "files",
        nargs="+",
        help="Raw .fits (with .metafits), .uvfits, .uvh5, .ms supported",
    )
    group_mutex = group_read.add_mutually_exclusive_group()
    group_mutex.add_argument("--diff", default=True, help=SUPPRESS)
    group_mutex.add_argument(
        "--no-diff",
        action="store_false",
        dest="diff",
        help="Don't difference visibilities in time (sky-subtract)",
    )
    group_mutex = group_read.add_mutually_exclusive_group()
    group_mutex.add_argument("--flag-init", default=True, help=SUPPRESS)
    group_mutex.add_argument(
        "--no-flag-init",
        action="store_false",
        dest="flag_init",
        help="Skip flagging of quack time, edge channels",
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
        help="original = apply flags from visibilities before running ssins (only recommended for --plot-type=flags)",
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

    # arguments for SSINS.INS
    group_ins = parser.add_argument_group("SSINS.INS")
    group_ins.add_argument(
        "--spectrum-type",
        default="all",
        choices=["all", "auto", "cross"],
        help="analyse auto-correlations or cross-correlations. default: auto",
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

    # arguments for SSINS.MF
    group_mf = parser.add_argument_group("SSINS.MF")
    group_mf.add_argument(
        "--threshold",
        default=5,
        type=float,
        help="match filter significance threshold. 0 disables match filter",
    )
    group_mutex = group_mf.add_mutually_exclusive_group()
    group_mutex.add_argument("--narrow", default=True, help=SUPPRESS)
    group_mutex.add_argument(
        "--no-narrow",
        action="store_false",
        dest="narrow",
        help="Don't look for narrowband RFI",
    )
    group_mutex = group_mf.add_mutually_exclusive_group()
    group_mutex.add_argument("--streak", default=True, help=SUPPRESS)
    group_mutex.add_argument(
        "--no-streak",
        action="store_false",
        dest="streak",
        help="Don't look for streak RFI",
    )

    # plotting
    group_plot = parser.add_argument_group("plotting")
    group_plot.add_argument(
        "--plot-type",
        default="spectrum",
        choices=["spectrum", "sigchain", "flags"],
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

    group_plot.add_argument(
        "--cmap",
        default="viridis",
        help="matplotlib.colormaps.get_cmap, default: viridis",
    )

    group_plot.add_argument(
        "--suffix",
        default="",
        type=str,
        help="additional text to add to plot output filename",
    )
    group_plot.add_argument("--fontsize", default=8, help="plot tick label font size")

    parser.add_argument(
        "--export-tsv", default=False, action="store_true", help="export values to TSV"
    )

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

    return present_ant_nums


def get_gps_times(uvd: UVData):
    return [*Time(np.unique(uvd.time_array), format="jd").gps]


def get_suffix(args):
    suffix = args.suffix
    if args.spectrum_type != "all":
        suffix = f".{args.spectrum_type}{suffix}"
    if args.diff:
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
    return MF(
        freq_array=ss.freq_array,
        sig_thresh=args.threshold,
        streak=args.streak,
        narrow=args.narrow,
    )


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
        # select only baselines or autos with this antenna
        ssa = ss.select(ant_str=f"{ant_num}", inplace=False)
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
            ax_signal.yaxis.set_label("Antenna")

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

        ax_signal.yaxis.set_ticks(np.arange(len(unflagged_ants)))
        ax_signal.yaxis.set_tick_params(pad=True)
        ax_signal.yaxis.set_ticklabels(
            ant_labels, fontsize=args.fontsize, fontfamily="monospace"
        )

        # by spectrum: [freq, time]
        ax_spectrum: Axis = subplots[1, i]
        ax_spectrum.xaxis.set_label("GPS Time [s]")
        if i == 0:
            ax_spectrum.yaxis.set_label("Frequency channel [MHz]")

        spectrum_pscore = slice(scores[..., i].transpose(2, 1, 0), axis=-1)

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
        8 * len(pols), (len(unflagged_ants) + ss.Nfreqs) * args.fontsize / 72
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
    channames = [f"{ch: 8.4f}" for ch in freqs_mhz]

    subplots = plt.subplots(
        2,
        len(pols),
        sharex=True,
        sharey=True,
    )[1]
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


def plot_flags(ss: UVData, args, obsname, suffix, cmap):
    pols = ss.get_pols()
    gps_times = get_gps_times(ss)
    freqs_mhz = (ss.freq_array) / 1e6

    occupancy = np.sum(
        ss.flag_array.reshape(ss.Ntimes, ss.Nbls, ss.Nspws, ss.Nfreqs, len(pols)),
        axis=(1, 2),
    ).astype(np.float64)
    full_occupancy_value = ss.Nbls * ss.Nspws
    occupancy[occupancy == full_occupancy_value] = np.nan
    max_occupancy = np.nanmax(occupancy)
    print(f"{max_occupancy=}")
    # clip at half occupancy
    # occupancy[occupancy >= full_occupancy_value / 2] = full_occupancy_value / 2

    occupancy /= full_occupancy_value

    subplots = plt.subplots(
        len(pols),
        1,
        sharex=True,
        sharey=True,
    )[1]
    if len(pols) == 1:
        subplots = [subplots]

    for i, pol in enumerate(pols):
        ax: Axis = subplots[i]

        ax.set_title(f"{obsname} occupancy{suffix} {pol if len(pols) > 1 else ''}")
        ax.imshow(
            occupancy[..., i],
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

        ax.set_ylabel("GPS Time [s]")

        if i == len(pols) - 1:
            ax.set_xlabel("Frequency channel [MHz]")

    plt.gcf().set_size_inches(16, np.min([9, 4 * len(pols)]))


def du_bs(path: Path, bs=1024 * 1024):
    if path.is_file():
        return path.stat().st_size / bs
    return sum(f.stat().st_size for f in path.glob("**/*") if f.is_file()) / bs


def read_raw(uvd: UVData, metafits, raw_fits, read_kwargs):
    file_sizes_mb = {f: du_bs(Path(f)) for f in raw_fits}
    total_size_mb = sum(file_sizes_mb.values())
    print(f"reading total {int(total_size_mb)}MB of raw files")

    start = time.time()
    if len(raw_fits) <= 1:
        uvd.read([metafits, *raw_fits], read_data=True, **read_kwargs)
        read_time = time.time() - start
        print(f"read took {int(read_time)}s. {int(total_size_mb/read_time)} MB/s")
        return uvd

    # group and read raw by channel to save memory
    raw_channel_groups = group_raw_by_channel(metafits, raw_fits)
    # channels not always aligned in time
    good = False
    times = mwalib_get_common_times(metafits, raw_fits, good)
    time_array = times.jd.astype(float)
    print(
        f"times from {times[0].isot} ({times[0].gps}) to {times[-1].isot} ({times[-1].gps})"
    )

    n_chs = len(raw_channel_groups)
    for ch_idx, ch in enumerate(sorted([*raw_channel_groups.keys()])):
        # make a new UVData object, the same type as
        uvd_ = type(uvd)()
        channel_raw_fits = raw_channel_groups[ch]
        channel_times = mwalib_get_common_times(metafits, raw_fits, good)
        print(
            f"channel {ch} times from {channel_times[0].isot} "
            f"({channel_times[0].gps}) to {channel_times[-1].isot} ({channel_times[-1].gps})"
        )
        if channel_times[0] != times[0]:
            print(
                f"WARN: channel {ch} starts at {channel_times[0].isot} but common is {times[0].isot}"
            )
        if channel_times[-1] != times[-1]:
            print(
                f"WARN: channel {ch} ends at {channel_times[-1].isot} but common is {times[-1].isot}"
            )

        channel_size_mb = sum([file_sizes_mb[f] for f in channel_raw_fits])
        print(
            f"reading channel {ch}: {int(channel_size_mb)}MB of raw files ({ch_idx+1} of {n_chs})"
        )
        ch_start = time.time()
        uvd_.read(
            [metafits, *raw_channel_groups[ch]],
            read_data=True,
            times=time_array,
            **read_kwargs,
        )
        read_time = time.time() - ch_start
        print(
            f"reading channel {ch} took {int(read_time)}s. {int(channel_size_mb/read_time)} MB/s"
        )
        if uvd.data_array is None:
            uvd = uvd_
        else:
            uvd.__add__(uvd_, inplace=True)

    read_time = time.time() - start
    print(f"read took {int(read_time)}s. {int(total_size_mb/read_time)} MB/s")


def read_select(uvd: UVData, args):
    file_groups = group_by_filetype(args.files)

    print(f"reading from {file_groups=}")

    read_kwargs = {
        "diff": args.diff,  # difference timesteps
        "remove_coarse_band": args.remove_coarse_band,  # does not work with low freq res
        "correct_van_vleck": args.correct_van_vleck,  # slow
        "remove_flagged_ants": args.remove_flagged_ants,  # remove flagged ants
        "flag_init": args.flag_init,
        "ant_str": args.spectrum_type,
        "flag_choice": args.flag_choice,
    }
    select_kwargs = {}

    # output name is basename of metafits, first uvfits or first ms if provided
    base = None
    # metafits and mwaf flag files only used if raw fits supplied
    other_types = set(file_groups.keys()) - set([".fits", ".metafits"])
    if ".fits" in file_groups:
        if ".metafits" not in file_groups:
            raise UserWarning(f"fits supplied, but no metafits in {args.files}")
        if len(file_groups[".metafits"]) > 1:
            raise UserWarning(f"multiple metafits supplied in {args.files}")
        metafits = file_groups[".metafits"][0]
        base, _ = splitext(metafits)
        read_raw(uvd, metafits, file_groups[".fits"], read_kwargs)
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
        uvd.read(vis, **read_kwargs)
        uvd.scan_number_array = None  # these are not handled correctly
        read_time = time.time() - start
        print(f"read took {int(read_time)}s. {int(total_size_mb/read_time)} MB/s")
    elif len(other_types.intersection([".uvfits", ".uvh5"])) == 1:
        vis = sum(
            [
                file_groups.get(".uvfits", []),
                file_groups.get(".uvh5", []),
            ],
            start=[],
        )
        base, _ = os.path.splitext(vis[0])

        total_size_mb = sum(du_bs(Path(f)) for f in vis)
        print(f"reading total {int(total_size_mb)}MB")
        start = time.time()
        uvd.read(vis, read_data=True, **read_kwargs)
        read_time = time.time() - start
        print(f"read took {int(read_time)}s. {int(total_size_mb/read_time)} MB/s")
    else:
        raise ValueError

    if args.sel_pols:
        select_kwargs["polarizations"] = args.sel_pols
    if args.freq_range:
        fmin, fmax = map(float, args.freq_range)
        select_kwargs["frequencies"] = uvd.freq_array[
            np.where(np.logical_and(uvd.freq_array >= fmin, uvd.freq_array <= fmax))
        ]
        if len(select_kwargs["frequencies"]) == 0:
            raise ValueError(
                f"could not find frequencies within bounds {(fmin, fmax)} in {uvd.freq_array}"
            )
    if args.time_limit is not None and args.time_limit > 0:
        select_kwargs["times"] = [np.unique(uvd.time_array)[: args.time_limit]]

    uvd.select(inplace=True, **select_kwargs)

    return base


def main():
    parser = get_parser()
    args = parser.parse_args()
    print(f"{args=}")

    # sky-subtract https://ssins.readthedocs.io/en/latest/sky_subtract.html
    ss = SS()

    try:
        base = read_select(ss, args)
    except ValueError as exc:
        traceback.print_exception(exc)
        parser.print_usage()
        exit(1)

    # TODO: ss.apply_flags(flag_choice=flag_choice) ?

    plt.style.use("dark_background")
    cmap = mpl.colormaps.get_cmap(args.cmap)
    cmap.set_bad(color="#00000000")

    suffix = get_suffix(args)
    obsname = base.split("/")[-1]
    plt.suptitle(f"{obsname}{suffix}")
    if args.plot_type == "sigchain":
        plot_sigchain(ss, args, obsname, suffix, cmap)
    elif args.plot_type == "spectrum":
        plot_spectrum(ss, args, obsname, suffix, cmap)
    elif args.plot_type == "flags":
        plot_flags(ss, args, obsname, suffix, cmap)

    figname = f"{base}{suffix}.{args.plot_type}.png"
    plt.savefig(figname, bbox_inches="tight")
    print(f"wrote {figname}")


if __name__ == "__main__":
    main()
