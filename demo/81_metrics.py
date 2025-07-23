#!/usr/bin/env python

"""
Plot the metrics files produced by Birli --metrics-out.

example usage:
. .venv/bin/activate && demo/81_metrics.py --name foo bar.fits ...
"""

import argparse
from os.path import realpath
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from astropy.io import fits


def main():
    parser = argparse.ArgumentParser(
        description="Plot metrics files produced by Birli --metrics-out",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --name obsid *.fits
  %(prog)s --name 1436729760 birli_*_metrics.fits
        """,
    )

    parser.add_argument(
        "--name", required=True, help="Name for the output plots (e.g., observation ID)"
    )
    parser.add_argument("--show", action="store_true", help="Show plots interactively")
    parser.add_argument("files", nargs="+", help="Metrics FITS files to process")

    args = parser.parse_args()

    # Use CLI arguments
    metrics_files = sorted(args.files)
    name = args.name
    show = args.show
    plt.style.use("dark_background")

    print(f"Found {len(metrics_files)} metrics files")

    # Store data and time coordinates separately
    all_data = {
        "AO_FLAG_METRICS": [],
        "SSINS_POL=XX": [],
        "SSINS_POL=XY": [],
        "SSINS_POL=YY": [],
        "EAVILS_POL=XX": [],
        "EAVILS_POL=XY": [],
        "EAVILS_POL=YY": [],
    }
    all_times = []  # GPS times for each sample

    # Store additional metrics data
    additional_data = {
        "AUTO_POL=XX": [],
        "AUTO_POL=YY": [],
        "AUTO_POL=XY": [],
        "EAVILS_MEAN_AMP_FP": [],
        "EAVILS_SQRT_MEAN_VAR_AMP_FP": [],
        "SSINS_DIFF_MEAN_AMP_FP": [],
    }
    additional_times = []  # GPS times for additional metrics

    # Store 2D data for additional metrics (AMP_FP)
    additional_data_2d = {
        "AUTO_POL=XX": [],
        "AUTO_POL=YY": [],
        "AUTO_POL=XY": [],
        "EAVILS_MEAN_AMP_FP": [],
        "EAVILS_SQRT_MEAN_VAR_AMP_FP": [],
        "SSINS_DIFF_MEAN_AMP_FP": [],
    }
    additional_times_2d = {
        "AUTO_POL=XX": [],
        "AUTO_POL=YY": [],
        "AUTO_POL=XY": [],
        "EAVILS_MEAN_AMP_FP": [],
        "EAVILS_SQRT_MEAN_VAR_AMP_FP": [],
        "SSINS_DIFF_MEAN_AMP_FP": [],
    }

    # Store 2D data for waterfall plots, grouped by dimensions
    all_data_2d = {}
    all_times_2d = {}

    files_processed = 0
    for filename in metrics_files:
        # Extract GPS time from filename
        gps_time = int(Path(filename).stem.split("_")[1])

        try:
            with fits.open(filename) as hdul:
                # Check if all required HDUs exist
                required_hdus = [
                    "AO_FLAG_METRICS",
                    "SSINS_POL=XX",
                    "SSINS_POL=XY",
                    "SSINS_POL=YY",
                    "EAVILS_POL=XX",
                    "EAVILS_POL=XY",
                    "EAVILS_POL=YY",
                ]

                # Additional HDUs (optional)
                additional_hdus = [
                    "AUTO_POL=XX",
                    "AUTO_POL=YY",
                    "AUTO_POL=XY",
                    "EAVILS_MEAN_AMP_FP",
                    "EAVILS_SQRT_MEAN_VAR_AMP_FP",
                    "SSINS_DIFF_MEAN_AMP_FP",
                ]

                missing_hdus = []
                for hdu_name in required_hdus:
                    try:
                        hdul[hdu_name]
                    except KeyError:
                        missing_hdus.append(hdu_name)

                if missing_hdus:
                    continue

                # Extract time coordinate information from AO_FLAG_METRICS HDU
                ao_hdu = hdul["AO_FLAG_METRICS"]
                header = ao_hdu.header

                # WCS time parameters
                crval2 = header.get("CRVAL2", gps_time)  # GPS time of reference pixel
                cdelt2 = header.get("CDELT2", 2.0)  # Time step in seconds
                crpix2 = header.get("CRPIX2", 1.0)  # Reference pixel

                # WCS frequency parameters
                crval1 = header.get(
                    "CRVAL1", 167040000.0
                )  # Frequency of reference pixel (Hz)
                cdelt1 = header.get("CDELT1", 20000.0)  # Frequency step (Hz)
                crpix1 = header.get("CRPIX1", 1.0)  # Reference pixel

                # Extract the required HDUs
                ao_flag = hdul["AO_FLAG_METRICS"].data  # (148, 1536)
                ssins_xx = hdul["SSINS_POL=XX"].data  # (147, 1536)
                ssins_xy = hdul["SSINS_POL=XY"].data  # (147, 1536)
                ssins_yy = hdul["SSINS_POL=YY"].data  # (147, 1536)
                eavils_xx = hdul["EAVILS_POL=XX"].data  # (148, 1536)
                eavils_xy = hdul["EAVILS_POL=XY"].data  # (148, 1536)
                eavils_yy = hdul["EAVILS_POL=YY"].data  # (148, 1536)

                # Handle time alignment - use SSINS time length (147 samples)
                n_time_samples = ssins_xx.shape[0]  # 147

                # Calculate GPS times for each sample using WCS
                # Time = CRVAL2 + (pixel_index - CRPIX2 + 1) * CDELT2
                pixel_indices = np.arange(1, n_time_samples + 1)  # 1-based indexing
                gps_times = crval2 + (pixel_indices - crpix2) * cdelt2

                # Truncate AO_FLAG and EAVILS to match SSINS (147 samples)
                ao_flag_aligned = ao_flag[:n_time_samples, :]
                eavils_xx_aligned = eavils_xx[:n_time_samples, :]
                eavils_xy_aligned = eavils_xy[:n_time_samples, :]
                eavils_yy_aligned = eavils_yy[:n_time_samples, :]

                # Store mean over frequency for each time sample
                ao_mean = np.nanmean(ao_flag_aligned, axis=1)
                ssins_xx_mean = np.nanmean(ssins_xx, axis=1)
                ssins_xy_mean = np.nanmean(ssins_xy, axis=1)
                ssins_yy_mean = np.nanmean(ssins_yy, axis=1)
                eavils_xx_mean = np.nanmean(eavils_xx_aligned, axis=1)
                eavils_xy_mean = np.nanmean(eavils_xy_aligned, axis=1)
                eavils_yy_mean = np.nanmean(eavils_yy_aligned, axis=1)

                all_data["AO_FLAG_METRICS"].append(ao_mean)
                all_data["SSINS_POL=XX"].append(ssins_xx_mean)
                all_data["SSINS_POL=XY"].append(ssins_xy_mean)
                all_data["SSINS_POL=YY"].append(ssins_yy_mean)
                all_data["EAVILS_POL=XX"].append(eavils_xx_mean)
                all_data["EAVILS_POL=XY"].append(eavils_xy_mean)
                all_data["EAVILS_POL=YY"].append(eavils_yy_mean)

                # Store the GPS times for this file
                all_times.append(gps_times)

                # Extract additional metrics if available
                for hdu_name in additional_hdus:
                    try:
                        additional_hdu_data = hdul[hdu_name].data

                        if hdu_name.startswith("AUTO_POL="):
                            # AUTO_POL data: (n_antennas, n_frequencies) - NOT time-varying within file
                            # Store the full antenna × frequency array
                            additional_data_2d[hdu_name].append(
                                additional_hdu_data
                            )  # Store full antenna×freq array
                            additional_times_2d[hdu_name].append(
                                gps_times[0]
                            )  # Use file start time

                            # For time series, take mean over antennas and frequencies
                            mean_data = np.nanmean(
                                additional_hdu_data
                            )  # Single value per file
                            mean_array = np.full(
                                n_time_samples, mean_data
                            )  # Repeat for all time samples in file
                            additional_data[hdu_name].append(mean_array)

                        elif "_AMP_FP" in hdu_name:
                            # AMP_FP data: (1536, 4) - store each polarization separately
                            # Polarizations are [XX, YY, XY, YX] - we want first 3
                            n_pols = min(
                                3, additional_hdu_data.shape[1]
                            )  # Take first 3 pols

                            for pol_idx in range(n_pols):
                                pol_names = ["_XX", "_YY", "_XY"]
                                pol_key = hdu_name + pol_names[pol_idx]

                                if pol_key not in additional_data_2d:
                                    additional_data_2d[pol_key] = []
                                    additional_times_2d[pol_key] = []

                                pol_spectrum = additional_hdu_data[
                                    :, pol_idx
                                ]  # Extract this polarization
                                additional_data_2d[pol_key].append(pol_spectrum)
                                additional_times_2d[pol_key].append(gps_times[0])

                    except KeyError:
                        # HDU doesn't exist, append NaNs
                        if hdu_name.startswith("AUTO_POL="):
                            additional_data[hdu_name].append(
                                np.full(n_time_samples, np.nan)
                            )
                            # Store NaN array with antenna × frequency dimensions
                            nan_array_2d = np.full(
                                (128, ao_flag_aligned.shape[1]), np.nan
                            )  # Assume 128 antennas
                            additional_data_2d[hdu_name].append(nan_array_2d)
                            additional_times_2d[hdu_name].append(gps_times[0])
                        elif "_AMP_FP" in hdu_name:
                            # For missing AMP_FP data, store NaN spectrum for each polarization
                            n_freq = ao_flag_aligned.shape[1]  # 768 freqs
                            pol_names = ["_XX", "_YY", "_XY"]

                            for pol_name in pol_names:
                                pol_key = hdu_name + pol_name
                                if pol_key not in additional_data_2d:
                                    additional_data_2d[pol_key] = []
                                    additional_times_2d[pol_key] = []

                                nan_spectrum = np.full(n_freq, np.nan)
                                additional_data_2d[pol_key].append(nan_spectrum)
                                additional_times_2d[pol_key].append(gps_times[0])

                # Store times for additional metrics (same as main metrics)
                additional_times.append(gps_times)

                # Store 2D data for waterfall plots, grouped by shape
                freq_channels = ao_flag_aligned.shape[1]
                shape_key = f"{freq_channels}freq"

                if shape_key not in all_data_2d:
                    all_data_2d[shape_key] = {
                        "AO_FLAG_METRICS": [],
                        "SSINS_POL=XX": [],
                        "SSINS_POL=XY": [],
                        "SSINS_POL=YY": [],
                        "EAVILS_POL=XX": [],
                        "EAVILS_POL=XY": [],
                        "EAVILS_POL=YY": [],
                    }
                    all_times_2d[shape_key] = {
                        "AO_FLAG_METRICS": [],
                        "SSINS_POL=XX": [],
                        "SSINS_POL=XY": [],
                        "SSINS_POL=YY": [],
                        "EAVILS_POL=XX": [],
                        "EAVILS_POL=XY": [],
                        "EAVILS_POL=YY": [],
                    }
                    # Store frequency information for this shape
                    all_data_2d[shape_key]["freq_info"] = {
                        "crval1": crval1,
                        "cdelt1": cdelt1,
                        "crpix1": crpix1,
                    }

                all_data_2d[shape_key]["AO_FLAG_METRICS"].append(ao_flag_aligned)
                all_data_2d[shape_key]["SSINS_POL=XX"].append(ssins_xx)
                all_data_2d[shape_key]["SSINS_POL=XY"].append(ssins_xy)
                all_data_2d[shape_key]["SSINS_POL=YY"].append(ssins_yy)
                all_data_2d[shape_key]["EAVILS_POL=XX"].append(eavils_xx_aligned)
                all_data_2d[shape_key]["EAVILS_POL=XY"].append(eavils_xy_aligned)
                all_data_2d[shape_key]["EAVILS_POL=YY"].append(eavils_yy_aligned)

                # Store times for waterfall plots (remove SSINS offset to fix aliasing)
                # All datasets use the same time grid in waterfall plots
                all_times_2d[shape_key]["AO_FLAG_METRICS"].append(gps_times)
                all_times_2d[shape_key]["SSINS_POL=XX"].append(
                    gps_times
                )  # No offset for waterfall
                all_times_2d[shape_key]["SSINS_POL=XY"].append(gps_times)
                all_times_2d[shape_key]["SSINS_POL=YY"].append(gps_times)
                all_times_2d[shape_key]["EAVILS_POL=XX"].append(gps_times)
                all_times_2d[shape_key]["EAVILS_POL=XY"].append(gps_times)
                all_times_2d[shape_key]["EAVILS_POL=YY"].append(gps_times)

                files_processed += 1

        except Exception as e:
            continue

    print(f"Successfully processed {files_processed} files")

    # Store original concatenated data for time alignment
    original_data = {}
    for key in all_data:
        if all_data[key]:
            original_data[key] = np.concatenate(all_data[key])
        else:
            original_data[key] = np.array([])  # Empty array for no data

    # Find the global time reference and range across all data
    all_gps_times = []
    for times_list in all_times:
        all_gps_times.extend(times_list)

    for shape_key in all_times_2d:
        for col_name in all_times_2d[shape_key]:
            if all_times_2d[shape_key][col_name]:
                for times_list in all_times_2d[shape_key][col_name]:
                    all_gps_times.extend(times_list)

    global_time_start = min(all_gps_times)
    global_time_end = max(all_gps_times)

    # Create common time grid with fine resolution (0.5s to match highest resolution data)
    time_step = 0.5  # seconds
    common_times = np.arange(global_time_start, global_time_end + time_step, time_step)

    # Create arrays to hold data aligned to common time grid
    aligned_data = {}
    for key in original_data:
        aligned_data[key] = np.full(len(common_times), np.nan)

    # Fill in the data at the appropriate time indices
    sample_idx = 0
    for i, times_list in enumerate(all_times):
        n_samples = len(times_list)

        # Find closest indices in common time grid
        for j, gps_time in enumerate(times_list):
            time_idx = int(round((gps_time - global_time_start) / time_step))
            if 0 <= time_idx < len(common_times):
                for key in original_data:
                    if sample_idx + j < len(original_data[key]):
                        aligned_data[key][time_idx] = original_data[key][sample_idx + j]

        sample_idx += n_samples

    # Check if we have valid data
    if not any(np.sum(~np.isnan(v)) > 0 for v in aligned_data.values()):
        exit(1)

    # Convert common times to relative minutes
    time_minutes_common = (common_times - global_time_start) / 60.0

    # Create the plot
    fig, axes = plt.subplots(7, 1, figsize=(15, 12), sharex=True)
    fig.suptitle(name, fontsize=6, fontweight="bold")

    column_names = [
        "AO_FLAG_METRICS",
        "SSINS_POL=XX",
        "SSINS_POL=XY",
        "SSINS_POL=YY",
        "EAVILS_POL=XX",
        "EAVILS_POL=XY",
        "EAVILS_POL=YY",
    ]

    colors = ["blue", "red", "orange", "green", "purple", "brown", "pink"]

    for i, (col_name, color) in enumerate(zip(column_names, colors)):
        if len(aligned_data[col_name]) > 0:
            axes[i].plot(
                time_minutes_common,
                aligned_data[col_name],
                color=color,
                alpha=0.7,
                linewidth=0.5,
            )
            # Set y-axis limits to show variation better
            data_range = np.nanmax(aligned_data[col_name]) - np.nanmin(
                aligned_data[col_name]
            )
            if data_range > 0:
                margin = data_range * 0.05
                y_min = np.nanquantile(aligned_data[col_name], 0.01) - margin
                y_max = np.nanquantile(aligned_data[col_name], 0.99) + margin
                axes[i].set_ylim(y_min, y_max)
        axes[i].set_ylabel(col_name, fontweight="bold")
        axes[i].grid(True, alpha=0.3)
        axes[i].set_xlim(time_minutes_common[0], time_minutes_common[-1])

    # Set x-axis label
    axes[-1].set_xlabel("Time (minutes from start)", fontweight="bold")

    plt.tight_layout()
    plot_filename = f"metrics_timeseries_{name}.png"
    plt.savefig(plot_filename, dpi=150, bbox_inches="tight")
    if show:
        plt.show()

    print(realpath(plot_filename))

    # Create waterfall plots
    # Process each shape group separately
    for shape_key in all_data_2d:
        # Find time range for this shape group
        all_times_shape = []
        for col_name in all_times_2d[shape_key]:
            if all_times_2d[shape_key][col_name]:
                for times_list in all_times_2d[shape_key][col_name]:
                    all_times_shape.extend(times_list)

        if not all_times_shape:
            continue

        shape_time_start = min(all_times_shape)
        shape_time_end = max(all_times_shape)

        # Get time step from shape key
        if "591time" in shape_key:
            shape_time_step = 0.5  # seconds
        else:
            shape_time_step = 2.0  # seconds

        # Create time grid for this shape
        shape_times = np.arange(
            shape_time_start, shape_time_end + shape_time_step, shape_time_step
        )

        # Get frequency dimensions
        n_freq = None
        for col_name in all_data_2d[shape_key]:
            if all_data_2d[shape_key][col_name]:
                n_freq = all_data_2d[shape_key][col_name][0].shape[1]
                break

        if n_freq is None:
            continue

        # Get frequency information
        freq_info = all_data_2d[shape_key].get("freq_info", {})
        crval1 = freq_info.get("crval1", 167040000.0)  # Hz
        cdelt1 = freq_info.get("cdelt1", 20000.0)  # Hz
        crpix1 = freq_info.get("crpix1", 1.0)

        # Calculate frequency array in MHz
        freq_channels = np.arange(1, n_freq + 1)  # 1-based indexing
        freq_hz = crval1 + (freq_channels - crpix1) * cdelt1
        freq_mhz = freq_hz / 1e6

        # Create 2D grids for waterfall data
        waterfall_data = {}
        waterfall_times = {}

        for col_name in all_data_2d[shape_key]:
            if col_name == "freq_info":  # Skip frequency info
                continue
            if all_data_2d[shape_key][col_name]:
                # Create 2D array with NaNs
                waterfall_data[col_name] = np.full((len(shape_times), n_freq), np.nan)

                # Fill in data where it exists
                file_idx = 0
                for data_2d, times_2d in zip(
                    all_data_2d[shape_key][col_name], all_times_2d[shape_key][col_name]
                ):
                    for i, gps_time in enumerate(times_2d):
                        time_idx = int(
                            round((gps_time - shape_time_start) / shape_time_step)
                        )
                        if 0 <= time_idx < len(shape_times) and i < data_2d.shape[0]:
                            waterfall_data[col_name][time_idx, :] = data_2d[i, :]

        if not waterfall_data:
            continue

        # Create waterfall plot for this shape group
        fig2, axes2 = plt.subplots(
            1, 7, figsize=(28, 8), sharex=True, sharey=True, tight_layout=True, dpi=100
        )
        fig2.suptitle(name, fontsize=6, fontweight="bold")

        for i, (col_name, color) in enumerate(zip(column_names, colors)):
            if col_name in waterfall_data and len(waterfall_data[col_name]) > 0:
                data_2d = waterfall_data[col_name]

                # Convert times to minutes from global start for consistent plotting
                time_minutes_2d = (shape_times - global_time_start) / 60.0

                # Create the waterfall plot (time on y-axis, frequency on x-axis)
                # Apply square root response function
                # data_2d_norm = np.sign(data_2d) * np.sqrt(np.abs(data_2d))
                data_2d_norm = data_2d
                vmin = np.nanquantile(data_2d_norm, 0.05)
                vmax = np.nanquantile(data_2d_norm, 0.95)
                im = axes2[i].imshow(
                    data_2d_norm,
                    aspect="auto",
                    origin="lower",
                    extent=[
                        freq_mhz[0],
                        freq_mhz[-1],
                        time_minutes_2d[0],
                        time_minutes_2d[-1],
                    ],
                    cmap="viridis",
                    interpolation="nearest",
                    vmin=vmin,
                    vmax=vmax,
                )

                # Add colorbar for this subplot at the bottom
                plt.colorbar(
                    im, ax=axes2[i], orientation="horizontal", pad=0.1, shrink=0.8
                )

            axes2[i].set_title(col_name, fontweight="bold")
            axes2[i].set_xlabel("Frequency (MHz)")
            if i == 0:
                axes2[i].set_ylabel("Time (minutes from start)")

        plt.tight_layout()
        plot_filename = f"metrics_waterfall_{name}_{shape_key}.png"
        plt.savefig(plot_filename, dpi=150, bbox_inches="tight")
        if show:
            plt.show()

        print(realpath(plot_filename))

    # Process additional metrics data
    # Process AUTO_POL data (time series)
    auto_pol_aligned = {}
    if additional_times:
        add_time_start = min([t for times_list in additional_times for t in times_list])
        add_time_end = max([t for times_list in additional_times for t in times_list])
        add_common_times = np.arange(
            add_time_start, add_time_end + time_step, time_step
        )

        for key in ["AUTO_POL=XX", "AUTO_POL=YY", "AUTO_POL=XY"]:
            if additional_data[key]:
                auto_pol_aligned[key] = np.full(len(add_common_times), np.nan)
                sample_idx = 0
                for i, times_list in enumerate(additional_times):
                    if i < len(additional_data[key]):
                        data_array = additional_data[key][i]
                        for j, gps_time in enumerate(times_list):
                            if j < len(data_array):
                                time_idx = int(
                                    round((gps_time - add_time_start) / time_step)
                                )
                                if 0 <= time_idx < len(add_common_times):
                                    auto_pol_aligned[key][time_idx] = data_array[j]

    # Process AUTO_POL 2D data (waterfall plots)
    if additional_data_2d["AUTO_POL=XX"]:  # Check if we have any AUTO_POL data
        # Get dimensions from first file
        first_auto_data = additional_data_2d["AUTO_POL=XX"][0]
        n_antennas, n_freq_auto = first_auto_data.shape

        # Get frequency info (same as main data)
        freq_hz_auto = crval1 + (np.arange(1, n_freq_auto + 1) - crpix1) * cdelt1
        freq_mhz_auto = freq_hz_auto / 1e6

        # Get file times
        auto_file_times = {}
        for hdu_name in ["AUTO_POL=XX", "AUTO_POL=YY", "AUTO_POL=XY"]:
            if additional_data_2d[hdu_name]:
                auto_file_times[hdu_name] = np.array(additional_times_2d[hdu_name])

        # Create antenna-specific waterfall plots (show first 12 antennas as examples)
        max_antennas_to_plot = min(12, n_antennas)

        for hdu_name in ["AUTO_POL=XX", "AUTO_POL=YY", "AUTO_POL=XY"]:
            if additional_data_2d[hdu_name]:
                # Get file times and convert to time grid
                file_times = np.array(additional_times_2d[hdu_name])

                # Create time grid that aligns with global time grid
                # Each file represents ~5 minutes, so use 5-minute bins
                time_step_minutes = 5.0  # minutes
                time_step_seconds = time_step_minutes * 60.0  # seconds

                # Create coarse time grid for files
                file_time_start = np.min(file_times)
                file_time_end = np.max(file_times)
                file_time_grid = np.arange(
                    file_time_start,
                    file_time_end + time_step_seconds,
                    time_step_seconds,
                )

                # Create 2D grid for each antenna: (n_time_bins, n_freq)
                n_time_bins = len(file_time_grid)
                antenna_grids = {}

                for ant_idx in range(max_antennas_to_plot):
                    antenna_grids[ant_idx] = np.full((n_time_bins, n_freq_auto), np.nan)

                # Fill in data at appropriate time indices
                all_files_data = np.array(
                    additional_data_2d[hdu_name]
                )  # (n_files, n_antennas, n_freq)

                for file_idx, file_time in enumerate(file_times):
                    # Find closest time bin
                    time_bin_idx = np.argmin(np.abs(file_time_grid - file_time))

                    for ant_idx in range(max_antennas_to_plot):
                        if ant_idx < n_antennas:
                            antenna_grids[ant_idx][time_bin_idx, :] = all_files_data[
                                file_idx, ant_idx, :
                            ]

                # Create subplots for multiple antennas
                fig, axes = plt.subplots(
                    3, 4, figsize=(20, 12), sharex=True, sharey=True
                )
                fig.suptitle(
                    f"{name} - {hdu_name} by Antenna", fontsize=10, fontweight="bold"
                )
                axes = axes.flatten()

                # Convert file time grid to minutes from global start
                time_minutes_grid = (file_time_grid - global_time_start) / 60.0

                for ant_idx in range(max_antennas_to_plot):
                    if ant_idx < n_antennas:
                        # Get data for this antenna
                        antenna_data = antenna_grids[ant_idx]  # (n_time_bins, n_freq)

                        # Apply quantile scaling
                        vmin = np.nanquantile(antenna_data, 0.05)
                        vmax = np.nanquantile(antenna_data, 0.95)

                        # Plot: time bins on y-axis, frequency on x-axis
                        extent = [
                            freq_mhz_auto[0],
                            freq_mhz_auto[-1],
                            time_minutes_grid[0],
                            time_minutes_grid[-1],
                        ]
                        im = axes[ant_idx].imshow(
                            antenna_data,
                            aspect="auto",
                            origin="lower",
                            extent=extent,
                            cmap="viridis",
                            interpolation="nearest",
                            vmin=vmin,
                            vmax=vmax,
                        )

                        # Compress the y-axis to reduce vertical space, expand frequency axis
                        axes[ant_idx].set_aspect(
                            aspect=0.3
                        )  # Make it much wider than tall
                        axes[ant_idx].set_title(f"Antenna {ant_idx}", fontsize=8)

                # Add colorbar on the right side
                plt.tight_layout()
                cbar = fig.colorbar(
                    im, ax=axes, orientation="vertical", pad=0.02, shrink=0.8
                )
                cbar.set_label(f"{hdu_name} Amplitude", fontsize=8)

                auto_pol_plot_filename = (
                    f"auto_pol_antennas_{hdu_name.replace('=', '_')}_{name}.png"
                )
                plt.savefig(auto_pol_plot_filename, dpi=150, bbox_inches="tight")
                if show:
                    plt.show()

                print(realpath(auto_pol_plot_filename))

    else:
        print("No AUTO_POL data found")

    # Check if we have any AMP_FP polarization data
    amp_fp_base_names = [
        "EAVILS_MEAN_AMP_FP",
        "EAVILS_SQRT_MEAN_VAR_AMP_FP",
        "SSINS_DIFF_MEAN_AMP_FP",
    ]
    pol_suffixes = ["_XX", "_YY", "_XY"]

    found_amp_fp = False
    for base_name in amp_fp_base_names:
        for pol_suffix in pol_suffixes:
            pol_key = base_name + pol_suffix
            if pol_key in additional_data_2d and additional_data_2d[pol_key]:
                found_amp_fp = True
                break
        if found_amp_fp:
            break

    if found_amp_fp:
        # Get frequency info (use same as main data)
        n_freq = 768  # From the main data
        freq_hz = crval1 + (np.arange(1, n_freq + 1) - crpix1) * cdelt1
        freq_mhz = freq_hz / 1e6

        # Create 3x3 subplot grid (3 rows for pols × 3 columns for metrics)
        fig4, axes4 = plt.subplots(3, 3, figsize=(24, 12), sharex=True, sharey=True)
        fig4.suptitle(
            f"{name} - Metrics by Polarization", fontsize=10, fontweight="bold"
        )

        # Process each metric and polarization combination
        for col_idx, base_name in enumerate(amp_fp_base_names):
            for row_idx, pol_suffix in enumerate(pol_suffixes):
                pol_key = base_name + pol_suffix

                if pol_key in additional_data_2d and additional_data_2d[pol_key]:
                    # Get file times and spectra
                    file_times = np.array(additional_times_2d[pol_key])  # (n_files,)
                    spectra_list = additional_data_2d[
                        pol_key
                    ]  # List of (n_freq,) arrays

                    # Create time grid that aligns with global time grid
                    # Each file represents ~5 minutes, so use 5-minute bins
                    time_step_minutes = 5.0  # minutes
                    time_step_seconds = time_step_minutes * 60.0  # seconds

                    # Create coarse time grid for files
                    file_time_start = np.min(file_times)
                    file_time_end = np.max(file_times)
                    file_time_grid = np.arange(
                        file_time_start,
                        file_time_end + time_step_seconds,
                        time_step_seconds,
                    )

                    # Create 2D grid: (n_time_bins, n_freq)
                    n_time_bins = len(file_time_grid)
                    spectra_grid = np.full((n_time_bins, n_freq), np.nan)

                    # Fill in data at appropriate time indices
                    for file_idx, file_time in enumerate(file_times):
                        # Find closest time bin
                        time_bin_idx = np.argmin(np.abs(file_time_grid - file_time))
                        if file_idx < len(spectra_list):
                            spectra_grid[time_bin_idx, :] = spectra_list[file_idx]

                    # Convert file time grid to minutes from global start
                    time_minutes_grid = (file_time_grid - global_time_start) / 60.0

                    # Apply quantile scaling
                    vmin = np.nanquantile(spectra_grid, 0.05)
                    vmax = np.nanquantile(spectra_grid, 0.95)

                    # Plot: time bins on y-axis, frequency on x-axis
                    extent = [
                        freq_mhz[0],
                        freq_mhz[-1],
                        time_minutes_grid[0],
                        time_minutes_grid[-1],
                    ]
                    im = axes4[row_idx, col_idx].imshow(
                        spectra_grid,
                        aspect="auto",
                        origin="lower",
                        extent=extent,
                        cmap="viridis",
                        interpolation="nearest",
                        vmin=vmin,
                        vmax=vmax,
                    )

                    # Compress the y-axis to reduce vertical space, expand frequency axis
                    axes4[row_idx, col_idx].set_aspect(aspect=0.3)
                else:
                    # No data for this combination
                    axes4[row_idx, col_idx].text(
                        0.5,
                        0.5,
                        f"No data for\n{base_name}\n{pol_suffix[1:]}",
                        transform=axes4[row_idx, col_idx].transAxes,
                        ha="center",
                        va="center",
                        fontsize=8,
                    )

                # Set titles and labels
                if row_idx == 0:  # Top row
                    axes4[row_idx, col_idx].set_title(
                        base_name.replace("_", " "), fontsize=9, fontweight="bold"
                    )
                if col_idx == 0:  # Left column
                    axes4[row_idx, col_idx].set_ylabel(
                        f"{pol_suffix[1:]} Pol\nTime (min)",
                        fontsize=9,
                        fontweight="bold",
                    )
                if row_idx == 2:  # Bottom row
                    axes4[row_idx, col_idx].set_xlabel(
                        "Frequency (MHz)", fontsize=9, fontweight="bold"
                    )

        # Add single colorbar on the right side for all subplots
        plt.tight_layout()
        cbar = fig4.colorbar(im, ax=axes4, orientation="vertical", pad=0.02, shrink=0.8)
        cbar.set_label("Amplitude", fontsize=10)

        amp_fp_grid_filename = f"amp_fp_grid_{name}.png"
        plt.savefig(amp_fp_grid_filename, dpi=150, bbox_inches="tight")
        if show:
            plt.show()
        print(realpath(amp_fp_grid_filename))
    else:
        print("No AMP_FP polarization data found")


if __name__ == "__main__":
    main()
