#!/usr/bin/env python
from SSINS import SS, INS, MF
import os
import matplotlib as mpl
from matplotlib import pyplot as plt
import numpy as np
from astropy.time import Time
import argparse
import pandas as pd

parser = argparse.ArgumentParser()
parser.add_argument("--no-diff", default=False, action="store_true")
parser.add_argument("--no-cache", default=False, action="store_true")
group = parser.add_mutually_exclusive_group()
group.add_argument("--crosses", default=False, action="store_true", help="plot crosses instead of default: autos")
group.add_argument("--sigchain", default=False, action="store_true", help="plot sigchain instead of default: spectrum", )

parser.add_argument("--threshold", default=5, help="match filter significance threshold")
parser.add_argument("--fontsize", default=8, help="plot font size")
parser.add_argument("files", nargs="+")
args = parser.parse_args()

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

# sky-subtract https://ssins.readthedocs.io/en/latest/sky_subtract.html
ss = SS()

def get_unflagged_ants(ss, args):
    # TODO: args to flag additional ants
    return np.unique(ss.ant_1_array)

suffix = "" if args.no_diff else ".diff"
spectrum_type = "cross" if args.crosses else "auto"
suffix += f".{spectrum_type}"
cache = f"{base}{suffix}.h5"
if not args.no_cache and os.path.exists(cache):
    print(f"reading from {cache=}")
    ss.read_uvh5(cache, read_data=True, use_future_array_shapes=True)
    unflagged_ants = get_unflagged_ants(ss, args)
else:
    print(f"reading from {args.files=}")
    ss.read(
        args.files,
        read_data=True,
        diff=(not args.no_diff),  # difference timesteps
        remove_coarse_band=False,  # does not work with low freq res
        correct_van_vleck=False,  # slow
        remove_flagged_ants=True,  # remove flagged antennas
    )

    unflagged_ants = get_unflagged_ants(ss, args)
    def cross_filter(pair):
        a, b = pair
        return a != b and a in unflagged_ants and b in unflagged_ants
    def auto_filter(pair):
        a, b = pair
        return a == b and a in unflagged_ants
    bls = [*filter( {"cross": cross_filter, "auto": auto_filter}[spectrum_type], ss.get_antpairs() )]
    ss = ss.select(bls=bls, inplace=False)
    ss.apply_flags(flag_choice="original")
    if not args.no_cache:
        ss.write_uvh5(cache)
        print(f"wrote ss to {cache=}")

# incoherent noise spectrum https://ssins.readthedocs.io/en/latest/incoherent_noise_spectrum.html
ins = INS(ss, spectrum_type=spectrum_type)

# match filter https://ssins.readthedocs.io/en/latest/match_filter.html
mf = MF(ss.freq_array, args.threshold, streak=True, narrow=False)
mf.apply_match_test(ins)
ins.sig_array[~np.isfinite(ins.sig_array)] = 0

# #### #
# PLOT #
# #### #
plt.style.use("dark_background")
cmap = mpl.colormaps.get_cmap("viridis")
cmap.set_bad(color="#00000000")

pols = ss.get_pols()
gps_times = np.unique(Time(ss.time_array, format="jd").gps)
int_time = np.unique(ss.integration_time)[0]
obsid = round(gps_times[0] - int_time / 2)
title = f"{obsid}"
plt.title(title)

def plot_sigchain(ss, args):
    ant_mask = np.where(np.isin(ss.antenna_numbers, unflagged_ants))[0]
    antenna_numbers = np.array(ss.antenna_numbers)[ant_mask]
    antenna_names = np.array(ss.antenna_names)[ant_mask]

    # build a scores array for each signal chain
    scores = np.zeros((len(unflagged_ants), ss.Ntimes, ss.Nfreqs, ss.Npols))
    for ant_idx, (ant_num, ant_name) in enumerate(zip(antenna_numbers, antenna_names)):
        print(ant_idx, ant_num, ant_name)
        if ant_num not in unflagged_ants:
            continue
        # select only the auto-correlation for this antenna
        ssa = ss.select(antenna_nums=[(ant_num, ant_num)], inplace=False)
        ins = INS(ssa, spectrum_type="auto")
        mf.apply_match_test(ins)
        ins.sig_array[~np.isfinite(ins.sig_array)] = 0
        scores[ant_idx] = ins.sig_array

    plt.style.use("dark_background")
    subplots = plt.subplots(
        2,
        len(pols),
        height_ratios=[len(unflagged_ants), ss.Nfreqs],
    )[1]

    def slice(scores, axis):
        pscore = np.sqrt(np.sum(scores**2, axis=-1))
        # make per-antenna anomalies stand out more
        # pscore = pscore / np.nanstd(pscore, axis=1)[:, np.newaxis]
        # subtract minimum value
        # pscore -= np.nanmin(pscore)
        return pscore

    # pad names
    namelen = max(len(name) for name in antenna_names)
    antnames = [f"{name: <{namelen}}" for name in antenna_names]
    channames = [f"{ch: 8.4f}" for ch in ss.freq_array / 1e6]

    for i, pol in enumerate(ss.get_pols()):
        ax_signal, ax_spectrum = subplots[:, i]
        title = f"{obsid} Autos z-score magnitude {pol}"

        # by signal chain: [ant, time]
        signal_pscore = slice(scores[..., i], axis=-1)
        print(signal_pscore.shape)
        signal_df = pd.DataFrame(
            signal_pscore.transpose(), index=gps_times, columns=antnames
        )
        signal_df.to_csv(
            f"{base}.auto_sig.{pol}.tsv",
            index_label="gps_time",
            float_format="%.3f",
            sep="\t",
        )

        ax_signal.imshow(signal_pscore, aspect="auto", interpolation="none", cmap=cmap)
        ax_signal.set_ylabel("Antenna")
        ax_spectrum.set_xlabel("Timestep")
        ax_signal.set_yticks(np.arange(len(unflagged_ants)))
        ax_signal.tick_params(pad=True)
        ax_signal.set_yticklabels(antnames, fontsize=args.fontsize)
        ax_signal.set_title(f"{obsid} Autos z-score row-normalized {pol}")

        # by spectrum: [freq, time]
        spectrum_pscore = slice(scores[..., i].transpose(2, 1, 0), axis=-1)
        spectrum_df = pd.DataFrame(
            spectrum_pscore.transpose(), index=gps_times, columns=channames
        )
        spectrum_df.to_csv(
            f"{base}.auto_spx.{pol}.tsv",
            index_label="gps_time",
            float_format="%.3f",
            sep="\t",
        )
        ax_spectrum.set_xlabel("Timestep")
        ax_spectrum.set_ylabel("Frequency channel")
        ax_spectrum.set_yticks(np.arange(ss.Nfreqs))
        ax_spectrum.set_yticklabels(channames, fontsize=args.fontsize)
        ax_spectrum.tick_params(pad=True)
        ax_spectrum.imshow(spectrum_pscore, aspect="auto", interpolation="none", cmap=cmap)

def plot_spectrum(ss, args):
    pols = ss.get_pols()
    subplot_rows = 2

    subplots = plt.subplots(
        subplot_rows,
        len(pols),
        sharex=True,
        sharey=True,
    )[1]

    time_labels = [*Time(np.unique(ss.time_array), format="jd").iso]
    ntimes_visible = 16 * 72 / args.fontsize / 2.4 / subplot_rows
    time_stride = int(max(1, len(time_labels) // ntimes_visible))
    chan_labels = [f"{ch: 8.3f}" for ch in ss.freq_array / 1e6]
    nchans_visible = 16 * 72 / args.fontsize / 2.0 / len(pols)
    chan_stride = int(max(1, len(chan_labels) // nchans_visible))

    for i, pol in enumerate(pols):
        ax_met, ax_sig = subplots[:, i]

        ax_met.set_title(
            f'{base.split("/")[-1]} ss vis amps{suffix} {pol}'
        )
        ax_met.imshow(
            ins.metric_array[..., i], aspect="auto", interpolation="none", cmap=cmap
        )
        ax_sig.set_title(f'{base.split("/")[-1]} z-score {pol}')
        ax_sig.imshow(ins.sig_array[..., i], aspect="auto", interpolation="none", cmap=cmap)
        if i == 0:
            ax_met.set_ylabel("Timestep [UTC]")
            ax_met.set_yticks(np.arange(ss.Ntimes)[::time_stride])
            ax_met.set_yticklabels(
                time_labels[::time_stride], fontsize=args.fontsize, fontfamily="monospace"
            )
            ax_sig.set_ylabel("Timestep [UTC]")
            ax_sig.set_yticks(np.arange(ss.Ntimes)[::time_stride])
            ax_sig.set_yticklabels(
                time_labels[::time_stride], fontsize=args.fontsize, fontfamily="monospace"
            )

        ax_sig.set_xlabel("Frequency channel [MHz]")
        ax_sig.set_xticks(np.arange(ss.Nfreqs)[::chan_stride])
        ax_sig.set_xticklabels(chan_labels[::chan_stride], fontsize=args.fontsize, rotation=90)

if args.sigchain:
    plot_sigchain(ss, args)
    plt.gcf().set_size_inches(8 * len(pols), (len(unflagged_ants) + ss.Ntimes) * args.fontsize / 72)
    figname = f"{base}{suffix}.sigchain.png"
else:
    plot_spectrum(ss, args)
    plt.gcf().set_size_inches(8 * len(pols), 16)
    figname = f"{base}{suffix}.spectrum.png"

plt.savefig(figname, bbox_inches="tight")
print(f"wrote {figname}")