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


def load_metafits_receiver_mapping(metafits_path):
    """Load antenna to receiver mapping from metafits file.

    Returns:
        dict: Mapping from antenna name to receiver number
    """
    antenna_to_receiver = {}

    try:
        with fits.open(metafits_path) as hdul:
            if 'TILEDATA' not in [hdu.name for hdu in hdul]:
                print(f"Warning: No TILEDATA HDU found in {metafits_path}")
                return {}

            tiledata = hdul['TILEDATA'].data

            # Create mapping from tile name to receiver
            # Each tile appears twice (for X and Y pol), so take unique tiles
            seen_tiles = set()
            for row in tiledata:
                tile_name = row['TileName']
                if isinstance(tile_name, bytes):
                    tile_name = tile_name.decode('utf-8')

                if tile_name not in seen_tiles:
                    rx_num = int(row['Rx'])
                    antenna_to_receiver[tile_name] = rx_num
                    seen_tiles.add(tile_name)

            print(f"Loaded receiver mapping for {len(antenna_to_receiver)} antennas from metafits")
            return antenna_to_receiver

    except Exception as e:
        print(f"Error reading metafits file {metafits_path}: {e}")
        return {}


def main():
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
             "Without this, plots will use incorrect RX_NUMBER from FITS headers."
    )
    parser.add_argument("files", nargs="+", help="Metrics FITS files to process")

    args = parser.parse_args()

    # Use CLI arguments
    metrics_files = sorted(args.files)
    name = args.name
    show = args.show
    metafits_path = args.metafits

    # Load correct receiver mapping from metafits if provided
    metafits_receiver_mapping = {}
    if metafits_path:
        metafits_receiver_mapping = load_metafits_receiver_mapping(metafits_path)
    else:
        # Extract obsid from first file to show helpful error message
        try:
            first_file = Path(metrics_files[0])
            obsid = first_file.stem.split('_')[1][:10]  # First 10 digits
            print("WARNING: No metafits file provided. Using incorrect RX_NUMBER from FITS headers.")
            print("For correct receiver mapping, download metafits from:")
            print(f"http://ws.mwatelescope.org/metadata/fits?obs_id={obsid}")
        except Exception:
            print("WARNING: No metafits file provided. Using incorrect RX_NUMBER from FITS headers.")

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

    # Store AUTO_POWER_ANT data
    auto_power_ant_data = {}  # Will be populated with antenna names as keys
    auto_power_ant_times = {}  # Times for each antenna

    # Store AUTO_SUB_ANT data (HDUs with ANT_ID in header)
    auto_sub_ant_data = {}  # Will be populated with HDU names as keys
    auto_sub_ant_times = {}  # Times for each HDU
    auto_sub_ant_metadata = {}  # Antenna metadata from headers

    # Store comprehensive antenna information table
    antenna_table = {}  # Will store metadata for ALL antennas

    # Store AUTO_DELAY_POL data
    auto_delay_pol_data = {}  # Will be populated with polarization names as keys
    auto_delay_pol_times = {}  # Times for each polarization

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
                additional_hdus = ['AUTO_POL=XX', 'AUTO_POL=YY', 'AUTO_POL=XY',
                                   'EAVILS_MEAN_AMP_FP', 'EAVILS_SQRT_MEAN_VAR_AMP_FP', 'SSINS_DIFF_MEAN_AMP_FP']

                # Find AUTO_POWER_ANT HDUs dynamically
                auto_power_ant_hdus = []
                for hdu in hdul:
                    if hdu.name.startswith('AUTO_POWER_ANT='):
                        auto_power_ant_hdus.append(hdu.name)

                # Find AUTO_SUB_ANT HDUs (HDUs with ANT_ID in header)
                auto_sub_ant_hdus = []
                for hdu in hdul:
                    if hasattr(hdu, 'header') and 'ANT_ID' in hdu.header:
                        auto_sub_ant_hdus.append(hdu.name)

                # Find AUTO_DELAY_POL HDUs
                auto_delay_pol_hdus = []
                for hdu in hdul:
                    if hdu.name.startswith('AUTO_DELAY_POL='):
                        auto_delay_pol_hdus.append(hdu.name)

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

                        if hdu_name.startswith('AUTO_POL='):
                            # AUTO_POL data: (n_antennas, n_frequencies) - NOT time-varying within file
                            # Store the full antenna × frequency array
                            additional_data_2d[hdu_name].append(additional_hdu_data)  # Store full antenna×freq array
                            additional_times_2d[hdu_name].append(gps_times[0])  # Use file start time

                            # For time series, take mean over antennas and frequencies
                            mean_data = np.nanmean(additional_hdu_data)  # Single value per file
                            mean_array = np.full(n_time_samples, mean_data)  # Repeat for all time samples in file
                            additional_data[hdu_name].append(mean_array)

                        elif '_AMP_FP' in hdu_name:
                            # AMP_FP data: (1536, 4) - store each polarization separately
                            # Polarizations are [XX, YY, XY, YX] - we want first 3
                            n_pols = min(3, additional_hdu_data.shape[1])  # Take first 3 pols

                            for pol_idx in range(n_pols):
                                pol_names = ['_XX', '_YY', '_XY']
                                pol_key = hdu_name + pol_names[pol_idx]

                                if pol_key not in additional_data_2d:
                                    additional_data_2d[pol_key] = []
                                    additional_times_2d[pol_key] = []

                                pol_spectrum = additional_hdu_data[:, pol_idx]  # Extract this polarization
                                additional_data_2d[pol_key].append(pol_spectrum)
                                additional_times_2d[pol_key].append(gps_times[0])

                    except KeyError:
                        # HDU doesn't exist, append NaNs
                        if hdu_name.startswith('AUTO_POL='):
                            additional_data[hdu_name].append(np.full(n_time_samples, np.nan))
                            # Store NaN array with antenna × frequency dimensions
                            nan_array_2d = np.full((128, ao_flag_aligned.shape[1]), np.nan)  # Assume 128 antennas
                            additional_data_2d[hdu_name].append(nan_array_2d)
                            additional_times_2d[hdu_name].append(gps_times[0])
                        elif '_AMP_FP' in hdu_name:
                            # For missing AMP_FP data, store NaN spectrum for each polarization
                            n_freq = ao_flag_aligned.shape[1]  # 768 freqs
                            pol_names = ['_XX', '_YY', '_XY']

                            for pol_name in pol_names:
                                pol_key = hdu_name + pol_name
                                if pol_key not in additional_data_2d:
                                    additional_data_2d[pol_key] = []
                                    additional_times_2d[pol_key] = []

                            nan_spectrum = np.full(n_freq, np.nan)
                            additional_data_2d[pol_key].append(nan_spectrum)
                            additional_times_2d[pol_key].append(gps_times[0])

                # Process AUTO_POWER_ANT HDUs
                for hdu_name in auto_power_ant_hdus:
                    try:
                        ant_data = hdul[hdu_name].data  # (4, 592, 768) = pol by time by freq
                        antenna_name = hdu_name.replace('AUTO_POWER_ANT=', '')
                        if antenna_name not in auto_power_ant_data:
                            auto_power_ant_data[antenna_name] = []
                            auto_power_ant_times[antenna_name] = []
                        auto_power_ant_data[antenna_name].append(ant_data)
                        auto_power_ant_times[antenna_name].append(gps_times)
                    except KeyError:
                        # Antenna data missing for this file
                        pass

                # Process AUTO_SUB_ANT HDUs
                for hdu_name in auto_sub_ant_hdus:
                    try:
                        hdu_data = hdul[hdu_name].data
                        hdu_header = hdul[hdu_name].header
                        ant_id = hdu_header.get('ANT_ID')
                        if ant_id is not None:
                            if ant_id not in auto_sub_ant_data:
                                auto_sub_ant_data[ant_id] = []
                                auto_sub_ant_times[ant_id] = []
                                auto_sub_ant_metadata[ant_id] = {}
                            auto_sub_ant_data[ant_id].append(hdu_data)
                            auto_sub_ant_times[ant_id].append(gps_times)  # Use full time array
                            auto_sub_ant_metadata[ant_id]['filename'] = filename
                            auto_sub_ant_metadata[ant_id]['hdu_name'] = hdu_name
                            auto_sub_ant_metadata[ant_id]['header'] = hdu_header

                            # Build comprehensive antenna table (only on first file to avoid duplicates)
                            if ant_id not in antenna_table:
                                ant_info = {'HDU_NAME': hdu_name}

                                # Extract key metadata
                                key_fields = [
                                    'ANTNAME', 'ANT_ID', 'ANT_NUM', 'ANT_TYPE',
                                    'RX_NUMBER', 'RX_SLOT', 'RX_TYPE'
                                ]
                                for key in key_fields:
                                    if key in hdu_header:
                                        value = hdu_header[key]
                                        if isinstance(value, str):
                                            value = value.strip()
                                        ant_info[key] = value

                                # Extract hierarchical keys
                                for key in hdu_header:
                                    if key.startswith('HIERARCH'):
                                        clean_key = key.replace('HIERARCH ', '')
                                        value = hdu_header[key]
                                        if isinstance(value, str):
                                            value = value.strip()
                                        ant_info[clean_key] = value

                                # Extract coordinates
                                for key in ['OBSGEO-X', 'OBSGEO-Y', 'OBSGEO-Z']:
                                    if key in hdu_header:
                                        ant_info[key] = hdu_header[key]

                                antenna_table[ant_id] = ant_info
                    except KeyError:
                        # HDU data missing for this file
                        pass

                # Process AUTO_DELAY_POL HDUs
                for hdu_name in auto_delay_pol_hdus:
                    try:
                        hdu_data = hdul[hdu_name].data  # (n_antennas, n_delays)
                        pol_name = hdu_name.replace('AUTO_DELAY_POL=', '')
                        if pol_name not in auto_delay_pol_data:
                            auto_delay_pol_data[pol_name] = []
                            auto_delay_pol_times[pol_name] = []
                        auto_delay_pol_data[pol_name].append(hdu_data)
                        auto_delay_pol_times[pol_name].append(gps_time)  # Use actual file GPS time
                    except KeyError:
                        # HDU data missing for this file
                        pass

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

    # Print antenna table summary
    if antenna_table:
        print(f"Found antenna information for {len(antenna_table)} antennas")
        antenna_types = {}
        for ant_id, info in antenna_table.items():
            ant_type = info.get('ANT_TYPE', 'Unknown')
            antenna_types[ant_type] = antenna_types.get(ant_type, 0) + 1
        print(f"Antenna types: {dict(antenna_types)}")

    def get_antenna_display_name(ant_id):
        """Get a nice display name for an antenna from the antenna table."""
        if ant_id in antenna_table:
            info = antenna_table[ant_id]
            ant_name = info.get('ANTNAME', f'ANT_{ant_id}')
            ant_num = info.get('ANT_NUM', '')
            if ant_num:
                return f"{ant_name} (#{ant_num})"
            else:
                return f"{ant_name} (ID={ant_id})"
        else:
            return f"ANT_ID={ant_id}"

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

    # Use actual GPS time in seconds
    time_gps_common = common_times

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
            # Only plot non-NaN data
            valid_mask = ~np.isnan(aligned_data[col_name])
            if np.any(valid_mask):
                axes[i].plot(
                    time_gps_common[valid_mask],
                    aligned_data[col_name][valid_mask],
                    color=color,
                    alpha=0.7,
                    linewidth=0.5,
                    marker='.',
                    markersize=1
                )
                # Set y-axis limits to show variation better
                valid_data = aligned_data[col_name][valid_mask]
                data_range = np.max(valid_data) - np.min(valid_data)
                if data_range > 0:
                    margin = data_range * 0.1  # Use larger margin for sparse data
                    y_min = np.min(valid_data) - margin
                    y_max = np.max(valid_data) + margin
                    axes[i].set_ylim(y_min, y_max)
                else:
                    # Data is constant, use percentage range around the value
                    center_val = np.mean(valid_data)
                    if abs(center_val) > 1e-10:  # Avoid division by zero for tiny values
                        axes[i].set_ylim(center_val * 0.95, center_val * 1.05)
                    else:
                        axes[i].set_ylim(-1e-10, 1e-10)
            else:
                # No valid data - show empty plot with message
                axes[i].text(
                    0.5, 0.5, f'No valid data\nfor {col_name}',
                    transform=axes[i].transAxes, ha='center', va='center')
        axes[i].set_ylabel(col_name, fontweight="bold")
        axes[i].grid(True, alpha=0.3)
        axes[i].set_xlim(time_gps_common[0], time_gps_common[-1])

    # Set x-axis label
    axes[-1].set_xlabel("GPS Time (seconds)", fontweight="bold")

    plt.tight_layout()
    plt.savefig(f'metrics_timeseries_{name}.png', dpi=150, bbox_inches='tight')
    if show:
        plt.show()

    print(realpath(f'metrics_timeseries_{name}.png'))

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

                # Use GPS times directly for consistent plotting
                time_gps_2d = shape_times

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
                        time_gps_2d[0],
                        time_gps_2d[-1],
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
                axes2[i].set_ylabel("GPS Time (s)")

        plt.tight_layout()
        plot_filename = f'metrics_waterfall_{name}_{shape_key}.png'
        plt.savefig(plot_filename, dpi=150, bbox_inches='tight')
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
        for hdu_name in ["AUTO_POL=XX", "AUTO_POL=YY", "AUTO_POL=XY"]:  # Only 3 pols
            if additional_data_2d[hdu_name]:
                auto_file_times[hdu_name] = np.array(additional_times_2d[hdu_name])

        # Group antennas by receiver using antenna table
        receivers = {}
        for ant_id, info in antenna_table.items():
            # Use metafits receiver mapping if available, otherwise fall back to FITS header
            if metafits_receiver_mapping:
                ant_name = info.get('ANTNAME', '')
                rx_num = metafits_receiver_mapping.get(ant_name, 'Unknown')
                if rx_num == 'Unknown':
                    print(f"Warning: Antenna {ant_name} not found in metafits, skipping")
                    continue
            else:
                rx_num = info.get('RX_NUMBER', 'Unknown')

            if rx_num not in receivers:
                receivers[rx_num] = []
            receivers[rx_num].append(ant_id)

        # Create plots grouped by receiver
        for rx_num in sorted(receivers.keys()):
            if rx_num == 'Unknown':
                continue

            ant_ids_in_rx = sorted(receivers[rx_num])[:8]  # Take first 8 antennas

            for pol_name in ["XX", "YY", "XY"]:  # Only 3 polarizations
                hdu_name = f"AUTO_POL={pol_name}"
                if hdu_name in additional_data_2d and additional_data_2d[hdu_name]:

                    # Get file times and convert to time grid
                    file_times = np.array(additional_times_2d[hdu_name])

                    # Create time grid that aligns with global time grid
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

                    for ant_id in ant_ids_in_rx:
                        if ant_id < n_antennas:  # Check antenna exists in data
                            antenna_grids[ant_id] = np.full((n_time_bins, n_freq_auto), np.nan)

                    # Fill in data at appropriate time indices
                    all_files_data = np.array(
                        additional_data_2d[hdu_name]
                    )  # (n_files, n_antennas, n_freq)

                    for file_idx, file_time in enumerate(file_times):
                        # Find closest time bin
                        time_bin_idx = np.argmin(np.abs(file_time_grid - file_time))

                        for ant_id in ant_ids_in_rx:
                            if ant_id < n_antennas and ant_id in antenna_grids:
                                antenna_grids[ant_id][time_bin_idx, :] = all_files_data[
                                    file_idx, ant_id, :
                                ]

                    # Create subplots for antennas in this receiver
                    fig, axes = plt.subplots(
                        2, 4, figsize=(20, 10), sharex=True, sharey=True
                    )
                    fig.suptitle(
                        f"{name} - AUTO_POL {pol_name} - Receiver {rx_num}",
                        fontsize=12, fontweight="bold"
                    )
                    axes = axes.flatten()

                    # Use file time grid as GPS seconds
                    time_gps_grid = file_time_grid

                    for plot_idx, ant_id in enumerate(ant_ids_in_rx):
                        if plot_idx < 8 and ant_id in antenna_grids:
                            # Get data for this antenna
                            antenna_data = antenna_grids[ant_id]  # (n_time_bins, n_freq)

                            # Apply quantile scaling
                            vmin = np.nanquantile(antenna_data, 0.05)
                            vmax = np.nanquantile(antenna_data, 0.95)

                            # Plot: time bins on y-axis, frequency on x-axis
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
                                cmap="viridis",
                                interpolation="nearest",
                                vmin=vmin,
                                vmax=vmax,
                            )

                            # Get antenna name from antenna table
                            ant_name = get_antenna_display_name(ant_id)
                            axes[plot_idx].set_title(f"{ant_name}", fontsize=9)

                            if plot_idx >= 4:  # Bottom row
                                axes[plot_idx].set_xlabel("Frequency (MHz)", fontsize=8)
                            if plot_idx % 4 == 0:  # Left column
                                axes[plot_idx].set_ylabel("GPS Time (s)", fontsize=8)
                        else:
                            axes[plot_idx].set_visible(False)

                    # Add colorbar on the right side
                    plt.tight_layout()
                    cbar = fig.colorbar(
                        im, ax=axes, orientation="vertical", pad=0.02, shrink=0.8
                    )
                    cbar.set_label(f"{hdu_name} Amplitude", fontsize=8)

                    auto_pol_plot_filename = f"auto_pol_RX{rx_num}_{pol_name}_{name}.png"
                    plt.savefig(auto_pol_plot_filename, dpi=150, bbox_inches="tight")
                    if show:
                        plt.show()
                    else:
                        plt.close()  # Close figure to save memory

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

                    # Use file time grid as GPS seconds
                    time_gps_grid = file_time_grid

                    # Apply quantile scaling
                    vmin = np.nanquantile(spectra_grid, 0.05)
                    vmax = np.nanquantile(spectra_grid, 0.95)

                    # Plot: time bins on y-axis, frequency on x-axis
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
                        cmap="viridis",
                        interpolation="nearest",
                        vmin=vmin,
                        vmax=vmax,
                    )

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

    # Process AUTO_POWER_ANT data
    if auto_power_ant_data:
        print(f"Found AUTO_POWER_ANT data for {len(auto_power_ant_data)} antennas")

        # Get frequency info (same as main data)
        freq_hz = crval1 + (np.arange(1, n_freq + 1) - crpix1) * cdelt1
        freq_mhz = freq_hz / 1e6

        # Select first few antennas for plotting (limit to 12 for visibility)
        antenna_names = sorted(list(auto_power_ant_data.keys()))[:12]

        # Create plots for each polarization (XX, YY, XY)
        pol_names = ['XX', 'YY', 'XY']

        for pol_idx, pol_name in enumerate(pol_names):
            fig5, axes5 = plt.subplots(3, 4, figsize=(20, 12), sharex=True, sharey=True)
            fig5.suptitle(f'{name} - AUTO_POWER_ANT {pol_name} (Time vs Frequency)', fontsize=10, fontweight='bold')
            axes5 = axes5.flatten()

            for ant_idx, antenna_name in enumerate(antenna_names):
                if ant_idx < len(antenna_names):
                    # Get data for this antenna and polarization
                    ant_file_data = auto_power_ant_data[antenna_name]  # List of (4, 592, 768) arrays
                    ant_times = auto_power_ant_times[antenna_name]  # List of time arrays

                    # Create time grid for this antenna
                    all_ant_times = []
                    for times_array in ant_times:
                        all_ant_times.extend(times_array)

                    if all_ant_times:
                        ant_time_start = min(all_ant_times)
                        ant_time_end = max(all_ant_times)
                        time_step_seconds = 300.0  # 5 minute bins
                        ant_time_grid = np.arange(ant_time_start, ant_time_end + time_step_seconds, time_step_seconds)

                        # Create 2D grid: (n_time_bins, n_freq)
                        n_time_bins = len(ant_time_grid)
                        pol_data_grid = np.full((n_time_bins, n_freq), np.nan)

                        # Fill in data at appropriate time indices
                        for file_idx, (file_data, file_times) in enumerate(zip(ant_file_data, ant_times)):
                            # Extract polarization data: file_data[pol_idx, :, :] = (time, freq)
                            pol_data = file_data[pol_idx, :, :]  # (592, 768)

                            # Find time bin for this file
                            file_start_time = file_times[0]
                            time_bin_idx = np.argmin(np.abs(ant_time_grid - file_start_time))

                            # Average over time within file to get one spectrum per file
                            file_spectrum = np.nanmean(pol_data, axis=0)  # (768,)
                            pol_data_grid[time_bin_idx, :] = file_spectrum

                        # Use time grid as GPS seconds
                        time_gps_grid = ant_time_grid

                        # Apply quantile scaling
                        vmin = np.nanquantile(pol_data_grid, 0.05)
                        vmax = np.nanquantile(pol_data_grid, 0.95)

                        # Plot: time bins on y-axis, frequency on x-axis
                        im = axes5[ant_idx].imshow(
                            pol_data_grid, aspect='auto', origin='lower',
                            extent=[freq_mhz[0], freq_mhz[-1],
                                    time_gps_grid[0], time_gps_grid[-1]],
                            cmap='viridis', interpolation='nearest', vmin=vmin, vmax=vmax)

                        # Compress the y-axis to reduce vertical space
                        axes5[ant_idx].set_aspect(aspect=0.3)

                    else:
                        # No data for this antenna
                        axes5[ant_idx].text(
                            0.5, 0.5, f'No data for\n{antenna_name}',
                            transform=axes5[ant_idx].transAxes,
                            ha='center', va='center', fontsize=8)

                    axes5[ant_idx].set_title(f'{antenna_name}', fontsize=8)

                    if ant_idx >= 8:  # Bottom row
                        axes5[ant_idx].set_xlabel('Frequency (MHz)', fontsize=8)
                    if ant_idx % 4 == 0:  # Left column
                        axes5[ant_idx].set_ylabel('GPS Time (s)', fontsize=8)
                else:
                    axes5[ant_idx].set_visible(False)

            # Add colorbar on the right side
            plt.tight_layout()
            cbar = fig5.colorbar(im, ax=axes5, orientation='vertical', pad=0.02, shrink=0.8)
            cbar.set_label(f'AUTO_POWER_ANT {pol_name} Amplitude', fontsize=8)

            auto_power_filename = f'auto_power_ant_{pol_name}_{name}.png'
            plt.savefig(auto_power_filename, dpi=150, bbox_inches='tight')
            if show:
                plt.show()

            print(realpath(auto_power_filename))

    else:
        print("No AUTO_POWER_ANT data found")

    # Process AUTO_SUB_ANT data (4-quadrant plots)
    if auto_sub_ant_data:
        print(f"Found AUTO_SUB_ANT data for {len(auto_sub_ant_data)} antennas")

        # Get frequency info (same as main data)
        freq_hz = crval1 + (np.arange(1, n_freq + 1) - crpix1) * cdelt1
        freq_mhz = freq_hz / 1e6

        # Select all antennas for plotting
        ant_ids = sorted(list(auto_sub_ant_data.keys()))

        for ant_id in ant_ids:
            ant_file_data = auto_sub_ant_data[ant_id]  # List of arrays
            ant_times = auto_sub_ant_times[ant_id]  # List of time arrays
            ant_metadata = auto_sub_ant_metadata[ant_id]  # Metadata dict

            # Get nice antenna name from antenna table
            antenna_display_name = get_antenna_display_name(ant_id)

            # Create 2x2 subplot grid (XX, YY, XY, metadata)
            fig6, axes6 = plt.subplots(2, 2, figsize=(16, 12))
            fig6.suptitle(
                f'{name} - AUTO_SUB_ANT {antenna_display_name}',
                fontsize=12, fontweight='bold')

            # Create time grid for this antenna
            all_ant_times = []
            for times_array in ant_times:
                all_ant_times.extend(times_array)

            if all_ant_times and ant_file_data:
                # Collect all time samples from all files
                all_times_list = []
                all_data_list = []

                for file_idx, (file_data, file_times) in enumerate(zip(ant_file_data, ant_times)):
                    if len(file_data.shape) == 3:  # (pol, time, freq)
                        # Extract each time sample from this file
                        for time_idx, gps_time in enumerate(file_times):
                            all_times_list.append(gps_time)
                            all_data_list.append(file_data[:, time_idx, :])  # (pol, freq) for this time

                # Sort by time
                sorted_indices = np.argsort(all_times_list)
                sorted_times = [all_times_list[i] for i in sorted_indices]
                sorted_data = [all_data_list[i] for i in sorted_indices]

                # Use actual GPS times in seconds
                time_gps = sorted_times

                # Process each polarization
                pol_names = ['XX', 'YY', 'XY']
                positions = [(0, 0), (0, 1), (1, 0)]  # XX, YY, XY positions

                for pol_idx, (pol_name, pos) in enumerate(zip(pol_names, positions)):
                    row, col = pos
                    ax = axes6[row, col]

                    if pol_idx < 3 and sorted_data:  # Only plot first 3 pols
                        # Create 2D grid: (n_time_samples, n_freq)
                        n_time_samples = len(sorted_data)
                        pol_data_grid = np.full((n_time_samples, n_freq), np.nan)

                        # Fill in data: each time sample contributes one row
                        for time_idx, time_data in enumerate(sorted_data):
                            if pol_idx < time_data.shape[0]:  # Check pol exists
                                pol_data_grid[time_idx, :] = time_data[pol_idx, :]  # (freq,)

                        # Apply quantile scaling
                        vmin = np.nanquantile(pol_data_grid, 0.05)
                        vmax = np.nanquantile(pol_data_grid, 0.95)

                        # Plot: time samples on y-axis, frequency on x-axis
                        im = ax.imshow(
                            pol_data_grid, aspect='auto', origin='lower',
                            extent=[freq_mhz[0], freq_mhz[-1],
                                    time_gps[0], time_gps[-1]],
                            cmap='viridis', interpolation='none', vmin=vmin, vmax=vmax)

                        ax.set_title(f'{pol_name} Pol', fontsize=10, fontweight='bold')
                        ax.set_xlabel('Frequency (MHz)', fontsize=9)
                        ax.set_ylabel('GPS Time (s)', fontsize=9)

                # Add metadata in bottom-right quadrant
                ax_meta = axes6[1, 1]
                ax_meta.axis('off')  # Turn off axis for metadata display

                # Extract key metadata from antenna table
                if ant_id in antenna_table:
                    info = antenna_table[ant_id]
                    metadata_text = []

                    # Primary antenna info
                    if 'ANTNAME' in info:
                        metadata_text.append(f"Name: {info['ANTNAME']}")
                    if 'ANT_NUM' in info:
                        metadata_text.append(f"Number: {info['ANT_NUM']}")
                    if 'ANT_TYPE' in info:
                        metadata_text.append(f"Type: {info['ANT_TYPE']}")

                    metadata_text.append("")  # Blank line

                    # Receiver info
                    if 'RX_NUMBER' in info:
                        metadata_text.append(f"RX Number: {info['RX_NUMBER']}")
                    if 'RX_SLOT' in info:
                        metadata_text.append(f"RX Slot: {info['RX_SLOT']}")
                    if 'RX_TYPE' in info:
                        metadata_text.append(f"RX Type: {info['RX_TYPE']}")

                    # Add hierarchical info if available
                    hierarchical_keys = [
                        k for k in info.keys() if k not in
                        ['HDU_NAME', 'ANTNAME', 'ANT_ID', 'ANT_NUM', 'ANT_TYPE',
                         'RX_NUMBER', 'RX_SLOT', 'RX_TYPE', 'OBSGEO-X', 'OBSGEO-Y', 'OBSGEO-Z']
                    ]
                    if hierarchical_keys:
                        metadata_text.append("")  # Blank line
                        for key in hierarchical_keys:
                            metadata_text.append(f"{key}: {info[key]}")

                    # Add coordinates
                    if all(k in info for k in ['OBSGEO-X', 'OBSGEO-Y', 'OBSGEO-Z']):
                        metadata_text.append("")  # Blank line
                        metadata_text.append("Coordinates:")
                        metadata_text.append(f"  X: {info['OBSGEO-X']:.1f}")
                        metadata_text.append(f"  Y: {info['OBSGEO-Y']:.1f}")
                        metadata_text.append(f"  Z: {info['OBSGEO-Z']:.1f}")

                    # Display metadata
                    if metadata_text:
                        ax_meta.text(
                            0.05, 0.95, '\n'.join(metadata_text),
                            transform=ax_meta.transAxes, fontsize=8,
                            verticalalignment='top', fontfamily='monospace')
                else:
                    # Fallback to original header if antenna table doesn't have info
                    header = ant_metadata.get('header', {})
                    metadata_text = []

                    # Key antenna information
                    for key in ['ANTNAME', 'ANT_ID', 'ANT_NUM', 'ANT_TYPE', 'RX_NUMBER', 'RX_SLOT', 'RX_TYPE']:
                        if key in header:
                            value = header[key]
                            if isinstance(value, str):
                                value = value.strip()
                            metadata_text.append(f'{key}: {value}')

                    # Display metadata
                    if metadata_text:
                        ax_meta.text(
                            0.05, 0.95, '\n'.join(metadata_text),
                            transform=ax_meta.transAxes, fontsize=8,
                            verticalalignment='top', fontfamily='monospace')
                    else:
                        ax_meta.text(
                            0.5, 0.5, f'ANT_ID: {ant_id}\nNo metadata available',
                            transform=ax_meta.transAxes, ha='center', va='center', fontsize=10)

            else:
                # No data for this antenna
                for ax in axes6.flat:
                    ax.text(
                        0.5, 0.5, f'No data for ANT_ID {ant_id}',
                        transform=ax.transAxes, ha='center', va='center', fontsize=10)

            plt.tight_layout()
            # Use antenna name in filename for better organization
            ant_name = antenna_table.get(ant_id, {}).get('ANTNAME', f'ANT_{ant_id}')
            auto_sub_filename = f'auto_sub_ant_{ant_name}_{name}.png'
            plt.savefig(auto_sub_filename, dpi=150, bbox_inches='tight')
            if show:
                plt.show()

            print(realpath(auto_sub_filename))

    else:
        print("No AUTO_SUB_ANT data found")

    # Process AUTO_DELAY_POL data (delay spectra plots)
    if auto_delay_pol_data:
        print(f"Found AUTO_DELAY_POL data for {len(auto_delay_pol_data)} polarizations")

        # Create plots for each polarization, grouped by receiver
        pol_names = ['XX', 'YY', 'XY']  # Only 3 polarizations

        # Group antennas by receiver using antenna table
        receivers = {}
        for ant_id, info in antenna_table.items():
            # Use metafits receiver mapping if available, otherwise fall back to FITS header
            if metafits_receiver_mapping:
                ant_name = info.get('ANTNAME', '')
                rx_num = metafits_receiver_mapping.get(ant_name, 'Unknown')
                if rx_num == 'Unknown':
                    print(f"Warning: Antenna {ant_name} not found in metafits, skipping")
                    continue
            else:
                rx_num = info.get('RX_NUMBER', 'Unknown')

            if rx_num not in receivers:
                receivers[rx_num] = []
            receivers[rx_num].append(ant_id)

        for pol_name in pol_names:
            if pol_name in auto_delay_pol_data:
                delay_file_data = auto_delay_pol_data[pol_name]  # List of (n_antennas, n_delays) arrays
                delay_times = auto_delay_pol_times[pol_name]  # List of file times

                if delay_file_data:
                    # Get dimensions from first file
                    first_delay_data = delay_file_data[0]
                    n_antennas, n_delays = first_delay_data.shape

                    # Sort files by time and create direct time vs delay plot
                    sorted_indices = np.argsort(delay_times)
                    sorted_times = [delay_times[i] for i in sorted_indices]
                    sorted_data = [delay_file_data[i] for i in sorted_indices]

                    # Use GPS times directly
                    time_gps = sorted_times

                    # Create plots for each receiver
                    for rx_num in sorted(receivers.keys()):
                        if rx_num == 'Unknown':
                            continue

                        ant_ids_in_rx = sorted(receivers[rx_num])[:8]  # Take first 8 antennas

                        # Create subplots for antennas in this receiver
                        fig7, axes7 = plt.subplots(2, 4, figsize=(20, 12), sharex=True, sharey=True)
                        fig7.suptitle(
                            f'{name} - AUTO_DELAY_POL {pol_name} - Receiver {rx_num}',
                            fontsize=12, fontweight='bold')
                        axes7 = axes7.flatten()

                        for plot_idx, ant_id in enumerate(ant_ids_in_rx):
                            if plot_idx < 8 and ant_id < n_antennas:
                                # Create 2D grid: (n_files, n_delays) - each file is one time row
                                n_files = len(sorted_data)
                                ant_delay_grid = np.full((n_files, n_delays), np.nan)

                                # Fill in data at appropriate time indices
                                for file_idx, file_data in enumerate(sorted_data):
                                    ant_delay_grid[file_idx, :] = file_data[ant_id, :]  # (n_delays,)

                                # Apply quantile scaling
                                vmin = np.nanquantile(ant_delay_grid, 0.05)
                                vmax = np.nanquantile(ant_delay_grid, 0.95)

                                # Plot: files (time) on y-axis, delay on x-axis
                                im = axes7[plot_idx].imshow(
                                    ant_delay_grid, aspect='auto', origin='lower',
                                    extent=[0, n_delays - 1, time_gps[0], time_gps[-1]],
                                    cmap='viridis', interpolation='none', vmin=vmin, vmax=vmax)

                                # Get antenna name from antenna table
                                ant_name = get_antenna_display_name(ant_id)
                                axes7[plot_idx].set_title(f'{ant_name}', fontsize=9)

                                if plot_idx >= 4:  # Bottom row
                                    axes7[plot_idx].set_xlabel('Delay Bin', fontsize=8)
                                if plot_idx % 4 == 0:  # Left column
                                    axes7[plot_idx].set_ylabel('GPS Time (s)', fontsize=8)
                            else:
                                axes7[plot_idx].set_visible(False)

                        # Add colorbar on the right side
                        plt.tight_layout()
                        cbar = fig7.colorbar(im, ax=axes7, orientation='vertical', pad=0.02, shrink=0.8)
                        cbar.set_label(f'AUTO_DELAY_POL {pol_name} Amplitude', fontsize=8)

                        auto_delay_filename = f'auto_delay_pol_RX{rx_num}_{pol_name}_{name}.png'
                        plt.savefig(auto_delay_filename, dpi=150, bbox_inches='tight')
                        if show:
                            plt.show()
                        else:
                            plt.close()  # Close figure to save memory

                        print(realpath(auto_delay_filename))

    else:
        print("No AUTO_DELAY_POL data found")


if __name__ == "__main__":
    main()
