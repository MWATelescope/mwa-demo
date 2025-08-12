#!/usr/bin/env python3
"""
Plot time series of phase-fit lengths and intercepts for all tiles.

Scans for pivoted per-timeblock TSV files produced by 82_calfit.py, named like:
  "<prefix> tNNN phase_fits.tsv"

Then aggregates values across time and produces grid plots (rx x slot):
- lengths_xx/yy over time
- intercepts_xx/yy over time

Usage examples:
demo/83_clock.py \
    --glob "clock_tec/* t??? phase_fits.tsv" \
    --out-dir ./clock_tec --title "combined" \
    --smooth 8 --timestep-sec 2 --show --dark
"""

from __future__ import annotations

import argparse
import glob
import os
import re
from collections.abc import Iterable
from dataclasses import dataclass

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns


@dataclass
class PhaseFitsFile:
    """A phase_fits.tsv file with its parsed time index and GPS start."""

    path: str
    time_index: int
    gps_start: int | None


TIME_RE = re.compile(r"t(\d{3})\s+phase_fits\.tsv$")
GPS_RE = re.compile(r"(?<!\d)(\d{10})(?!\d)")


def find_phase_fits(
    *,
    directory: str,
    glob_pattern: str | None,
    prefix: str | None,
) -> list[PhaseFitsFile]:
    """Find all phase_fits.tsv files and extract their time index."""
    candidates: list[str]
    if glob_pattern:
        candidates = sorted(glob.glob(glob_pattern))
    else:
        candidates = sorted(glob.glob(os.path.join(directory, "* t??? phase_fits.tsv")))

    files: list[PhaseFitsFile] = []
    for path in candidates:
        base = os.path.basename(path)
        # optional prefix filter
        if prefix and not base.startswith(prefix):
            continue
        m = TIME_RE.search(base)
        if not m:
            continue
        time_index = int(m.group(1))
        gps_match = GPS_RE.findall(base)
        gps_start: int | None = int(gps_match[0]) if gps_match else None
        files.append(
            PhaseFitsFile(path=path, time_index=time_index, gps_start=gps_start)
        )

    files.sort(key=lambda f: f.time_index)
    return files


def load_timeseries(files: Iterable[PhaseFitsFile]) -> pd.DataFrame:
    """Load and concatenate pivoted phase_fits TSV files with time index.

    Returns a dataframe with columns including:
    - time_index, name, tile_id, rx, slot, flavor
    - length_xx, length_yy, intercept_xx, intercept_yy
    - other metrics if present (e.g., chi2dof_xx/yy, sigma_resid)
    """
    frames: list[pd.DataFrame] = []
    for f in files:
        df = pd.read_csv(f.path, sep="\t")
        df["time_index"] = f.time_index
        df["gps_start"] = f.gps_start
        frames.append(df)
    if not frames:
        raise RuntimeError("No phase_fits.tsv files found.")
    data = pd.concat(frames, ignore_index=True)
    # Ensure expected columns exist
    expected = [
        "time_index",
        "gps_start",
        "name",
        "tile_id",
        "rx",
        "slot",
        "flavor",
        "length_xx",
        "length_yy",
        "intercept_xx",
        "intercept_yy",
    ]
    for col in expected:
        if col not in data.columns:
            raise RuntimeError(f"Missing expected column in TSV: {col}")
    return data


def build_times_index(data: pd.DataFrame, timestep_sec: float) -> pd.DataFrame:
    """Build a complete time index per observation, inserting gaps.

    For each `gps_start`, generates all integer `time_index` values between the
    minimum and maximum present (inclusive). Computes `gps_time` as
      gps_start + time_index * timestep_sec
    and returns a concatenated, sorted index with an `order_index` column.
    """
    groups = []
    for gps_start, group in data.groupby("gps_start"):
        # ensure integers for time_index
        idx_min = int(pd.to_numeric(group["time_index"]).min())
        idx_max = int(pd.to_numeric(group["time_index"]).max())
        full_idx = pd.DataFrame({
            "gps_start": gps_start,
            "time_index": np.arange(idx_min, idx_max + 1, dtype=int),
        })
        full_idx["gps_time"] = (
            full_idx["gps_start"].astype(float) +
            full_idx["time_index"].astype(float) * float(timestep_sec)
        )
        groups.append(full_idx)
    if not groups:
        return pd.DataFrame(
            columns=["gps_start", "time_index", "gps_time", "order_index"]
        )  # type: ignore
    times_index = pd.concat(groups, ignore_index=True)
    times_index.sort_values(by=["gps_start", "time_index"], inplace=True)
    times_index.reset_index(drop=True, inplace=True)
    times_index["order_index"] = np.arange(len(times_index))
    return times_index


def _smooth_array(values: np.ndarray, window: int) -> np.ndarray:
    if window is None or window <= 1:
        return values
    try:
        import pandas as _pd  # local import to avoid top-level dependency issues

        return (
            _pd.Series(values, dtype=float)
            .rolling(window=window, min_periods=1, center=True)
            .mean()
            .to_numpy()
        )
    except Exception:
        # Fallback: simple convolution; treat NaNs as zeros with weight correction
        vals = values.astype(float)
        mask = np.isfinite(vals).astype(float)
        vals[~np.isfinite(vals)] = 0.0
        kernel = np.ones(window, dtype=float)
        num = np.convolve(vals, kernel, mode="same")
        den = np.convolve(mask, kernel, mode="same")
        den[den == 0] = 1.0
        return num / den


def plot_grid_over_time(
    data: pd.DataFrame,
    *,
    value_xx: str,
    value_yy: str,
    ylabel: str,
    title: str,
    out_path: str,
    sharey: bool = False,
    smooth_window: int = 4,
    times_index: pd.DataFrame | None = None,
) -> None:
    """Plot grid of values over time (rx x slot), XX and YY per tile."""
    sns.set_context("talk")
    rxs = np.sort(data["rx"].unique())
    slots = np.sort(data["slot"].unique())

    fig, axs = plt.subplots(
        len(rxs), len(slots), sharex=True, sharey=sharey, squeeze=True, figsize=(
            float(np.clip(len(slots) * 2.5, 5, 24)),
            float(np.clip(len(rxs) * 2.5, 5, 24)),
        )
    )
    # Normalize axs to 2D array
    if len(rxs) == 1 and len(slots) == 1:
        axs = np.array([[axs]])
    elif len(rxs) == 1:
        axs = axs[np.newaxis, :]
    elif len(slots) == 1:
        axs = axs[:, np.newaxis]

    # Build or reuse composite time index (must include gps_time)
    if times_index is None:
        times_index = (
            data[["gps_start", "time_index", "gps_time"]]
            .drop_duplicates()
            .sort_values(by=["gps_start", "time_index"], kind="mergesort")
            .reset_index(drop=True)
        )
    times_unique = times_index.copy()

    for ax in axs.flatten():
        ax.axis("off")

    for i, rx in enumerate(rxs):
        for j, slot in enumerate(slots):
            ax = axs[i][j]
            tile = data[(data["rx"] == rx) & (data["slot"] == slot)]
            if tile.empty:
                continue
            ax.axis("on")
            # Keep chronological across observations; join on composite times
            tile_times = times_unique.merge(
                tile.drop(columns=["gps_time"], errors="ignore"),
                on=["gps_start", "time_index"],
                how="left",
            )
            x_raw = tile_times[value_xx].to_numpy(dtype=float)
            y_raw = tile_times[value_yy].to_numpy(dtype=float)
            yx = _smooth_array(x_raw, smooth_window)
            yy = _smooth_array(y_raw, smooth_window)
            # Do not connect across gaps: preserve NaNs from raw
            yx[~np.isfinite(x_raw)] = np.nan
            yy[~np.isfinite(y_raw)] = np.nan
            # Break between different observations
            gps_start_arr = tile_times["gps_start"].to_numpy()
            breaks = np.concatenate(([False], gps_start_arr[1:] != gps_start_arr[:-1]))
            yx[breaks] = np.nan
            yy[breaks] = np.nan
            ax.plot(
                tile_times["gps_time"], yx,
                label="XX", color="#3366cc", linewidth=1.0,
            )
            ax.plot(
                tile_times["gps_time"], yy,
                label="YY", color="#dc3912", linewidth=1.0,
            )
            # title label
            name = tile["name"].iloc[0] if "name" in tile.columns else f"rx{rx} s{slot}"
            ax.set_title(str(name), fontsize=9)

    # global labels
    fig.supxlabel("GPS time (s)")
    fig.supylabel(ylabel)
    fig.suptitle(title)

    # Make a single legend
    handles = [
        plt.Line2D([0], [0], color="#3366cc", label="XX"),
        plt.Line2D([0], [0], color="#dc3912", label="YY"),
    ]
    fig.legend(handles=handles, loc="upper right")

    # Robust y-limits based on 1st-99th percentiles
    y_vals = np.concatenate([
        data[value_xx].to_numpy(dtype=float),
        data[value_yy].to_numpy(dtype=float),
    ], dtype=float)
    y_vals = y_vals[np.isfinite(y_vals)]
    if y_vals.size:
        lo, hi = np.nanpercentile(y_vals, [1.0, 99.0])
        for ax in np.ravel(axs):
            if hasattr(ax, 'set_ylim'):
                ax.set_ylim(lo, hi)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")


def plot_all_tiles_overlay_single(
    data: pd.DataFrame,
    *,
    value: str,
    ylabel: str,
    title: str,
    out_path: str,
    legend_max: int = 12,
    smooth_window: int = 4,
    timestep_sec: float = 8.0,
) -> None:
    """Plot all tiles overlaid in a single axes for a single value (XX or YY).

    - Different color per tile
    - Only the first `legend_max` tiles appear in the legend
    - Each tile's series is normalized by its median value
    """
    sns.set_context("talk")

    # Composite time order across observations
    times_unique = (
        data[["gps_start", "time_index"]]
        .drop_duplicates()
        .sort_values(by=["gps_start", "time_index"], kind="mergesort")
        .reset_index(drop=True)
    )
    times_unique["order_index"] = np.arange(len(times_unique))
    times_unique["gps_time"] = (
        times_unique["gps_start"].astype(float) +
        times_unique["time_index"].astype(float) * float(timestep_sec)
    )

    # Color palette large enough for many tiles
    groups = list(data.groupby(["rx", "slot"], sort=True))
    palette = sns.color_palette("husl", n_colors=max(len(groups), 3))

    fig, ax = plt.subplots(figsize=(12, 6))
    legend_handles: list[plt.Line2D] = []
    legend_labels: list[str] = []

    for idx, ((_rx, _slot), tile) in enumerate(groups):
        tile_times = times_unique.merge(
            tile.drop(columns=["gps_time"], errors="ignore"),
            on=["gps_start", "time_index"],
            how="left",
        )
        series = tile_times[value]
        series_raw = series.to_numpy(dtype=float)
        med = np.nanmedian(series_raw)
        if not np.isfinite(med):
            norm_series = series
        else:
            norm_series = series - med
        color = palette[idx]
        name = (
            tile["name"].iloc[0]
            if "name" in tile.columns and pd.notna(tile["name"].iloc[0])
            else f"rx{int(_rx)} s{int(_slot)}"
        )
        y_sm = _smooth_array(norm_series.to_numpy(dtype=float), smooth_window)
        # Do not connect across original gaps
        y_sm[~np.isfinite(series_raw)] = np.nan
        # Break between different observations
        gps_start_arr = tile_times["gps_start"].to_numpy()
        breaks = np.concatenate(([False], gps_start_arr[1:] != gps_start_arr[:-1]))
        y_sm[breaks] = np.nan
        (ln,) = ax.plot(
            tile_times["gps_time"],
            y_sm,
            color=color,
            alpha=0.2,
            linewidth=0.8,
            label=name if len(legend_labels) < legend_max else None,
        )
        if len(legend_labels) < legend_max:
            legend_handles.append(ln)
            legend_labels.append(name)

    ax.set_xlabel("GPS time (s)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if legend_handles:
        ax.legend(legend_handles, legend_labels, loc="upper right", ncol=2)

    # Robust y-limits (1st-99th percentiles) after normalization
    all_series = []
    for ((_rx, _slot), tile) in groups:
        tile_times = times_unique.merge(
            tile, on=["gps_start", "time_index"], how="left"
        )
        s = tile_times[value].to_numpy(dtype=float)
        med = np.nanmedian(s)
        if np.isfinite(med):
            s = s - med
        all_series.append(s)
    y_vals = np.array(all_series, dtype=float).ravel()
    y_vals = y_vals[np.isfinite(y_vals)]
    if y_vals.size:
        lo, hi = np.nanpercentile(y_vals, [1.0, 99.0])
        ax.set_ylim(lo, hi)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")


def plot_receiver_overlay_single(
    data: pd.DataFrame,
    *,
    value: str,
    ylabel: str,
    title: str,
    out_path: str,
    legend_max: int = 12,
    smooth_window: int = 4,
    timestep_sec: float = 8.0,
) -> None:
    """Plot one line per receiver: mean of tiles on each receiver.

    - For each receiver index `rx`, average across its tiles per time step
    - Median-subtract the receiver's series
    - Different color per receiver; only first `legend_max` in legend
    - Robust y-limits via 1st-99th percentiles
    """
    sns.set_context("talk")

    # Composite time order
    times_unique = (
        data[["gps_start", "time_index"]]
        .drop_duplicates()
        .sort_values(by=["gps_start", "time_index"], kind="mergesort")
        .reset_index(drop=True)
    )
    times_unique["order_index"] = np.arange(len(times_unique))
    times_unique["gps_time"] = (
        times_unique["gps_start"].astype(float) +
        times_unique["time_index"].astype(float) * float(timestep_sec)
    )

    # Group strictly by RX from TSV (8 tiles per receiver expected)
    receivers = np.sort(data["rx"].unique())
    palette = sns.color_palette("tab20", n_colors=max(len(receivers), 3))

    fig, ax = plt.subplots(figsize=(12, 6))
    legend_handles: list[plt.Line2D] = []
    legend_labels: list[str] = []
    all_series: list[np.ndarray] = []

    for idx, rx in enumerate(receivers):
        recv_df = data[data["rx"] == rx][["gps_start", "time_index", value]]
        # mean across tiles per time
        agg = (
            recv_df.groupby(["gps_start", "time_index"], as_index=False)[value]
            .mean()
        )
        merged = times_unique.merge(
            agg, on=["gps_start", "time_index"], how="left"
        )
        series = merged[value].to_numpy(dtype=float)
        med = np.nanmedian(series)
        if np.isfinite(med):
            series = series - med
        all_series.append(series)

        color = palette[idx % len(palette)]
        label = f"rx{int(rx):02d}" if len(legend_labels) < legend_max else None
        y_sm = _smooth_array(series, smooth_window)
        # Preserve gaps
        y_sm[~np.isfinite(series)] = np.nan
        # Break between different observations
        gps_start_arr = merged["gps_start"].to_numpy()
        breaks = np.concatenate(([False], gps_start_arr[1:] != gps_start_arr[:-1]))
        y_sm[breaks] = np.nan
        (ln,) = ax.plot(
            merged["gps_time"],
            y_sm,
            color=color,
            alpha=0.6,
            linewidth=1.2,
            label=label,
        )
        if label is not None:
            legend_handles.append(ln)
            legend_labels.append(label)

    ax.set_xlabel("GPS time (s)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    if legend_handles:
        ax.legend(legend_handles, legend_labels, loc="upper right", ncol=2)

    # Robust y-limits
    y_vals = np.array(all_series, dtype=float).ravel()
    y_vals = y_vals[np.isfinite(y_vals)]
    if y_vals.size:
        lo, hi = np.nanpercentile(y_vals, [1.0, 99.0])
        ax.set_ylim(lo, hi)

    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")

def main(argv: list[str] | None = None) -> None:
    """CLI entry point for plotting time series from phase_fits TSVs."""
    parser = argparse.ArgumentParser(
        description=(
            "Plot time series of lengths and intercepts from phase_fits.tsv files"
        )
    )
    parser.add_argument(
        "--dir", default=".", help="Directory to search for TSV files"
    )
    parser.add_argument(
        "--glob",
        dest="glob_pattern",
        default=None,
        help="Custom glob pattern for TSV files",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Only include files whose basename starts with this prefix",
    )
    parser.add_argument(
        "--out-dir", default=".", help="Directory to write output plots"
    )
    parser.add_argument("--title", default=None, help="Title prefix for plots")
    parser.add_argument("--show", action="store_true", help="Show plots interactively")
    parser.add_argument("--smooth", type=int, default=4, help="Smooth the time series")
    parser.add_argument(
        "--timestep-sec", type=float, default=8.0, help="Seconds per timestep"
    )
    parser.add_argument(
        "--dark", action="store_true", help="Use dark theme"
    )
    args = parser.parse_args(argv)

    if args.dark:
        plt.style.use("dark_background")

    files = find_phase_fits(
        directory=args.dir, glob_pattern=args.glob_pattern, prefix=args.prefix
    )
    data = load_timeseries(files)

    base_title = args.title or (args.prefix or "phase fits")
    os.makedirs(args.out_dir, exist_ok=True)

    # Create a complete times index with gps_time and filled gaps
    times_index = build_times_index(data, args.timestep_sec)

    # Lengths
    plot_grid_over_time(
        data,
        value_xx="length_xx",
        value_yy="length_yy",
        ylabel="length (m)",
        title=f"{base_title} - lengths over time",
        out_path=os.path.join(args.out_dir, f"{base_title} lengths_timeseries.png"),
        sharey=True,
        smooth_window=args.smooth,
        times_index=times_index,
    )

    # Intercepts (radians, wrapped)
    plot_grid_over_time(
        data,
        value_xx="intercept_xx",
        value_yy="intercept_yy",
        ylabel="intercept (rad)",
        title=f"{base_title} - intercepts over time",
        out_path=os.path.join(args.out_dir, f"{base_title} intercepts_timeseries.png"),
        sharey=True,
        smooth_window=args.smooth,
        times_index=times_index,
    )

    # # Overlay plots with all tiles together (separate XX and YY, median-normalized)
    # plot_all_tiles_overlay_single(
    #     data,
    #     value="length_xx",
    #     ylabel="Δlength (m)",
    #     title=f"{base_title} - lengths over time (all tiles, XX)",
    #     out_path=os.path.join(
    #         args.out_dir, f"{base_title} lengths_timeseries_all_xx.png"
    #     ),
    #     smooth_window=args.smooth,
    #     timestep_sec=args.timestep_sec,
    # )
    # plot_all_tiles_overlay_single(
    #     data,
    #     value="length_yy",
    #     ylabel="Δlength (m)",
    #     title=f"{base_title} - lengths over time (all tiles, YY)",
    #     out_path=os.path.join(
    #         args.out_dir, f"{base_title} lengths_timeseries_all_yy.png"
    #     ),
    #     smooth_window=args.smooth,
    #     timestep_sec=args.timestep_sec,
    # )

    # plot_all_tiles_overlay_single(
    #     data,
    #     value="intercept_xx",
    #     ylabel="Δintercept (rad)",
    #     title=f"{base_title} - intercepts over time (all tiles, XX)",
    #     out_path=os.path.join(
    #         args.out_dir, f"{base_title} intercepts_timeseries_all_xx.png"
    #     ),
    #     smooth_window=args.smooth,
    # )
    # plot_all_tiles_overlay_single(
    #     data,
    #     value="intercept_yy",
    #     ylabel="Δintercept (rad)",
    #     title=f"{base_title} - intercepts over time (all tiles, YY)",
    #     out_path=os.path.join(
    #         args.out_dir, f"{base_title} intercepts_timeseries_all_yy.png"
    #     ),
    #     smooth_window=args.smooth,
    # )

    # Receiver-average overlays (mean of 8 tiles per receiver)
    plot_receiver_overlay_single(
        data,
        value="length_xx",
        ylabel="mean Δlength (m)",
        title=f"{base_title} - receiver mean Δlength (XX)",
        out_path=os.path.join(
            args.out_dir, f"{base_title} lengths_timeseries_receiver_xx.png"
        ),
        smooth_window=args.smooth,
        timestep_sec=args.timestep_sec,
    )
    plot_receiver_overlay_single(
        data,
        value="length_yy",
        ylabel="mean Δlength (m)",
        title=f"{base_title} - receiver mean Δlength (YY)",
        out_path=os.path.join(
            args.out_dir, f"{base_title} lengths_timeseries_receiver_yy.png"
        ),
        smooth_window=args.smooth,
        timestep_sec=args.timestep_sec,
    )
    # plot_receiver_overlay_single(
    #     data,
    #     value="intercept_xx",
    #     ylabel="mean Δintercept (rad)",
    #     title=f"{base_title} - receiver mean Δintercept (XX)",
    #     out_path=os.path.join(
    #         args.out_dir, f"{base_title} intercepts_timeseries_receiver_xx.png"
    #     ),
    #     smooth_window=args.smooth,
    # )
    # plot_receiver_overlay_single(
    #     data,
    #     value="intercept_yy",
    #     ylabel="mean Δintercept (rad)",
    #     title=f"{base_title} - receiver mean Δintercept (YY)",
    #     out_path=os.path.join(
    #         args.out_dir, f"{base_title} intercepts_timeseries_receiver_yy.png"
    #     ),
    #     smooth_window=args.smooth,
    # )

    if args.show:
        plt.show()


if __name__ == "__main__":
    main()
