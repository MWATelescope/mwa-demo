#!/usr/bin/env python

"""
Plot the metrics files produced by Birli --metrics-out.

Can be used as a CLI tool or imported for individual plotting functions.

CLI usage:
. .venv/bin/activate && demo/81_metrics.py --name foo bar.fits ...

Import usage:
from demo.metrics_81 import load_metrics_data, plot_timeseries, plot_waterfall
data = load_metrics_data(files, metafits_path)
plot_timeseries(data, name, show=True)
"""

import argparse
from os.path import realpath
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from astropy.io import fits


def load_metafits_receiver_mapping(metafits_path):
    """Load antenna to receiver mapping from metafits file.

    Returns:
        dict: Mapping from antenna name to receiver number
    """
    antenna_to_receiver = {}

    try:
        with fits.open(metafits_path) as hdul:
            if "TILEDATA" not in [hdu.name for hdu in hdul]:
                print(f"Warning: No TILEDATA HDU found in {metafits_path}")
                return {}

            tiledata = hdul["TILEDATA"].data

            # Create mapping from tile name to receiver
            # Each tile appears twice (for X and Y pol), so take unique tiles
            seen_tiles = set()
            for row in tiledata:
                tile_name = row["TileName"]
                if isinstance(tile_name, bytes):
                    tile_name = tile_name.decode("utf-8")

                if tile_name not in seen_tiles:
                    rx_num = int(row["Rx"])
                    antenna_to_receiver[tile_name] = rx_num
                    seen_tiles.add(tile_name)

            print(
                f"Loaded receiver mapping for {len(antenna_to_receiver)} antennas from metafits"
            )
            return antenna_to_receiver

    except Exception as e:
        print(f"Error reading metafits file {metafits_path}: {e}")
        return {}


def load_metrics_data(metrics_files, metafits_path=None):
    """Load and process metrics data from FITS files.

    Args:
        metrics_files: List of FITS file paths
        metafits_path: Optional path to metafits file for receiver mapping

    Returns:
        dict: Processed data structure containing all metrics and metadata
    """
    # Load metafits receiver mapping if provided
    metafits_receiver_mapping = {}
    if metafits_path:
        metafits_receiver_mapping = load_metafits_receiver_mapping(metafits_path)
    else:
        print(
            "WARNING: No metafits file provided. Using incorrect RX_NUMBER from FITS headers."
        )

    print(f"Found {len(metrics_files)} metrics files")

    # Initialize data storage structures
    all_data = {
        "AO_FLAG_METRICS": [],
        "SSINS_POL=XX": [],
        "SSINS_POL=XY": [],
        "SSINS_POL=YY": [],
        "EAVILS_POL=XX": [],
        "EAVILS_POL=XY": [],
        "EAVILS_POL=YY": [],
    }
    all_times = []

    additional_data = {
        "AUTO_POL=XX": [],
        "AUTO_POL=YY": [],
        "AUTO_POL=XY": [],
        "EAVILS_MEAN_AMP_FP": [],
        "EAVILS_SQRT_MEAN_VAR_AMP_FP": [],
        "SSINS_DIFF_MEAN_AMP_FP": [],
    }
    additional_times = []

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

    auto_power_ant_data = {}
    auto_power_ant_times = {}
    auto_sub_ant_data = {}
    auto_sub_ant_times = {}
    auto_sub_ant_metadata = {}
    antenna_table = {}
    auto_delay_pol_data = {}
    auto_delay_pol_times = {}
    all_data_2d = {}
    all_times_2d = {}

    # Store WCS info from first valid file
    wcs_info = {}

    files_processed = 0
    for filename in metrics_files:
        stem_tokens = Path(filename).stem.split("_")
        # find the first token that is a 10 digit number
        gps_time = None
        for token in stem_tokens:
            if len(token) == 10 and token.isdigit():
                gps_time = int(token)
                break
        if gps_time is None:
            print(f"Warning: Could not parse GPS time from {filename}")

        try:
            with fits.open(filename) as hdul:
                required_hdus = [
                    "AO_FLAG_METRICS",
                    "SSINS_POL=XX",
                    "SSINS_POL=XY",
                    "SSINS_POL=YY",
                    "EAVILS_POL=XX",
                    "EAVILS_POL=XY",
                    "EAVILS_POL=YY",
                ]

                additional_hdus = [
                    "AUTO_POL=XX",
                    "AUTO_POL=YY",
                    "AUTO_POL=XY",
                    "EAVILS_MEAN_AMP_FP",
                    "EAVILS_SQRT_MEAN_VAR_AMP_FP",
                    "SSINS_DIFF_MEAN_AMP_FP",
                ]

                # Find dynamic HDUs
                auto_power_ant_hdus = [
                    hdu.name for hdu in hdul if hdu.name.startswith("AUTO_POWER_ANT=")
                ]
                auto_sub_ant_hdus = [
                    hdu.name
                    for hdu in hdul
                    if hasattr(hdu, "header") and "ANT_ID" in hdu.header
                ]
                auto_delay_pol_hdus = [
                    hdu.name for hdu in hdul if hdu.name.startswith("AUTO_DELAY_POL=")
                ]

                missing_hdus = [
                    hdu_name
                    for hdu_name in required_hdus
                    if hdu_name not in [h.name for h in hdul]
                ]
                if missing_hdus:
                    continue

                # Extract WCS and data
                ao_hdu = hdul["AO_FLAG_METRICS"]
                header = ao_hdu.header

                crval2 = header.get("CRVAL2", gps_time)
                cdelt2 = header.get("CDELT2", 2.0)
                crpix2 = header.get("CRPIX2", 1.0)
                crval1 = header.get("CRVAL1", 167040000.0)
                cdelt1 = header.get("CDELT1", 20000.0)
                crpix1 = header.get("CRPIX1", 1.0)

                # Store WCS info from first file
                if not wcs_info:
                    wcs_info = {
                        "crval1": crval1,  # Frequency reference value (Hz)
                        "cdelt1": cdelt1,  # Frequency step (Hz)
                        "crpix1": crpix1,  # Frequency reference pixel
                        "crval2": crval2,  # Time reference value (GPS seconds)
                        "cdelt2": cdelt2,  # Time step (seconds)
                        "crpix2": crpix2,  # Time reference pixel
                    }

                # Extract required HDU data
                ao_flag = hdul["AO_FLAG_METRICS"].data
                ssins_xx = hdul["SSINS_POL=XX"].data
                ssins_xy = hdul["SSINS_POL=XY"].data
                ssins_yy = hdul["SSINS_POL=YY"].data
                eavils_xx = hdul["EAVILS_POL=XX"].data
                eavils_xy = hdul["EAVILS_POL=XY"].data
                eavils_yy = hdul["EAVILS_POL=YY"].data

                # Process time alignment
                n_time_samples = ssins_xx.shape[0]
                pixel_indices = np.arange(1, n_time_samples + 1)
                gps_times = crval2 + (pixel_indices - crpix2) * cdelt2

                ao_flag_aligned = ao_flag[:n_time_samples, :]
                eavils_xx_aligned = eavils_xx[:n_time_samples, :]
                eavils_xy_aligned = eavils_xy[:n_time_samples, :]
                eavils_yy_aligned = eavils_yy[:n_time_samples, :]

                # Store 1D mean data
                all_data["AO_FLAG_METRICS"].append(np.nanmean(ao_flag_aligned, axis=1))
                all_data["SSINS_POL=XX"].append(np.nanmean(ssins_xx, axis=1))
                all_data["SSINS_POL=XY"].append(np.nanmean(ssins_xy, axis=1))
                all_data["SSINS_POL=YY"].append(np.nanmean(ssins_yy, axis=1))
                all_data["EAVILS_POL=XX"].append(np.nanmean(eavils_xx_aligned, axis=1))
                all_data["EAVILS_POL=XY"].append(np.nanmean(eavils_xy_aligned, axis=1))
                all_data["EAVILS_POL=YY"].append(np.nanmean(eavils_yy_aligned, axis=1))
                all_times.append(gps_times)

                # Process additional HDUs
                for hdu_name in additional_hdus:
                    try:
                        additional_hdu_data = hdul[hdu_name].data

                        if hdu_name.startswith("AUTO_POL="):
                            additional_data_2d[hdu_name].append(additional_hdu_data)
                            additional_times_2d[hdu_name].append(gps_times[0])
                            mean_data = np.nanmean(additional_hdu_data)
                            mean_array = np.full(n_time_samples, mean_data)
                            additional_data[hdu_name].append(mean_array)

                        elif "_AMP_FP" in hdu_name:
                            n_pols = min(3, additional_hdu_data.shape[1])
                            for pol_idx in range(n_pols):
                                pol_names = ["_XX", "_YY", "_XY"]
                                pol_key = hdu_name + pol_names[pol_idx]

                                if pol_key not in additional_data_2d:
                                    additional_data_2d[pol_key] = []
                                    additional_times_2d[pol_key] = []

                                pol_spectrum = additional_hdu_data[:, pol_idx]
                                additional_data_2d[pol_key].append(pol_spectrum)
                                additional_times_2d[pol_key].append(gps_times[0])

                    except KeyError:
                        # Handle missing data
                        if hdu_name.startswith("AUTO_POL="):
                            additional_data[hdu_name].append(
                                np.full(n_time_samples, np.nan)
                            )
                            nan_array_2d = np.full(
                                (128, ao_flag_aligned.shape[1]), np.nan
                            )
                            additional_data_2d[hdu_name].append(nan_array_2d)
                            additional_times_2d[hdu_name].append(gps_times[0])

                # Process AUTO_POWER_ANT HDUs
                for hdu_name in auto_power_ant_hdus:
                    try:
                        ant_data = hdul[hdu_name].data
                        antenna_name = hdu_name.replace("AUTO_POWER_ANT=", "")
                        if antenna_name not in auto_power_ant_data:
                            auto_power_ant_data[antenna_name] = []
                            auto_power_ant_times[antenna_name] = []
                        auto_power_ant_data[antenna_name].append(ant_data)
                        auto_power_ant_times[antenna_name].append(gps_times)
                    except KeyError:
                        pass

                # Process AUTO_SUB_ANT HDUs
                for hdu_name in auto_sub_ant_hdus:
                    try:
                        hdu_data = hdul[hdu_name].data
                        hdu_header = hdul[hdu_name].header
                        ant_id = hdu_header.get("ANT_ID")
                        if ant_id is not None:
                            if ant_id not in auto_sub_ant_data:
                                auto_sub_ant_data[ant_id] = []
                                auto_sub_ant_times[ant_id] = []
                                auto_sub_ant_metadata[ant_id] = {}
                            auto_sub_ant_data[ant_id].append(hdu_data)
                            auto_sub_ant_times[ant_id].append(gps_times)
                            auto_sub_ant_metadata[ant_id]["filename"] = filename
                            auto_sub_ant_metadata[ant_id]["hdu_name"] = hdu_name
                            auto_sub_ant_metadata[ant_id]["header"] = hdu_header

                            # Build antenna table
                            if ant_id not in antenna_table:
                                ant_info = {"HDU_NAME": hdu_name}
                                key_fields = [
                                    "ANTNAME",
                                    "ANT_ID",
                                    "ANT_NUM",
                                    "ANT_TYPE",
                                    "RX_NUMBER",
                                    "RX_SLOT",
                                    "RX_TYPE",
                                ]
                                for key in key_fields:
                                    if key in hdu_header:
                                        value = hdu_header[key]
                                        if isinstance(value, str):
                                            value = value.strip()
                                        ant_info[key] = value

                                for key in hdu_header:
                                    if key.startswith("HIERARCH"):
                                        clean_key = key.replace("HIERARCH ", "")
                                        value = hdu_header[key]
                                        if isinstance(value, str):
                                            value = value.strip()
                                        ant_info[clean_key] = value

                                for key in ["OBSGEO-X", "OBSGEO-Y", "OBSGEO-Z"]:
                                    if key in hdu_header:
                                        ant_info[key] = hdu_header[key]

                                antenna_table[ant_id] = ant_info
                    except KeyError:
                        pass

                # Process AUTO_DELAY_POL HDUs
                for hdu_name in auto_delay_pol_hdus:
                    try:
                        hdu_data = hdul[hdu_name].data
                        pol_name = hdu_name.replace("AUTO_DELAY_POL=", "")
                        if pol_name not in auto_delay_pol_data:
                            auto_delay_pol_data[pol_name] = []
                            auto_delay_pol_times[pol_name] = []
                        auto_delay_pol_data[pol_name].append(hdu_data)
                        auto_delay_pol_times[pol_name].append(gps_time)
                    except KeyError:
                        pass

                additional_times.append(gps_times)

                # Store 2D data for waterfall plots
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

                for col_name in all_times_2d[shape_key]:
                    all_times_2d[shape_key][col_name].append(gps_times)

                files_processed += 1

        except Exception as e:
            continue

    print(f"Successfully processed {files_processed} files")

    if antenna_table:
        print(f"Found antenna information for {len(antenna_table)} antennas")

    # Process and align data for consistent time grids
    original_data = {}
    for key in all_data:
        if all_data[key]:
            original_data[key] = np.concatenate(all_data[key])
        else:
            original_data[key] = np.array([])

    # Find global time reference
    all_gps_times = []
    for times_list in all_times:
        all_gps_times.extend(times_list)

    for shape_key in all_times_2d:
        for col_name in all_times_2d[shape_key]:
            if all_times_2d[shape_key][col_name]:
                for times_list in all_times_2d[shape_key][col_name]:
                    all_gps_times.extend(times_list)

    if all_gps_times:
        global_time_start = min(all_gps_times)
        global_time_end = max(all_gps_times)
        time_step = 0.5
        common_times = np.arange(
            global_time_start, global_time_end + time_step, time_step
        )

        # Create aligned data
        aligned_data = {}
        for key in original_data:
            aligned_data[key] = np.full(len(common_times), np.nan)

        sample_idx = 0
        for i, times_list in enumerate(all_times):
            n_samples = len(times_list)
            for j, gps_time in enumerate(times_list):
                time_idx = int(round((gps_time - global_time_start) / time_step))
                if 0 <= time_idx < len(common_times):
                    for key in original_data:
                        if sample_idx + j < len(original_data[key]):
                            aligned_data[key][time_idx] = original_data[key][
                                sample_idx + j
                            ]
            sample_idx += n_samples
    else:
        common_times = np.array([])
        aligned_data = {}

    return {
        "aligned_data": aligned_data,
        "common_times": common_times,
        "all_data_2d": all_data_2d,
        "all_times_2d": all_times_2d,
        "additional_data_2d": additional_data_2d,
        "additional_times_2d": additional_times_2d,
        "auto_power_ant_data": auto_power_ant_data,
        "auto_power_ant_times": auto_power_ant_times,
        "auto_sub_ant_data": auto_sub_ant_data,
        "auto_sub_ant_times": auto_sub_ant_times,
        "auto_sub_ant_metadata": auto_sub_ant_metadata,
        "antenna_table": antenna_table,
        "auto_delay_pol_data": auto_delay_pol_data,
        "auto_delay_pol_times": auto_delay_pol_times,
        "metafits_receiver_mapping": metafits_receiver_mapping,
        "files_processed": files_processed,
        "wcs_info": wcs_info,
    }


def get_antenna_display_name(ant_id, antenna_table):
    """Get a nice display name for an antenna from the antenna table."""
    if ant_id in antenna_table:
        info = antenna_table[ant_id]
        ant_name = info.get("ANTNAME", f"ANT_{ant_id}")
        ant_num = info.get("ANT_NUM", "")
        if ant_num:
            return f"{ant_name} (#{ant_num})"
        else:
            return f"{ant_name} (ID={ant_id})"
    else:
        return f"ANT_ID={ant_id}"


def plot_timeseries(data, name, show=False, save=True):
    """Plot 1D timeseries for main metrics.

    Args:
        data: Data dict from load_metrics_data()
        name: Plot name/title
        show: Whether to show plot interactively
        save: Whether to save plot to file

    Returns:
        str: Path to saved plot file (if save=True)
    """
    aligned_data = data["aligned_data"]
    common_times = data["common_times"]

    if not any(np.sum(~np.isnan(v)) > 0 for v in aligned_data.values()):
        print("No valid data for timeseries plot")
        return None

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
            valid_mask = ~np.isnan(aligned_data[col_name])
            if np.any(valid_mask):
                axes[i].plot(
                    common_times[valid_mask],
                    aligned_data[col_name][valid_mask],
                    color=color,
                    alpha=0.7,
                    linewidth=0.5,
                    marker=".",
                    markersize=1,
                )
                valid_data = aligned_data[col_name][valid_mask]
                data_range = np.max(valid_data) - np.min(valid_data)
                if data_range > 0:
                    margin = data_range * 0.1
                    y_min = np.min(valid_data) - margin
                    y_max = np.max(valid_data) + margin
                    axes[i].set_ylim(y_min, y_max)
                else:
                    center_val = np.mean(valid_data)
                    if abs(center_val) > 1e-10:
                        axes[i].set_ylim(center_val * 0.95, center_val * 1.05)
                    else:
                        axes[i].set_ylim(-1e-10, 1e-10)
            else:
                axes[i].text(
                    0.5,
                    0.5,
                    f"No valid data\nfor {col_name}",
                    transform=axes[i].transAxes,
                    ha="center",
                    va="center",
                )
        axes[i].set_ylabel(col_name, fontweight="bold")
        axes[i].grid(True, alpha=0.3)
        if len(common_times) > 0:
            axes[i].set_xlim(common_times[0], common_times[-1])

    axes[-1].set_xlabel("GPS Time (seconds)", fontweight="bold")

    plt.tight_layout()

    filename = None
    if save:
        filename = f"metrics_timeseries_{name}.png"
        plt.savefig(filename, dpi=150, bbox_inches="tight")
        print(realpath(filename))

    if show:
        plt.show()
    else:
        plt.close()

    return filename


def plot_waterfall(data, name, show=False, save=True):
    """Plot 2D waterfall plots for main metrics.

    Args:
        data: Data dict from load_metrics_data()
        name: Plot name/title
        show: Whether to show plot interactively
        save: Whether to save plot to file

    Returns:
        list: Paths to saved plot files (if save=True)
    """
    all_data_2d = data["all_data_2d"]
    all_times_2d = data["all_times_2d"]

    filenames = []
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

    for shape_key in all_data_2d:
        all_times_shape = []
        for col_name in all_times_2d[shape_key]:
            if all_times_2d[shape_key][col_name]:
                for times_list in all_times_2d[shape_key][col_name]:
                    all_times_shape.extend(times_list)

        if not all_times_shape:
            continue

        shape_time_start = min(all_times_shape)
        shape_time_end = max(all_times_shape)

        if "591time" in shape_key:
            shape_time_step = 0.5
        else:
            shape_time_step = 2.0

        shape_times = np.arange(
            shape_time_start, shape_time_end + shape_time_step, shape_time_step
        )

        n_freq = None
        for col_name in all_data_2d[shape_key]:
            if all_data_2d[shape_key][col_name]:
                n_freq = all_data_2d[shape_key][col_name][0].shape[1]
                break

        if n_freq is None:
            continue

        freq_info = all_data_2d[shape_key].get("freq_info", {})
        crval1 = freq_info.get("crval1", 167040000.0)
        cdelt1 = freq_info.get("cdelt1", 20000.0)
        crpix1 = freq_info.get("crpix1", 1.0)

        freq_channels = np.arange(1, n_freq + 1)
        freq_hz = crval1 + (freq_channels - crpix1) * cdelt1
        freq_mhz = freq_hz / 1e6

        waterfall_data = {}
        for col_name in all_data_2d[shape_key]:
            if col_name == "freq_info":
                continue
            if all_data_2d[shape_key][col_name]:
                waterfall_data[col_name] = np.full((len(shape_times), n_freq), np.nan)

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

        fig2, axes2 = plt.subplots(
            1, 7, figsize=(28, 32), sharex=True, sharey=True, tight_layout=True, dpi=100
        )
        fig2.suptitle(name, fontsize=6, fontweight="bold")

        for i, (col_name, color) in enumerate(zip(column_names, colors)):
            if col_name in waterfall_data and len(waterfall_data[col_name]) > 0:
                data_2d = waterfall_data[col_name]
                time_gps_2d = shape_times

                data_2d_norm = data_2d
                vmin = np.nanquantile(data_2d_norm, 0.05)
                vmax = np.nanquantile(data_2d_norm, 0.95)
                im = axes2[i].imshow(
                    data_2d_norm,
                    aspect="auto",
                    origin="lower",
                    extent=[freq_mhz[0], freq_mhz[-1], time_gps_2d[0], time_gps_2d[-1]],
                    cmap="cool",
                    interpolation="nearest",
                    vmin=vmin,
                    vmax=vmax,
                )

                plt.colorbar(
                    im, ax=axes2[i], orientation="horizontal", pad=0.1, shrink=0.8
                )

            axes2[i].set_title(col_name, fontweight="bold")
            axes2[i].set_xlabel("Frequency (MHz)")
            if i == 0:
                axes2[i].set_ylabel("GPS Time (s)")

        plt.tight_layout()

        filename = None
        if save:
            filename = f"metrics_waterfall_{name}_{shape_key}.png"
            plt.savefig(filename, dpi=150, bbox_inches="tight")
            filenames.append(filename)
            print(realpath(filename))

        if show:
            plt.show()
        else:
            plt.close()

    return filenames


def plot_auto_pol(data, name, show=False, save=True):
    """Plot AUTO_POL data grouped by receiver.

    Args:
        data: Data dict from load_metrics_data()
        name: Plot name/title
        show: Whether to show plot interactively
        save: Whether to save plot to file

    Returns:
        list: Paths to saved plot files (if save=True)
    """
    additional_data_2d = data["additional_data_2d"]
    additional_times_2d = data["additional_times_2d"]
    antenna_table = data["antenna_table"]
    metafits_receiver_mapping = data["metafits_receiver_mapping"]

    filenames = []

    if not additional_data_2d["AUTO_POL=XX"]:
        print("No AUTO_POL data found")
        return filenames

    first_auto_data = additional_data_2d["AUTO_POL=XX"][0]
    n_antennas, n_freq_auto = first_auto_data.shape

    # Frequency info from stored WCS
    wcs_info = data["wcs_info"]
    crval1, cdelt1, crpix1 = wcs_info["crval1"], wcs_info["cdelt1"], wcs_info["crpix1"]
    freq_hz_auto = crval1 + (np.arange(1, n_freq_auto + 1) - crpix1) * cdelt1
    freq_mhz_auto = freq_hz_auto / 1e6

    # Group antennas by receiver
    receivers = {}
    for ant_id, info in antenna_table.items():
        if metafits_receiver_mapping:
            ant_name = info.get("ANTNAME", "")
            rx_num = metafits_receiver_mapping.get(ant_name, "Unknown")
            if rx_num == "Unknown":
                continue
        else:
            rx_num = info.get("RX_NUMBER", "Unknown")

        if rx_num not in receivers:
            receivers[rx_num] = []
        receivers[rx_num].append(ant_id)

    for rx_num in sorted(receivers.keys()):
        if rx_num == "Unknown":
            continue

        ant_ids_in_rx = sorted(receivers[rx_num])[:8]

        for pol_name in ["XX", "YY", "XY"]:
            hdu_name = f"AUTO_POL={pol_name}"
            if hdu_name in additional_data_2d and additional_data_2d[hdu_name]:
                file_times = np.array(additional_times_2d[hdu_name])
                time_step_minutes = 5.0
                time_step_seconds = time_step_minutes * 60.0

                file_time_start = np.min(file_times)
                file_time_end = np.max(file_times)
                file_time_grid = np.arange(
                    file_time_start,
                    file_time_end + time_step_seconds,
                    time_step_seconds,
                )

                n_time_bins = len(file_time_grid)
                antenna_grids = {}

                for ant_id in ant_ids_in_rx:
                    if ant_id < n_antennas:
                        antenna_grids[ant_id] = np.full(
                            (n_time_bins, n_freq_auto), np.nan
                        )

                all_files_data = np.array(additional_data_2d[hdu_name])

                for file_idx, file_time in enumerate(file_times):
                    time_bin_idx = np.argmin(np.abs(file_time_grid - file_time))
                    for ant_id in ant_ids_in_rx:
                        if ant_id < n_antennas and ant_id in antenna_grids:
                            antenna_grids[ant_id][time_bin_idx, :] = all_files_data[
                                file_idx, ant_id, :
                            ]

                fig, axes = plt.subplots(
                    2, 4, figsize=(20, 10), sharex=True, sharey=True
                )
                fig.suptitle(
                    f"{name} - AUTO_POL {pol_name} - Receiver {rx_num}",
                    fontsize=12,
                    fontweight="bold",
                )
                axes = axes.flatten()

                time_gps_grid = file_time_grid

                for plot_idx, ant_id in enumerate(ant_ids_in_rx):
                    if plot_idx < 8 and ant_id in antenna_grids:
                        antenna_data = antenna_grids[ant_id]

                        vmin = np.nanquantile(antenna_data, 0.05)
                        vmax = np.nanquantile(antenna_data, 0.95)

                        extent = [
                            freq_mhz_auto[0],
                            freq_mhz_auto[-1],
                            time_gps_grid[0],
                            time_gps_grid[-1],
                        ]
                        im = axes[plot_idx].imshow(
                            antenna_data,
                            aspect="auto",
                            origin="lower",
                            extent=extent,
                            cmap="cool",
                            interpolation="nearest",
                            vmin=vmin,
                            vmax=vmax,
                        )

                        ant_name = get_antenna_display_name(ant_id, antenna_table)
                        axes[plot_idx].set_title(f"{ant_name}", fontsize=9)

                        if plot_idx >= 4:
                            axes[plot_idx].set_xlabel("Frequency (MHz)", fontsize=8)
                        if plot_idx % 4 == 0:
                            axes[plot_idx].set_ylabel("GPS Time (s)", fontsize=8)
                    else:
                        axes[plot_idx].set_visible(False)

                plt.tight_layout()
                cbar = fig.colorbar(
                    im, ax=axes, orientation="vertical", pad=0.02, shrink=0.8
                )
                cbar.set_label(f"{hdu_name} Amplitude", fontsize=8)

                filename = None
                if save:
                    filename = f"auto_pol_RX{rx_num}_{pol_name}_{name}.png"
                    plt.savefig(filename, dpi=150, bbox_inches="tight")
                    filenames.append(filename)
                    print(realpath(filename))

                if show:
                    plt.show()
                else:
                    plt.close()

    return filenames


def plot_auto_pol_lines(data, name, show=False, save=True):
    """Plot AUTO_POL data as line plots with each timestep overlaid.

    Args:
        data: Data dict from load_metrics_data()
        name: Plot name/title
        show: Whether to show plot interactively
        save: Whether to save plot to file

    Returns:
        list: Paths to saved plot files (if save=True)
    """
    additional_data_2d = data["additional_data_2d"]
    additional_times_2d = data["additional_times_2d"]
    antenna_table = data["antenna_table"]
    metafits_receiver_mapping = data["metafits_receiver_mapping"]

    filenames = []

    if not additional_data_2d["AUTO_POL=XX"]:
        print("No AUTO_POL data found")
        return filenames

    first_auto_data = additional_data_2d["AUTO_POL=XX"][0]
    n_antennas, n_freq_auto = first_auto_data.shape

    # Frequency info from stored WCS
    wcs_info = data["wcs_info"]
    crval1, cdelt1, crpix1 = wcs_info["crval1"], wcs_info["cdelt1"], wcs_info["crpix1"]
    freq_hz_auto = crval1 + (np.arange(1, n_freq_auto + 1) - crpix1) * cdelt1
    freq_mhz_auto = freq_hz_auto / 1e6

    # Group antennas by receiver
    receivers = {}
    for ant_id, info in antenna_table.items():
        if metafits_receiver_mapping:
            ant_name = info.get("ANTNAME", "")
            rx_num = metafits_receiver_mapping.get(ant_name, "Unknown")
            if rx_num == "Unknown":
                continue
        else:
            rx_num = info.get("RX_NUMBER", "Unknown")

        if rx_num not in receivers:
            receivers[rx_num] = []
        receivers[rx_num].append(ant_id)

    for rx_num in sorted(receivers.keys()):
        if rx_num == "Unknown":
            continue

        ant_ids_in_rx = sorted(receivers[rx_num])[:8]

        for pol_name in ["XX", "YY", "XY"]:
            hdu_name = f"AUTO_POL={pol_name}"
            if hdu_name in additional_data_2d and additional_data_2d[hdu_name]:

                file_times = np.array(additional_times_2d[hdu_name])
                all_files_data = np.array(additional_data_2d[hdu_name])  # (n_files, n_antennas, n_freq)

                fig, axes = plt.subplots(2, 4, figsize=(20, 10), sharex=True, sharey=True)
                fig.suptitle(
                    f"{name} - AUTO_POL {pol_name} Lines - Receiver {rx_num}",
                    fontsize=12,
                    fontweight="bold",
                )
                axes = axes.flatten()

                # Colors for different timesteps
                colors = plt.cm.cool(np.linspace(0, 1, len(all_files_data)))

                for plot_idx, ant_id in enumerate(ant_ids_in_rx):
                    if plot_idx < 8 and ant_id < n_antennas:
                        # Plot each timestep as a separate line for this antenna
                        for file_idx in range(len(all_files_data)):
                            antenna_spectrum = all_files_data[file_idx, ant_id, :]  # (n_freq,)

                            axes[plot_idx].plot(
                                freq_mhz_auto,
                                antenna_spectrum,
                                color=colors[file_idx],
                                alpha=0.7,
                                linewidth=1.0,
                                label=f"T{file_idx}" if file_idx < 5 else ""  # Only label first few
                            )

                        ant_name = get_antenna_display_name(ant_id, antenna_table)
                        axes[plot_idx].set_title(f"{ant_name}", fontsize=9)
                        axes[plot_idx].grid(True, alpha=0.3)

                        # Add legend only for first subplot if there are multiple timesteps
                        if plot_idx == 0 and len(all_files_data) > 1:
                            axes[plot_idx].legend(fontsize=6)

                        if plot_idx >= 4:
                            axes[plot_idx].set_xlabel("Frequency (MHz)", fontsize=8)
                        if plot_idx % 4 == 0:
                            axes[plot_idx].set_ylabel(f"{pol_name} Amplitude", fontsize=8)
                    else:
                        axes[plot_idx].set_visible(False)

                plt.tight_layout()

                filename = None
                if save:
                    filename = f"auto_pol_lines_RX{rx_num}_{pol_name}_{name}.png"
                    plt.savefig(filename, dpi=150, bbox_inches="tight")
                    filenames.append(filename)
                    print(realpath(filename))

                if show:
                    plt.show()
                else:
                    plt.close()

    return filenames


def plot_amp_fp_grid(data, name, show=False, save=True):
    """Plot AMP_FP metrics in a grid format.

    Args:
        data: Data dict from load_metrics_data()
        name: Plot name/title
        show: Whether to show plot interactively
        save: Whether to save plot to file

    Returns:
        str: Path to saved plot file (if save=True)
    """
    additional_data_2d = data["additional_data_2d"]
    additional_times_2d = data["additional_times_2d"]

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

    if not found_amp_fp:
        print("No AMP_FP polarization data found")
        return None

    # Frequency info from stored WCS
    wcs_info = data["wcs_info"]
    n_freq = 768  # This should match the data shape
    crval1, cdelt1, crpix1 = wcs_info["crval1"], wcs_info["cdelt1"], wcs_info["crpix1"]
    freq_hz = crval1 + (np.arange(1, n_freq + 1) - crpix1) * cdelt1
    freq_mhz = freq_hz / 1e6

    fig4, axes4 = plt.subplots(
        3, 3, figsize=(24, 12), sharex=True, sharey=True, dpi=150, tight_layout=True
    )
    fig4.suptitle(f"{name} - Metrics by Polarization", fontsize=10, fontweight="bold")

    for col_idx, base_name in enumerate(amp_fp_base_names):
        for row_idx, pol_suffix in enumerate(pol_suffixes):
            pol_key = base_name + pol_suffix

            if pol_key in additional_data_2d and additional_data_2d[pol_key]:
                file_times = np.array(additional_times_2d[pol_key])
                spectra_list = additional_data_2d[pol_key]

                time_step_minutes = 5.0
                time_step_seconds = time_step_minutes * 60.0

                file_time_start = np.min(file_times)
                file_time_end = np.max(file_times)
                file_time_grid = np.arange(
                    file_time_start,
                    file_time_end + time_step_seconds,
                    time_step_seconds,
                )

                n_time_bins = len(file_time_grid)
                spectra_grid = np.full((n_time_bins, n_freq), np.nan)

                for file_idx, file_time in enumerate(file_times):
                    time_bin_idx = np.argmin(np.abs(file_time_grid - file_time))
                    if file_idx < len(spectra_list):
                        spectra_grid[time_bin_idx, :] = spectra_list[file_idx]

                time_gps_grid = file_time_grid

                vmin = np.nanquantile(spectra_grid, 0.05)
                vmax = np.nanquantile(spectra_grid, 0.95)

                extent = [
                    freq_mhz[0],
                    freq_mhz[-1],
                    time_gps_grid[0],
                    time_gps_grid[-1],
                ]
                im = axes4[row_idx, col_idx].imshow(
                    spectra_grid,
                    aspect="auto",
                    origin="lower",
                    extent=extent,
                    cmap="cool",
                    interpolation="nearest",
                    vmin=vmin,
                    vmax=vmax,
                )

                # axes4[row_idx, col_idx].set_aspect(aspect=0.3)
            else:
                axes4[row_idx, col_idx].text(
                    0.5,
                    0.5,
                    f"No data for\n{base_name}\n{pol_suffix[1:]}",
                    transform=axes4[row_idx, col_idx].transAxes,
                    ha="center",
                    va="center",
                    fontsize=8,
                )

            if row_idx == 0:
                axes4[row_idx, col_idx].set_title(
                    base_name.replace("_", " "), fontsize=9, fontweight="bold"
                )
            if col_idx == 0:
                axes4[row_idx, col_idx].set_ylabel(
                    f"{pol_suffix[1:]} Pol\nTime (min)", fontsize=9, fontweight="bold"
                )
            if row_idx == 2:
                axes4[row_idx, col_idx].set_xlabel(
                    "Frequency (MHz)", fontsize=9, fontweight="bold"
                )

    plt.tight_layout()
    cbar = fig4.colorbar(im, ax=axes4, orientation="vertical", pad=0.02, shrink=0.8)
    cbar.set_label("Amplitude", fontsize=10)

    filename = None
    if save:
        filename = f"amp_fp_grid_{name}.png"
        plt.savefig(filename, dpi=150, bbox_inches="tight")
        print(realpath(filename))

    if show:
        plt.show()
    else:
        plt.close()

    return filename


def plot_auto_power_ant(data, name, show=False, save=True):
    """Plot AUTO_POWER_ANT data.

    Args:
        data: Data dict from load_metrics_data()
        name: Plot name/title
        show: Whether to show plot interactively
        save: Whether to save plot to file

    Returns:
        list: Paths to saved plot files (if save=True)
    """
    auto_power_ant_data = data["auto_power_ant_data"]
    auto_power_ant_times = data["auto_power_ant_times"]

    filenames = []

    if not auto_power_ant_data:
        print("No AUTO_POWER_ANT data found")
        return filenames

    print(f"Found AUTO_POWER_ANT data for {len(auto_power_ant_data)} antennas")

    # Frequency info from stored WCS
    wcs_info = data["wcs_info"]
    n_freq = 768  # This should match the data shape
    crval1, cdelt1, crpix1 = wcs_info["crval1"], wcs_info["cdelt1"], wcs_info["crpix1"]
    freq_hz = crval1 + (np.arange(1, n_freq + 1) - crpix1) * cdelt1
    freq_mhz = freq_hz / 1e6

    antenna_names = sorted(list(auto_power_ant_data.keys()))[:12]
    pol_names = ["XX", "YY", "XY"]

    for pol_idx, pol_name in enumerate(pol_names):
        fig5, axes5 = plt.subplots(3, 4, figsize=(20, 12), sharex=True, sharey=True)
        fig5.suptitle(
            f"{name} - AUTO_POWER_ANT {pol_name} (Time vs Frequency)",
            fontsize=10,
            fontweight="bold",
        )
        axes5 = axes5.flatten()

        for ant_idx, antenna_name in enumerate(antenna_names):
            if ant_idx < len(antenna_names):
                ant_file_data = auto_power_ant_data[antenna_name]
                ant_times = auto_power_ant_times[antenna_name]

                all_ant_times = []
                for times_array in ant_times:
                    all_ant_times.extend(times_array)

                if all_ant_times:
                    ant_time_start = min(all_ant_times)
                    ant_time_end = max(all_ant_times)
                    time_step_seconds = 300.0
                    ant_time_grid = np.arange(
                        ant_time_start,
                        ant_time_end + time_step_seconds,
                        time_step_seconds,
                    )

                    n_time_bins = len(ant_time_grid)
                    pol_data_grid = np.full((n_time_bins, n_freq), np.nan)

                    for file_idx, (file_data, file_times) in enumerate(
                        zip(ant_file_data, ant_times)
                    ):
                        pol_data = file_data[pol_idx, :, :]
                        file_start_time = file_times[0]
                        time_bin_idx = np.argmin(
                            np.abs(ant_time_grid - file_start_time)
                        )
                        file_spectrum = np.nanmean(pol_data, axis=0)
                        pol_data_grid[time_bin_idx, :] = file_spectrum

                    time_gps_grid = ant_time_grid

                    vmin = np.nanquantile(pol_data_grid, 0.05)
                    vmax = np.nanquantile(pol_data_grid, 0.95)

                    im = axes5[ant_idx].imshow(
                        pol_data_grid,
                        aspect="auto",
                        origin="lower",
                        extent=[
                            freq_mhz[0],
                            freq_mhz[-1],
                            time_gps_grid[0],
                            time_gps_grid[-1],
                        ],
                        cmap="cool",
                        interpolation="nearest",
                        vmin=vmin,
                        vmax=vmax,
                    )

                    axes5[ant_idx].set_aspect(aspect=0.3)
                else:
                    axes5[ant_idx].text(
                        0.5,
                        0.5,
                        f"No data for\n{antenna_name}",
                        transform=axes5[ant_idx].transAxes,
                        ha="center",
                        va="center",
                        fontsize=8,
                    )

                axes5[ant_idx].set_title(f"{antenna_name}", fontsize=8)

                if ant_idx >= 8:
                    axes5[ant_idx].set_xlabel("Frequency (MHz)", fontsize=8)
                if ant_idx % 4 == 0:
                    axes5[ant_idx].set_ylabel("GPS Time (s)", fontsize=8)
            else:
                axes5[ant_idx].set_visible(False)

        plt.tight_layout()
        cbar = fig5.colorbar(im, ax=axes5, orientation="vertical", pad=0.02, shrink=0.8)
        cbar.set_label(f"AUTO_POWER_ANT {pol_name} Amplitude", fontsize=8)

        filename = None
        if save:
            filename = f"auto_power_ant_{pol_name}_{name}.png"
            plt.savefig(filename, dpi=150, bbox_inches="tight")
            filenames.append(filename)
            print(realpath(filename))

        if show:
            plt.show()
        else:
            plt.close()

    return filenames


def plot_auto_power_ant_lines(data, name, show=False, save=True):
    """Plot AUTO_POWER_ANT data as line plots with each timestep overlaid.

    Args:
        data: Data dict from load_metrics_data()
        name: Plot name/title
        show: Whether to show plot interactively
        save: Whether to save plot to file

    Returns:
        list: Paths to saved plot files (if save=True)
    """
    auto_power_ant_data = data["auto_power_ant_data"]
    auto_power_ant_times = data["auto_power_ant_times"]

    filenames = []

    if not auto_power_ant_data:
        print("No AUTO_POWER_ANT data found")
        return filenames

    print(f"Found AUTO_POWER_ANT data for {len(auto_power_ant_data)} antennas")

    # Frequency info from stored WCS
    wcs_info = data["wcs_info"]
    n_freq = 768  # This should match the data shape
    crval1, cdelt1, crpix1 = wcs_info["crval1"], wcs_info["cdelt1"], wcs_info["crpix1"]
    freq_hz = crval1 + (np.arange(1, n_freq + 1) - crpix1) * cdelt1
    freq_mhz = freq_hz / 1e6

    antenna_names = sorted(list(auto_power_ant_data.keys()))[:12]
    pol_names = ["XX", "YY", "XY"]

    for pol_idx, pol_name in enumerate(pol_names):
        fig5, axes5 = plt.subplots(3, 4, figsize=(20, 12), sharex=True, sharey=True)
        fig5.suptitle(
            f"{name} - AUTO_POWER_ANT {pol_name} (Frequency Lines)",
            fontsize=10,
            fontweight="bold",
        )
        axes5 = axes5.flatten()

        for ant_idx, antenna_name in enumerate(antenna_names):
            if ant_idx < len(antenna_names):
                ant_file_data = auto_power_ant_data[antenna_name]
                ant_times = auto_power_ant_times[antenna_name]

                if ant_file_data and ant_times:
                    # Plot each timestep as a separate line
                    colors = plt.cm.cool(np.linspace(0, 1, len(ant_file_data)))

                    for file_idx, (file_data, file_times) in enumerate(
                        zip(ant_file_data, ant_times)
                    ):
                        if pol_idx < file_data.shape[0]:
                            # Extract polarization data: file_data[pol_idx, :, :] = (time, freq)
                            pol_data = file_data[pol_idx, :, :]  # (time_samples, freq)

                            # Average over time within this file to get one spectrum
                            file_spectrum = np.nanmean(pol_data, axis=0)  # (freq,)

                            # Plot this timestep as a line
                            axes5[ant_idx].plot(
                                freq_mhz,
                                file_spectrum,
                                color=colors[file_idx],
                                alpha=0.7,
                                linewidth=1.0,
                                label=f"T{file_idx}" if file_idx < 5 else ""  # Only label first few
                            )

                    axes5[ant_idx].set_title(f"{antenna_name}", fontsize=8)
                    axes5[ant_idx].grid(True, alpha=0.3)

                    # Add legend only for first subplot if there are multiple timesteps
                    if ant_idx == 0 and len(ant_file_data) > 1:
                        axes5[ant_idx].legend(fontsize=6)

                else:
                    axes5[ant_idx].text(
                        0.5,
                        0.5,
                        f"No data for\n{antenna_name}",
                        transform=axes5[ant_idx].transAxes,
                        ha="center",
                        va="center",
                        fontsize=8,
                    )

                if ant_idx >= 8:  # Bottom row
                    axes5[ant_idx].set_xlabel("Frequency (MHz)", fontsize=8)
                if ant_idx % 4 == 0:  # Left column
                    axes5[ant_idx].set_ylabel(f"{pol_name} Amplitude", fontsize=8)
            else:
                axes5[ant_idx].set_visible(False)

        plt.tight_layout()

        filename = None
        if save:
            filename = f"auto_power_ant_lines_{pol_name}_{name}.png"
            plt.savefig(filename, dpi=150, bbox_inches="tight")
            filenames.append(filename)
            print(realpath(filename))

        if show:
            plt.show()
        else:
            plt.close()

    return filenames


def plot_auto_sub_ant(data, name, show=False, save=True):
    """Plot AUTO_SUB_ANT data with 4-quadrant plots per antenna.

    Args:
        data: Data dict from load_metrics_data()
        name: Plot name/title
        show: Whether to show plot interactively
        save: Whether to save plot to file

    Returns:
        list: Paths to saved plot files (if save=True)
    """
    auto_sub_ant_data = data["auto_sub_ant_data"]
    auto_sub_ant_times = data["auto_sub_ant_times"]
    auto_sub_ant_metadata = data["auto_sub_ant_metadata"]
    antenna_table = data["antenna_table"]

    filenames = []

    if not auto_sub_ant_data:
        print("No AUTO_SUB_ANT data found")
        return filenames

    print(f"Found AUTO_SUB_ANT data for {len(auto_sub_ant_data)} antennas")

    # Frequency info from stored WCS
    wcs_info = data["wcs_info"]
    n_freq = 768  # This should match the data shape
    crval1, cdelt1, crpix1 = wcs_info["crval1"], wcs_info["cdelt1"], wcs_info["crpix1"]
    freq_hz = crval1 + (np.arange(1, n_freq + 1) - crpix1) * cdelt1
    freq_mhz = freq_hz / 1e6

    ant_ids = sorted(list(auto_sub_ant_data.keys()))

    for ant_id in ant_ids:
        ant_file_data = auto_sub_ant_data[ant_id]
        ant_times = auto_sub_ant_times[ant_id]
        ant_metadata = auto_sub_ant_metadata[ant_id]

        antenna_display_name = get_antenna_display_name(ant_id, antenna_table)

        fig6, axes6 = plt.subplots(2, 2, figsize=(16, 12))
        fig6.suptitle(
            f"{name} - AUTO_SUB_ANT {antenna_display_name}",
            fontsize=12,
            fontweight="bold",
        )

        all_ant_times = []
        for times_array in ant_times:
            all_ant_times.extend(times_array)

        if all_ant_times and ant_file_data:
            all_times_list = []
            all_data_list = []

            for file_idx, (file_data, file_times) in enumerate(
                zip(ant_file_data, ant_times)
            ):
                if len(file_data.shape) == 3:
                    for time_idx, gps_time in enumerate(file_times):
                        all_times_list.append(gps_time)
                        all_data_list.append(file_data[:, time_idx, :])

            sorted_indices = np.argsort(all_times_list)
            sorted_times = [all_times_list[i] for i in sorted_indices]
            sorted_data = [all_data_list[i] for i in sorted_indices]

            time_gps = sorted_times

            pol_names = ["XX", "YY", "XY"]
            positions = [(0, 0), (0, 1), (1, 0)]

            for pol_idx, (pol_name, pos) in enumerate(zip(pol_names, positions)):
                row, col = pos
                ax = axes6[row, col]

                if pol_idx < 3 and sorted_data:
                    n_time_samples = len(sorted_data)
                    pol_data_grid = np.full((n_time_samples, n_freq), np.nan)

                    for time_idx, time_data in enumerate(sorted_data):
                        if pol_idx < time_data.shape[0]:
                            pol_data_grid[time_idx, :] = time_data[pol_idx, :]

                    vmin = np.nanquantile(pol_data_grid, 0.05)
                    vmax = np.nanquantile(pol_data_grid, 0.95)

                    im = ax.imshow(
                        pol_data_grid,
                        aspect="auto",
                        origin="lower",
                        extent=[freq_mhz[0], freq_mhz[-1], time_gps[0], time_gps[-1]],
                        cmap="cool",
                        interpolation="none",
                        vmin=vmin,
                        vmax=vmax,
                    )

                    ax.set_title(f"{pol_name} Pol", fontsize=10, fontweight="bold")
                    ax.set_xlabel("Frequency (MHz)", fontsize=9)
                    ax.set_ylabel("GPS Time (s)", fontsize=9)

            # Add metadata in bottom-right quadrant
            ax_meta = axes6[1, 1]
            ax_meta.axis("off")

            if ant_id in antenna_table:
                info = antenna_table[ant_id]
                metadata_text = []

                if "ANTNAME" in info:
                    metadata_text.append(f"Name: {info['ANTNAME']}")
                if "ANT_NUM" in info:
                    metadata_text.append(f"Number: {info['ANT_NUM']}")
                if "ANT_TYPE" in info:
                    metadata_text.append(f"Type: {info['ANT_TYPE']}")

                metadata_text.append("")

                if "RX_NUMBER" in info:
                    metadata_text.append(f"RX Number: {info['RX_NUMBER']}")
                if "RX_SLOT" in info:
                    metadata_text.append(f"RX Slot: {info['RX_SLOT']}")
                if "RX_TYPE" in info:
                    metadata_text.append(f"RX Type: {info['RX_TYPE']}")

                hierarchical_keys = [
                    k
                    for k in info.keys()
                    if k
                    not in [
                        "HDU_NAME",
                        "ANTNAME",
                        "ANT_ID",
                        "ANT_NUM",
                        "ANT_TYPE",
                        "RX_NUMBER",
                        "RX_SLOT",
                        "RX_TYPE",
                        "OBSGEO-X",
                        "OBSGEO-Y",
                        "OBSGEO-Z",
                    ]
                ]
                if hierarchical_keys:
                    metadata_text.append("")
                    for key in hierarchical_keys:
                        metadata_text.append(f"{key}: {info[key]}")

                if all(k in info for k in ["OBSGEO-X", "OBSGEO-Y", "OBSGEO-Z"]):
                    metadata_text.append("")
                    metadata_text.append("Coordinates:")
                    metadata_text.append(f"  X: {info['OBSGEO-X']:.1f}")
                    metadata_text.append(f"  Y: {info['OBSGEO-Y']:.1f}")
                    metadata_text.append(f"  Z: {info['OBSGEO-Z']:.1f}")

                if metadata_text:
                    ax_meta.text(
                        0.05,
                        0.95,
                        "\n".join(metadata_text),
                        transform=ax_meta.transAxes,
                        fontsize=8,
                        verticalalignment="top",
                        fontfamily="monospace",
                    )
            else:
                ax_meta.text(
                    0.5,
                    0.5,
                    f"ANT_ID: {ant_id}\nNo metadata available",
                    transform=ax_meta.transAxes,
                    ha="center",
                    va="center",
                    fontsize=10,
                )

        else:
            for ax in axes6.flat:
                ax.text(
                    0.5,
                    0.5,
                    f"No data for ANT_ID {ant_id}",
                    transform=ax.transAxes,
                    ha="center",
                    va="center",
                    fontsize=10,
                )

        plt.tight_layout()

        filename = None
        if save:
            ant_name = antenna_table.get(ant_id, {}).get("ANTNAME", f"ANT_{ant_id}")
            filename = f"auto_sub_ant_{ant_name}_{name}.png"
            plt.savefig(filename, dpi=150, bbox_inches="tight")
            filenames.append(filename)
            print(realpath(filename))

        if show:
            plt.show()
        else:
            plt.close()

    return filenames


def plot_auto_delay_pol(data, name, show=False, save=True):
    """Plot AUTO_DELAY_POL data grouped by receiver.

    Args:
        data: Data dict from load_metrics_data()
        name: Plot name/title
        show: Whether to show plot interactively
        save: Whether to save plot to file

    Returns:
        list: Paths to saved plot files (if save=True)
    """
    auto_delay_pol_data = data["auto_delay_pol_data"]
    auto_delay_pol_times = data["auto_delay_pol_times"]
    antenna_table = data["antenna_table"]
    metafits_receiver_mapping = data["metafits_receiver_mapping"]

    filenames = []

    if not auto_delay_pol_data:
        print("No AUTO_DELAY_POL data found")
        return filenames

    print(f"Found AUTO_DELAY_POL data for {len(auto_delay_pol_data)} polarizations")

    # Group antennas by receiver
    receivers = {}
    for ant_id, info in antenna_table.items():
        if metafits_receiver_mapping:
            ant_name = info.get("ANTNAME", "")
            rx_num = metafits_receiver_mapping.get(ant_name, "Unknown")
            if rx_num == "Unknown":
                continue
        else:
            rx_num = info.get("RX_NUMBER", "Unknown")

        if rx_num not in receivers:
            receivers[rx_num] = []
        receivers[rx_num].append(ant_id)

    pol_names = ["XX", "YY", "XY"]

    for pol_name in pol_names:
        if pol_name in auto_delay_pol_data:
            delay_file_data = auto_delay_pol_data[pol_name]
            delay_times = auto_delay_pol_times[pol_name]

            if delay_file_data:
                first_delay_data = delay_file_data[0]
                n_antennas, n_delays = first_delay_data.shape

                sorted_indices = np.argsort(delay_times)
                sorted_times = [delay_times[i] for i in sorted_indices]
                sorted_data = [delay_file_data[i] for i in sorted_indices]

                time_gps = sorted_times

                for rx_num in sorted(receivers.keys()):
                    if rx_num == "Unknown":
                        continue

                    ant_ids_in_rx = sorted(receivers[rx_num])[:8]

                    fig7, axes7 = plt.subplots(
                        2, 4, figsize=(20, 12), sharex=True, sharey=True
                    )
                    fig7.suptitle(
                        f"{name} - AUTO_DELAY_POL {pol_name} - Receiver {rx_num}",
                        fontsize=12,
                        fontweight="bold",
                    )
                    axes7 = axes7.flatten()

                    for plot_idx, ant_id in enumerate(ant_ids_in_rx):
                        if plot_idx < 8 and ant_id < n_antennas:
                            n_files = len(sorted_data)
                            ant_delay_grid = np.full((n_files, n_delays), np.nan)

                            for file_idx, file_data in enumerate(sorted_data):
                                ant_delay_grid[file_idx, :] = file_data[ant_id, :]

                            vmin = np.nanquantile(ant_delay_grid, 0.05)
                            vmax = np.nanquantile(ant_delay_grid, 0.95)

                            im = axes7[plot_idx].imshow(
                                ant_delay_grid,
                                aspect="auto",
                                origin="lower",
                                extent=[0, n_delays - 1, time_gps[0], time_gps[-1]],
                                cmap="cool",
                                interpolation="none",
                                vmin=vmin,
                                vmax=vmax,
                            )

                            ant_name = get_antenna_display_name(ant_id, antenna_table)
                            axes7[plot_idx].set_title(f"{ant_name}", fontsize=9)

                            if plot_idx >= 4:
                                axes7[plot_idx].set_xlabel("Delay Bin", fontsize=8)
                            if plot_idx % 4 == 0:
                                axes7[plot_idx].set_ylabel("GPS Time (s)", fontsize=8)
                        else:
                            axes7[plot_idx].set_visible(False)

                    plt.tight_layout()
                    cbar = fig7.colorbar(
                        im, ax=axes7, orientation="vertical", pad=0.02, shrink=0.8
                    )
                    cbar.set_label(f"AUTO_DELAY_POL {pol_name} Amplitude", fontsize=8)

                    filename = None
                    if save:
                        filename = f"auto_delay_pol_RX{rx_num}_{pol_name}_{name}.png"
                        plt.savefig(filename, dpi=150, bbox_inches="tight")
                        filenames.append(filename)
                        print(realpath(filename))

                    if show:
                        plt.show()
                    else:
                        plt.close()

    return filenames


def plot_all_metrics(data, name, show=False, save=True):
    """Generate all available plots for the metrics data.

    Args:
        data: Data dict from load_metrics_data()
        name: Plot name/title
        show: Whether to show plots interactively
        save: Whether to save plots to file

    Returns:
        dict: Dictionary of plot types and their saved filenames
    """
    results = {}

    print("Generating timeseries plot...")
    results["timeseries"] = plot_timeseries(data, name, show, save)

    print("Generating waterfall plots...")
    results["waterfall"] = plot_waterfall(data, name, show, save)

    print("Generating AUTO_POL plots...")
    results["auto_pol"] = plot_auto_pol(data, name, show, save)

    print("Generating AUTO_POL line plots...")
    results["auto_pol_lines"] = plot_auto_pol_lines(data, name, show, save)

    print("Generating AMP_FP grid plot...")
    results["amp_fp"] = plot_amp_fp_grid(data, name, show, save)

    print("Generating AUTO_POWER_ANT plots...")
    results["auto_power_ant"] = plot_auto_power_ant(data, name, show, save)

    print("Generating AUTO_POWER_ANT line plots...")
    results["auto_power_ant_lines"] = plot_auto_power_ant_lines(data, name, show, save)

    print("Generating AUTO_SUB_ANT plots...")
    results["auto_sub_ant"] = plot_auto_sub_ant(data, name, show, save)

    print("Generating AUTO_DELAY_POL plots...")
    results["auto_delay_pol"] = plot_auto_delay_pol(data, name, show, save)

    return results


def main():
    """CLI interface for the metrics plotting tool."""
    parser = argparse.ArgumentParser(
        description="Plot metrics files produced by Birli --metrics-out",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --name obsid --metafits obsid.metafits *.fits
        """,
    )

    parser.add_argument(
        "--name", required=True, help="Name for the output plots (e.g., observation ID)"
    )
    parser.add_argument("--show", action="store_true", help="Show plots interactively")
    parser.add_argument(
        "--metafits",
        help="Path to metafits file for correct receiver mapping. "
        "Download from http://ws.mwatelescope.org/metadata/fits?obs_id=OBSID. "
        "Without this, plots will use incorrect RX_NUMBER from FITS headers.",
    )
    parser.add_argument("files", nargs="+", help="Metrics FITS files to process")

    args = parser.parse_args()

    metrics_files = sorted(args.files)
    name = args.name
    show = args.show
    metafits_path = args.metafits

    if not metafits_path:
        try:
            first_file = Path(metrics_files[0])
            obsid = first_file.stem.split("_")[1][:10]
            print(
                "WARNING: No metafits file provided. Using incorrect RX_NUMBER from FITS headers."
            )
            print("For correct receiver mapping, download metafits from:")
            print(f"http://ws.mwatelescope.org/metadata/fits?obs_id={obsid}")
        except Exception:
            print(
                "WARNING: No metafits file provided. Using incorrect RX_NUMBER from FITS headers."
            )

    plt.style.use("dark_background")

    # Load data
    data = load_metrics_data(metrics_files, metafits_path)

    # Generate all plots
    plot_all_metrics(data, name, show, save=True)


if __name__ == "__main__":
    main()
