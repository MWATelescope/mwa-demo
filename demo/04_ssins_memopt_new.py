#!/usr/bin/env python

"""
Memory-optimized version of the SSINS RFI identification script.

This version focuses on practical memory optimization without sacrificing reliability.
Key improvements:
1. Strategic garbage collection at critical points
2. Smart handling of read-only arrays
3. Careful processing of large datasets with minimal memory footprint
4. Selective loading of data
"""

import os
import re
import sys
import time
import gc
import psutil
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

from SSINS import INS, MF, SS

# Import original functions from 04_ssins.py
import importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ssins_module = importlib.import_module("04_ssins")

# Get functions from the imported module
get_parser_common = ssins_module.get_parser_common
get_parser = ssins_module.get_parser
group_by_filetype = ssins_module.group_by_filetype
file_group_by_obsid = ssins_module.file_group_by_obsid
group_raw_by_channel = ssins_module.group_raw_by_channel
mwalib_get_common_times = ssins_module.mwalib_get_common_times
get_unflagged_ants = ssins_module.get_unflagged_ants
get_gps_times = ssins_module.get_gps_times
get_suffix = ssins_module.get_suffix
get_match_filter = ssins_module.get_match_filter
preapply_flags = ssins_module.preapply_flags
apply_match_test = ssins_module.apply_match_test
du_bs = ssins_module.du_bs
display_time = ssins_module.display_time
compare_time = ssins_module.compare_time
compare_channel_times = ssins_module.compare_channel_times


def memory_report(label=""):
    """Report current memory usage."""
    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / (1024 * 1024)
    available_mb = psutil.virtual_memory().available / (1024 * 1024)
    print(f"Memory usage {label}: {mem_mb:.2f} MB (Available: {available_mb:.2f} MB)")
    return mem_mb


def plot_spectrum_memopt(ss, args, obsname, suffix, cmap):
    """Memory-optimized version of spectrum plotting."""
    memory_report("before plot_spectrum_memopt")

    # Get basic information
    pols = ss.get_pols()
    gps_times = get_gps_times(ss)
    freqs_mhz = ss.freq_array.flatten() / 1e6

    # Create match filter outside polarization loop to save processing time
    mf = get_match_filter(ss.freq_array, args)

    # Create and configure plot
    fig, axes = plt.subplots(2, len(pols), sharex=True, sharey=True, figsize=(8 * len(pols), 16))
    subplots = np.reshape(axes, (2, len(pols)))

    # Create a list to collect mask filenames for all polarizations
    all_masks = []

    # Process one polarization at a time to reduce memory usage
    for i, pol in enumerate(pols):
        print(f"Processing polarization {pol}")

        # Create a copy of the SS object with just this polarization
        with np.errstate(invalid="ignore"):
            # Explicitly copy to prevent read-only issues
            pol_ss = ss.select(polarizations=[pol], inplace=False)

        # Create INS for this polarization
        try:
            ins = INS(pol_ss, spectrum_type=args.spectrum_type)

            # Apply match test
            apply_match_test(mf, ins, args)

            # Plot results for this polarization
            ax_mets = [
                ("vis_amps", np.array(ins.metric_array[..., 0].copy())),  # Create copy to avoid read-only issues
                ("z_score", np.array(ins.sig_array[..., 0].copy())),      # Create copy to avoid read-only issues
            ]

            for a, (name, metric) in enumerate(ax_mets):
                ax = subplots[a, i]
                ax.set_title(f"{obsname} {name}{suffix} {pol if len(pols) > 1 else ''}")

                # Handle potential NaN or empty arrays
                if np.all(np.isnan(metric)):
                    print(f"Warning: All NaN values in {name} data for {pol}")
                    metric = np.zeros_like(metric)

                # Calculate percentiles safely for visualization limits
                valid_data = metric[~np.isnan(metric)].copy()  # Create a copy to ensure it's not read-only

                if len(valid_data) > 0:
                    # Calculate percentiles safely
                    vmin = float(np.percentile(valid_data, 5))
                    vmax = float(np.percentile(valid_data, 95))
                    if vmin == vmax:  # Handle constant data
                        vmin = float(vmin - 0.1)
                        vmax = float(vmax + 0.1)
                else:
                    vmin, vmax = 0, 1  # Default if no valid data

                print(f"Plotting {name} for {pol}: min={np.nanmin(metric)}, max={np.nanmax(metric)}, " +
                       f"5th percentile={vmin}, 95th percentile={vmax}")

                im = ax.imshow(
                    metric,
                    aspect="auto",
                    interpolation="none",
                    cmap=cmap,
                    vmin=vmin,
                    vmax=vmax,
                    extent=[
                        np.min(freqs_mhz),
                        np.max(freqs_mhz),
                        np.max(gps_times),
                        np.min(gps_times),
                    ],
                )

                # Add colorbar
                plt.colorbar(im, ax=ax)

                if i == 0:
                    ax.set_ylabel("GPS Time [s]")

                if a == len(ax_mets) - 1:
                    ax.set_xlabel("Frequency channel [MHz]")

                if args.export_tsv:
                    channames = [f"{ch: 8.4f}" for ch in freqs_mhz]
                    df = pd.DataFrame(metric, columns=channames, index=gps_times)
                    df.to_csv(
                        p := f"{obsname}.{name}{suffix}.{pol}.tsv",
                        index_label="gps_time",
                        float_format="%.3f",
                        sep="\t",
                    )
                    print(p)

            # Write the mask for this polarization if needed
            maskname = f"{obsname}{suffix}.{pol}"
            print(f"Creating SSINS mask for {pol}")
            ins.write(f"{maskname}", output_type="mask", clobber=True)
            print(f"Wrote {maskname}_SSINS_mask.h5")
            all_masks.append(f"{maskname}_SSINS_mask.h5")

            # Clean up this polarization resources - can't delete properties directly
            del ins

        except Exception as e:
            print(f"Error processing polarization {pol}: {e}")
            traceback.print_exc()

        # Clean up
        del pol_ss
        gc.collect()

    # Make sure the figure adjusts properly to show all polarizations
    plt.tight_layout()

    # Set the figure size proportional to the number of polarizations
    # This ensures all polarizations are visible
    plt.gcf().set_size_inches(8 * len(pols), 16)

    memory_report("after plot_spectrum_memopt")

    # Report all mask files created
    if all_masks:
        print(f"Created mask files: {', '.join(all_masks)}")

    return None


def plot_flags_memopt(ss, args, obsname, suffix, cmap):
    """Memory-optimized version of flag plotting."""
    memory_report("before plot_flags_memopt")

    pols = ss.get_pols()
    gps_times = get_gps_times(ss)
    freqs_mhz = (ss.freq_array.flatten()) / 1e6

    # Calculate occupancy with controlled memory usage
    flag_array = ss.flag_array.reshape(ss.Ntimes, ss.Nbls, ss.Nspws, ss.Nfreqs, len(pols))
    occupancy = np.zeros((ss.Ntimes, ss.Nfreqs), dtype=np.float64)

    # Process chunk by chunk to reduce memory usage
    chunk_size = 10  # Adjust based on memory constraints
    for t_idx in range(0, ss.Ntimes, chunk_size):
        t_end = min(t_idx + chunk_size, ss.Ntimes)
        # Sum over baselines, spws, and pols axes
        chunk_occupancy = np.sum(flag_array[t_idx:t_end], axis=(1, 2, 4), dtype=np.float64)
        occupancy[t_idx:t_end] = chunk_occupancy

    # Convert to fraction
    full_occupancy_value = ss.Nbls * ss.Nspws * len(pols)
    occupancy = occupancy / full_occupancy_value

    # Handle NaN values for visualization
    occupancy[occupancy == 1.0] = np.nan

    plt.suptitle(f"{obsname} occupancy{suffix} {pols[0] if len(pols) == 1 else ''}")
    plt.imshow(
        occupancy,
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

    # Add a color bar
    cbar = plt.colorbar()
    cbar.set_label("Flag occupancy")

    plt.ylabel("GPS Time [s]")
    plt.xlabel("Frequency channel [MHz]")

    plt.gcf().set_size_inches(16, np.min([9, 4 * len(pols)]))

    memory_report("after plot_flags_memopt")


def plot_sigchain_memopt(ss, args, obsname, suffix, cmap):
    """Memory-optimized version of signal chain plotting."""
    memory_report("before plot_sigchain_memopt")

    # Get basic information
    unflagged_ants = get_unflagged_ants(ss, args)

    # Check if we have any antennas to process
    if len(unflagged_ants) == 0:
        print("WARNING: No antennas match the selection criteria for sigchain plotting")
        plt.figure()
        plt.text(0.5, 0.5, "No antennas match the selection criteria",
                 horizontalalignment="center", verticalalignment="center")
        memory_report("after empty plot_sigchain_memopt")
        return

    ant_mask = np.where(np.isin(ss.antenna_numbers, unflagged_ants))[0]
    ant_numbers = np.array(ss.antenna_numbers)[ant_mask]
    ant_names = np.array(ss.antenna_names)[ant_mask]
    pols = ss.get_pols()
    gps_times = get_gps_times(ss)
    freqs_mhz = (ss.freq_array.flatten()) / 1e6

    # Pad names
    name_len = max(len(name) for name in ant_names)
    ant_labels = [f"{name: <{name_len}}" for name in ant_names]

    # Create plot
    fig, axes = plt.subplots(
        2, len(pols), height_ratios=[len(unflagged_ants), ss.Nfreqs]
    )
    subplots = np.reshape(axes, (2, len(pols)))

    # Get match filter first to avoid multiple creations
    mf = get_match_filter(ss.freq_array, args)

    # Process each polarization separately
    for i, pol in enumerate(pols):
        print(f"Processing polarization {pol}")

        # Initialize score arrays
        signal_pscore = np.zeros((len(unflagged_ants), ss.Ntimes))
        spectrum_pscore = np.zeros((ss.Nfreqs, ss.Ntimes))

        # Select only this polarization
        pol_ss = ss.select(polarizations=[pol], inplace=False)

        # Process each antenna individually
        for ant_idx, (ant_num, ant_name) in enumerate(zip(ant_numbers, ant_names)):
            if ant_num not in unflagged_ants:
                continue

            print(f"  Processing antenna {ant_name} ({ant_num})")

            try:
                # Select only baselines with this antenna
                ssa = pol_ss.select(ant_str=f"{ant_num}", inplace=False)

                # Create INS
                with np.errstate(invalid="ignore"):
                    ins = INS(ssa, spectrum_type=args.spectrum_type)

                # Apply match test
                preapply_flags(ssa, ins, args)
                apply_match_test(mf, ins, args)

                # Get data arrays (copy to avoid read-only issues)
                sig_array = np.array(ins.sig_array[..., 0].copy())

                # Update signal score for this antenna
                signal_pscore[ant_idx] = np.sqrt(np.nansum(sig_array**2, axis=0))

                # Update spectrum score incrementally
                spectrum_pscore += np.sqrt(sig_array**2)

                # Clean up
                del ssa, ins, sig_array

            except Exception as e:
                print(f"  Error processing antenna {ant_name}: {e}")

            # Force garbage collection after each antenna
            gc.collect()

        # Plot signal scores
        ax_signal = subplots[0, i]
        ax_signal.set_title(f"{obsname} zscore{suffix} {pol if len(pols) > 1 else ''}")

        # Mask zeros
        signal_pscore[signal_pscore == 0] = np.nan

        # Safe plotting with proper scaling
        valid_signal = signal_pscore[~np.isnan(signal_pscore)].copy()
        if len(valid_signal) > 0:
            vmin_signal = float(np.percentile(valid_signal, 5))
            vmax_signal = float(np.percentile(valid_signal, 95))
        else:
            vmin_signal, vmax_signal = 0, 1

        im1 = ax_signal.imshow(
            signal_pscore,
            aspect="auto",
            interpolation="none",
            cmap=cmap,
            vmin=vmin_signal,
            vmax=vmax_signal,
            extent=[np.min(gps_times), np.max(gps_times), len(ant_labels) - 0.5, -0.5],
        )
        plt.colorbar(im1, ax=ax_signal)

        if i == 0:
            ax_signal.set_ylabel("Antenna")

        ax_signal.set_yticks(np.arange(len(unflagged_ants)))
        ax_signal.set_yticklabels(ant_labels, fontsize=args.fontsize, fontfamily="monospace")

        # Plot spectrum scores
        ax_spectrum = subplots[1, i]

        # Mask zeros
        spectrum_pscore[spectrum_pscore == 0] = np.nan

        # Safe plotting with proper scaling
        valid_spectrum = spectrum_pscore[~np.isnan(spectrum_pscore)].copy()
        if len(valid_spectrum) > 0:
            vmin_spectrum = float(np.percentile(valid_spectrum, 5))
            vmax_spectrum = float(np.percentile(valid_spectrum, 95))
        else:
            vmin_spectrum, vmax_spectrum = 0, 1

        im2 = ax_spectrum.imshow(
            spectrum_pscore,
            aspect="auto",
            interpolation="none",
            cmap=cmap,
            vmin=vmin_spectrum,
            vmax=vmax_spectrum,
            extent=[
                np.min(gps_times),
                np.max(gps_times),
                np.max(freqs_mhz),
                np.min(freqs_mhz),
            ],
        )
        plt.colorbar(im2, ax=ax_spectrum)

        if i == 0:
            ax_spectrum.set_ylabel("Frequency channel [MHz]")
        ax_spectrum.set_xlabel("GPS Time [s]")

        # Clean up
        del pol_ss, signal_pscore, spectrum_pscore
        gc.collect()

    plt.gcf().set_size_inches(
        8 * len(pols), (len(unflagged_ants) + ss.Nfreqs) * args.fontsize / 72
    )

    memory_report("after plot_sigchain_memopt")


def read_data_memopt(ss, args):
    """Memory-optimized data reading."""
    memory_report("before reading data")

    file_groups = group_by_filetype(args.files)
    print(f"Reading from {file_groups=}")

    # Setup read parameters
    read_kwargs = {
        "diff": args.diff,
        "remove_coarse_band": args.remove_coarse_band,
        "correct_van_vleck": args.correct_van_vleck,
        "remove_flagged_ants": args.remove_flagged_ants,
        "flag_init": args.flag_init,
        "flag_choice": args.flag_choice,
        "run_check": False,
    }

    if "spectrum_type" in vars(args) and args.spectrum_type != "all":
        read_kwargs["ant_str"] = args.spectrum_type

    select_kwargs = {"run_check": False}

    # Force garbage collection before reading
    gc.collect()

    # Determine base name and file type
    base = None
    other_types = set(file_groups.keys()) - {".fits", ".metafits"}

    # FITS file handling
    if ".fits" in file_groups:
        if ".metafits" not in file_groups:
            raise ValueError(f"Fits supplied, but no metafits in {args.files}")

        metafits = sorted(file_groups[".metafits"])[0]
        base, _ = splitext(metafits)
        fg_by_id = file_group_by_obsid(file_groups)

        # Read files using original method
        if len(fg_by_id) == 1:
            ssins_module.read_raw(ss, file_groups[".metafits"][0], file_groups[".fits"], read_kwargs)
        else:
            for obsid in sorted(fg_by_id.keys()):
                obs_groups = fg_by_id[obsid]
                if ".fits" not in obs_groups or ".metafits" not in obs_groups:
                    raise ValueError(f"Obsid {obsid} missing metafits or fits files")

                metafits_, raw_fits = obs_groups[".metafits"][0], obs_groups[".fits"]
                if ss.data_array is None:
                    ss_ = ss
                else:
                    ss_ = type(ss)()

                ssins_module.read_raw(ss_, metafits_, raw_fits, read_kwargs)

                if ss_ != ss:
                    ss.__add__(ss_, inplace=True)
                    del ss_
                    gc.collect()

    # MS file handling
    elif len(other_types) > 1:
        raise ValueError(f"Multiple file types found ({[*other_types]}) {args.files}")
    elif len(other_types.intersection([".ms"])) == 1:
        vis = file_groups.get(".ms", [])
        base, _ = os.path.splitext(vis[0])

        if args.diff:
            read_kwargs["run_check"] = False
            select_kwargs["run_check"] = False

        ss.read(vis, **read_kwargs)
        ss.scan_number_array = None

    # UVFITS/UVH5 handling
    elif len(other_types.intersection([".uvfits", ".uvh5"])) == 1:
        vis = sum([file_groups.get(".uvfits", []), file_groups.get(".uvh5", [])], start=[])
        base, _ = os.path.splitext(vis[0])

        total_size_mb = sum(du_bs(Path(f)) for f in vis)
        print(f"Reading total {int(total_size_mb)}MB")

        start = time.time()
        ss.read(vis, read_data=True, **read_kwargs)
        read_time = time.time() - start
        print(f"Read took {int(read_time)}s. {int(total_size_mb / read_time)} MB/s")
    else:
        raise ValueError(f"Could not determine visibility file type {file_groups}")

    # Apply selection criteria
    if args.sel_pols:
        select_kwargs["polarizations"] = args.sel_pols
    if args.freq_range:
        fmin, fmax = map(float, args.freq_range)
        select_kwargs["frequencies"] = ss.freq_array[
            np.where(np.logical_and(ss.freq_array >= fmin, ss.freq_array <= fmax))
        ]
        if len(select_kwargs["frequencies"]) == 0:
            raise ValueError(f"No frequencies found within range {fmin}-{fmax}")
    if args.time_limit is not None and args.time_limit > 0:
        select_kwargs["times"] = [np.unique(ss.time_array)[: args.time_limit]]

    # Get unflagged antennas and select
    start = time.time()
    unflagged_ants = get_unflagged_ants(ss, args)
    if len(unflagged_ants) != len(ss.antenna_numbers):
        select_kwargs["antenna_nums"] = unflagged_ants

    # Select the data
    ss.select(inplace=True, **select_kwargs)
    select_time = time.time() - start
    print(f"Select took {int(select_time)}s.")

    # Apply flags if needed
    if args.flag_choice is not None:
        ss.apply_flags(flag_choice=args.flag_choice)

    # Force garbage collection after reading
    gc.collect()
    memory_report("after reading data")

    return base


def main():
    """Main function with memory optimization."""
    start_time = time.time()
    memory_report("at startup")

    # Parse arguments
    parser = get_parser()
    parser.add_argument(
        "--memopt",
        action="store_true",
        help="Use memory optimization techniques",
    )
    args = parser.parse_args()

    # Print arguments
    print(f"{args=}")

    # Create SS object and read data
    ss = SS()

    try:
        base = read_data_memopt(ss, args)
    except Exception as exc:
        traceback.print_exception(exc)
        parser.print_usage()
        exit(1)

    # Setup plotting
    plt.style.use("dark_background")
    cmap = mpl.colormaps.get_cmap(args.cmap)
    cmap.set_bad(color="#00000000")

    suffix = get_suffix(args)
    obsname = base.split("/")[-1]
    plt.figure().clear()  # Clear any existing figures
    plt.suptitle(f"{obsname}{suffix}")

    # Do the appropriate plotting with memory optimization
    if args.plot_type == "sigchain":
        plot_sigchain_memopt(ss, args, obsname, suffix, cmap)
    elif args.plot_type == "spectrum":
        plot_spectrum_memopt(ss, args, obsname, suffix, cmap)
    elif args.plot_type == "flags":
        plot_flags_memopt(ss, args, obsname, suffix, cmap)

    # Add debug info if requested
    if args.debug:
        plt.subplots_adjust(top=0.95, bottom=0.05, left=0.05, right=0.95)
        endl = "\n"
        plt.text(
            0.5,
            0.5,
            f"{endl.join(sys.argv)}",
            horizontalalignment="center",
            verticalalignment="center",
            transform=plt.gca().transAxes,
        )

    # Save the figure - make sure we have the correct figure
    figname = f"{base}{suffix}.{args.plot_type}.png"
    plt.savefig(figname, bbox_inches="tight")
    print(f"Wrote {figname}")

    # Final memory and time reporting
    end_time = time.time()
    memory_report("at end")
    print(f"Total runtime: {end_time - start_time:.2f}s")


if __name__ == "__main__":
    main()