#!/usr/bin/env python3
"""
Plot alpha, beta, and gain time series for the top-N sources from ionosub JSON files.

Ranking for "top" sources defaults to highest mean absolute gain across time.

Usage:
demo/84_iono.py \
    --glob "ionosub/hyp_peel_109*_ionosub_ssins_30l_src8k_300it_160kHz_i1000_uv.json" \
    --out-dir ionosub --top 10 --rank-by brightness --sort-by ra \
    --timestep-sec 2 --smooth 8 --dark --show
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import defaultdict
from contextlib import suppress

import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns

GPS_RE = re.compile(r"(?<!\d)(\d{10})(?!\d)")


def extract_time_from_filename(path: str) -> int | None:
    """Extract a 10-digit GPS time from the filename if present."""
    base = os.path.basename(path)
    m = GPS_RE.search(base)
    return int(m.group(1)) if m else None


def load_json(path: str) -> dict:
    """Load a JSON file into a dict."""
    with open(path) as f:
        return json.load(f)


def coerce_to_source_maps(
    doc: dict,
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """Return (alpha_map, beta_map, gain_map) as dicts name->float.

    Tries multiple schema variants; missing metrics return empty dicts.
    """
    alpha: dict[str, float] = {}
    beta: dict[str, float] = {}
    gain: dict[str, float] = {}

    # Variant 1: list of sources with per-source fields
    if isinstance(doc.get("sources"), list):
        for s in doc["sources"]:
            name = str(s.get("name", ""))
            if not name:
                continue
            if "alpha" in s:
                with suppress(Exception):
                    alpha[name] = float(s["alpha"])  # type: ignore
            if "beta" in s:
                with suppress(Exception):
                    beta[name] = float(s["beta"])  # type: ignore
            if "gain" in s:
                with suppress(Exception):
                    gain[name] = float(s["gain"])  # type: ignore

    # Variant 2/3: dict-of-dicts
    for akey in ("alphas", "alpha", "ALPHAS", "ALPHA"):
        if isinstance(doc.get(akey), dict):
            for k, v in doc[akey].items():
                try:
                    alpha[str(k)] = float(v)  # type: ignore
                except Exception:
                    continue
            break
    for bkey in ("betas", "beta", "BETAS", "BETA"):
        if isinstance(doc.get(bkey), dict):
            for k, v in doc[bkey].items():
                try:
                    beta[str(k)] = float(v)  # type: ignore
                except Exception:
                    continue
            break
    for gkey in ("gains", "gain", "GAINS", "GAIN"):
        if isinstance(doc.get(gkey), dict):
            for k, v in doc[gkey].items():
                try:
                    gain[str(k)] = float(v)  # type: ignore
                except Exception:
                    continue
            break

    # Variant 4: lists with src_names
    if isinstance(doc.get("src_names"), list):
        names = [str(x) for x in doc["src_names"]]
        for key, target in (("alpha", alpha), ("beta", beta), ("gain", gain)):
            arr = doc.get(key)
            if isinstance(arr, list) and len(arr) == len(names):
                for n, v in zip(names, arr):
                    try:
                        target[n] = float(v)  # type: ignore
                    except Exception:
                        continue

    # Variant 5: mapping of source -> {alphas: [...], betas: [...], gains: [...]}
    # Reduce each array to a robust statistic (median), ignoring nulls
    try:
        for src_name, vals in doc.items():
            if not isinstance(vals, dict):
                continue
            # Accept both plural and singular keys
            for key, _target in (("alphas", alpha), ("alpha", alpha)):
                if isinstance(vals.get(key), list):
                    arr = np.array(vals[key], dtype=float)
                    med = float(np.nanmedian(arr)) if arr.size else np.nan
                    if np.isfinite(med):
                        alpha[str(src_name)] = med
                    break
            for key, _target in (("betas", beta), ("beta", beta)):
                if isinstance(vals.get(key), list):
                    arr = np.array(vals[key], dtype=float)
                    med = float(np.nanmedian(arr)) if arr.size else np.nan
                    if np.isfinite(med):
                        beta[str(src_name)] = med
                    break
            for key, _target in (("gains", gain), ("gain", gain)):
                if isinstance(vals.get(key), list):
                    arr = np.array(vals[key], dtype=float)
                    med = float(np.nanmedian(arr)) if arr.size else np.nan
                    if np.isfinite(med):
                        gain[str(src_name)] = med
                    break
    except Exception:
        # fall back silently if structure doesn't match
        pass

    return alpha, beta, gain


def select_top_by_series(series_map: dict[str, list[float]], top: int) -> list[str]:
    """Pick top names by mean absolute magnitude across concatenated series."""
    scored = []
    for name, vals in series_map.items():
        arr = np.array(vals, dtype=float)
        if arr.size:
            score = float(np.nanmean(np.abs(arr)))
        else:
            score = -np.inf
        scored.append((name, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [name for name, _ in scored[:top]]


def _smooth_array(values: list[float] | np.ndarray, window: int) -> np.ndarray:
    """Centered moving average with NaN handling; window<=1 returns input."""
    try:
        arr = np.array(values, dtype=float)
    except Exception:
        return np.asarray(values)
    if window is None or window <= 1:
        return arr
    try:
        import pandas as _pd  # type: ignore

        return (
            _pd.Series(arr, dtype=float)
            .rolling(window=window, min_periods=1, center=True)
            .mean()
            .to_numpy()
        )
    except Exception:
        # Fallback: weighted convolution treating NaNs as 0 with mask
        vals = arr.astype(float)
        mask = np.isfinite(vals).astype(float)
        vals[~np.isfinite(vals)] = 0.0
        kernel = np.ones(int(window), dtype=float)
        num = np.convolve(vals, kernel, mode="same")
        den = np.convolve(mask, kernel, mode="same")
        den[den == 0] = 1.0
        return num / den


def plot_metric(
    timepoints: dict[str, list[float]] | list[int] | None,
    series_map: dict[str, list[float]],
    top_names: list[str],
    title: str,
    ylabel: str,
    out_path: str,
    smooth_window: int = 1,
    show: bool = False,
    expected_step: float | None = None,
) -> None:
    """Plot a metric for the selected top sources across time."""
    sns.set_context("talk")
    plt.figure(figsize=(12, 6))
    palette = sns.color_palette("husl", n_colors=max(len(top_names), 3))
    handles = []
    labels = []
    uses_gps_axis = False
    for i, name in enumerate(top_names):
        y = series_map.get(name)
        if y is None:
            continue
        # Build x-axis per-series
        if isinstance(timepoints, dict):
            x = timepoints.get(name, list(range(len(y))))
        elif isinstance(timepoints, list):
            x = timepoints if len(timepoints) == len(y) else list(range(len(y)))
        else:
            x = list(range(len(y)))
        y_sm = _smooth_array(y, smooth_window)
        # Break lines across large time gaps
        if expected_step and isinstance(x, list) and len(x) == len(y_sm) and len(x) > 1:
            try:
                x_arr = np.array(x, dtype=float)
                deltas = np.diff(x_arr)
                gap_idx = np.where(deltas > (expected_step * 1.5))[0]
                if gap_idx.size:
                    y_sm = y_sm.astype(float)
                    # set point at the gap start to NaN so matplotlib breaks the line
                    y_sm[gap_idx] = np.nan
            except Exception:
                pass
        if (
            isinstance(x, list) and
            x and
            isinstance(x[0], (int, float)) and
            float(x[0]) > 1e8
        ):
            uses_gps_axis = True
        (ln,) = plt.plot(
            x,
            y_sm,
            color=palette[i],
            alpha=0.6,
            linewidth=1.2,
            label=name if len(labels) < 10 else None,
        )
        if len(labels) < 10:
            handles.append(ln)
            labels.append(name)
    plt.xlabel("GPS time (s)" if uses_gps_axis else "time index")
    plt.ylabel(ylabel)
    plt.title(title)
    if handles:
        plt.legend(handles=handles, labels=labels, loc="upper right", ncol=2)
    # Robust y-limits
    all_vals = np.array(
        [v for name in top_names for v in (series_map.get(name) or [])], dtype=float
    )
    all_vals = all_vals[np.isfinite(all_vals)]
    if all_vals.size:
        lo, hi = np.nanpercentile(all_vals, [1.0, 99.0])
        plt.ylim(lo, hi)
    plt.tight_layout()
    if show:
        plt.show()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")


def main() -> None:
    """CLI entrypoint for plotting alpha/beta/gain from ionosub JSONs."""
    parser = argparse.ArgumentParser(
        description="Plot alpha/beta/gain time series from ionosub JSON files"
    )
    parser.add_argument("paths", nargs="+", help="ionosub JSON files")
    parser.add_argument(
        "--out-dir", default="ionosub", help="Output directory for plots"
    )
    parser.add_argument(
        "--top", type=int, default=10, help="Number of top sources to plot"
    )
    parser.add_argument(
        "--rank-by",
        choices=["alpha", "beta", "gain", "brightness"],
        default="brightness",
        help="Ranking metric: series magnitude or 'brightness' count",
    )
    parser.add_argument(
        "--sort-by",
        choices=["name", "ra"],
        default="name",
        help="Order of plotted series (legend): by name or RA",
    )
    parser.add_argument(
        "--brightness-top-frac",
        type=float,
        default=0.1,
        help="For rank-by=brightness, fraction of sources per file counted as 'high'",
    )
    parser.add_argument(
        "--smooth", type=int, default=1, help="Centered moving average window size"
    )
    parser.add_argument("--show", action="store_true", help="Show plots interactively")
    parser.add_argument("--dark", action="store_true", help="Use dark theme")
    parser.add_argument(
        "--timestep-sec",
        type=float,
        default=8.0,
        help="Per-subintegration cadence (seconds) to construct time axis",
    )
    args = parser.parse_args()

    if args.dark:
        plt.style.use("dark_background")

    if not args.paths:
        raise SystemExit("No JSON files provided")

    # Build per-metric, per-source concatenated series and per-source time vectors
    time_map_alpha: dict[str, list[float]] = defaultdict(list)
    time_map_beta: dict[str, list[float]] = defaultdict(list)
    time_map_gain: dict[str, list[float]] = defaultdict(list)
    series_alpha: dict[str, list[float]] = defaultdict(list)
    series_beta: dict[str, list[float]] = defaultdict(list)
    series_gain: dict[str, list[float]] = defaultdict(list)
    # Pre-scan to collect RA per source and brightness ordering if needed
    ra_map_global: dict[str, float] = {}
    brightness_count: dict[str, int] = defaultdict(int)

    for p in args.paths:
        t = extract_time_from_filename(p)
        doc = load_json(p)
        # collect RA per source
        try:
            for src_name, vals in doc.items():
                if not isinstance(vals, dict):
                    continue
                pos = vals.get("weighted_catalogue_pos_j2000") or vals.get("pos")
                if isinstance(pos, dict) and "ra" in pos:
                    with suppress(Exception):
                        ra_map_global[str(src_name)] = float(pos["ra"])  # type: ignore
        except Exception:
            pass
        # collect brightness ranking per file (median gain)
        try:
            gain_per_src: list[tuple[str, float]] = []
            for src_name, vals in doc.items():
                if not isinstance(vals, dict):
                    continue
                arr = vals.get("gains") or vals.get("gain")
                if isinstance(arr, list) and arr:
                    arr_np = np.array(arr, dtype=float)
                    med = float(np.nanmedian(arr_np)) if arr_np.size else np.nan
                    if np.isfinite(med):
                        gain_per_src.append((str(src_name), med))
            if gain_per_src:
                gain_per_src.sort(key=lambda x: x[1], reverse=True)
                k = max(1, int(len(gain_per_src) * args.brightness_top_frac))
                for name, _ in gain_per_src[:k]:
                    brightness_count[name] += 1
        except Exception:
            pass
        # Determine segment length from any available array, and compute segment times
        seg_len = 0
        try:
            for vals in doc.values():
                if isinstance(vals, dict) and isinstance(vals.get("gains"), list):
                    seg_len = len(vals["gains"])  # type: ignore
                    break
            if seg_len == 0:
                for vals in doc.values():
                    if isinstance(vals, dict) and isinstance(vals.get("alphas"), list):
                        seg_len = len(vals["alphas"])  # type: ignore
                        break
        except Exception:
            seg_len = 0
        seg_times: list[float] = []
        if seg_len:
            base = float(t) if t is not None else 0.0
            step = float(args.timestep_sec)
            seg_times = [base + i * step for i in range(seg_len)]

        # For each source, extend series with full arrays if present and append times
        for src_name, vals in doc.items():
            if not isinstance(vals, dict):
                continue
            # alpha / beta / gain arrays
            with suppress(Exception):
                arr = vals.get("alphas") or vals.get("alpha")
                if isinstance(arr, list):
                    arr_np = np.array(arr, dtype=float)
                    series_alpha[str(src_name)].extend(arr_np.tolist())
                    if seg_times:
                        time_map_alpha[str(src_name)].extend(seg_times[: len(arr_np)])
            with suppress(Exception):
                arr = vals.get("betas") or vals.get("beta")
                if isinstance(arr, list):
                    arr_np = np.array(arr, dtype=float)
                    series_beta[str(src_name)].extend(arr_np.tolist())
                    if seg_times:
                        time_map_beta[str(src_name)].extend(seg_times[: len(arr_np)])
            with suppress(Exception):
                arr = vals.get("gains") or vals.get("gain")
                if isinstance(arr, list):
                    arr_np = np.array(arr, dtype=float)
                    series_gain[str(src_name)].extend(arr_np.tolist())
                    if seg_times:
                        time_map_gain[str(src_name)].extend(seg_times[: len(arr_np)])

    if not series_alpha and not series_beta and not series_gain:
        raise SystemExit("No usable alpha/beta/gain data found in JSONs.")

    # Prepare timepoints: prefer per-source GPS time vectors if available
    any_alpha_times = any(len(v) > 0 for v in time_map_alpha.values())
    any_beta_times = any(len(v) > 0 for v in time_map_beta.values())
    any_gain_times = any(len(v) > 0 for v in time_map_gain.values())
    timepoints_alpha = time_map_alpha if any_alpha_times else None
    timepoints_beta = time_map_beta if any_beta_times else None
    timepoints_gain = time_map_gain if any_gain_times else None

    # Pick top names
    if args.rank_by in ("alpha", "beta", "gain"):
        sel_map = {"alpha": series_alpha, "beta": series_beta, "gain": series_gain}[
            args.rank_by
        ]
        top_names = select_top_by_series(sel_map, top=args.top)
    else:
        top_names = []

    # Alternative ranking: brightness count
    if args.rank_by not in ("alpha", "beta", "gain") or not top_names:
        # Default to brightness-based if chosen (extend choices if needed)
        # Using computed brightness_count
        if brightness_count:
            sorted_bright = sorted(
                brightness_count.items(), key=lambda x: x[1], reverse=True
            )
            top_names = [name for name, _ in sorted_bright[: args.top]]
        else:
            # fallback: by gain
            top_names = select_top_by_series(series_gain, top=args.top)

    # Optional sort by RA
    if args.sort_by == "ra":
        top_names.sort(key=lambda n: (ra_map_global.get(n, float("inf")), n))

    os.makedirs(args.out_dir, exist_ok=True)

    plot_metric(
        timepoints_alpha,
        series_alpha,
        top_names,
        title="Alpha of top sources over time",
        ylabel="alpha",
        out_path=os.path.join(args.out_dir, "ionosub_alpha_top.png"),
        smooth_window=args.smooth,
        show=args.show,
        expected_step=float(args.timestep_sec)
        if timepoints_alpha is not None
        else None,
    )
    plt.close()

    plot_metric(
        timepoints_beta,
        series_beta,
        top_names,
        title="Beta of top sources over time",
        ylabel="beta",
        out_path=os.path.join(args.out_dir, "ionosub_beta_top.png"),
        smooth_window=args.smooth,
        show=args.show,
        expected_step=float(args.timestep_sec) if timepoints_beta is not None else None,
    )
    plt.close()

    plot_metric(
        timepoints_gain,
        series_gain,
        top_names,
        title="Gain of top sources over time",
        ylabel="gain",
        out_path=os.path.join(args.out_dir, "ionosub_gain_top.png"),
        smooth_window=args.smooth,
        show=args.show,
        expected_step=float(args.timestep_sec) if timepoints_gain is not None else None,
    )
    plt.close()


if __name__ == "__main__":
    main()
