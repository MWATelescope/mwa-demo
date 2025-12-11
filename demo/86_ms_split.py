#!/usr/bin/env python
"""Split a Measurement Set by time to respect a size limit."""

import argparse
import contextlib
import os
import shutil
import sys
from pathlib import Path

import numpy as np
from casacore.tables import taql


def get_tree_size(path):
    """Return total size of files in given path and subdirs."""
    total = 0
    # Walk the directory to handle nested structure of MS
    for root, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            # Do not follow symlinks to avoid double counting or loops
            with contextlib.suppress(OSError):
                total += os.path.getsize(fp)
    return total


def parse_size(size_str):
    """Parse a size string like '1GB', '500MB' into bytes."""
    size_str = size_str.strip().upper()
    units = {'K': 1024, 'M': 1024**2, 'G': 1024**3, 'T': 1024**4}

    multiplier = 1
    # Check for unit suffix
    for unit, value in units.items():
        if size_str.endswith(unit):
            multiplier = value
            size_str = size_str[:-1]
            break
        if size_str.endswith(unit + 'B'):
            multiplier = value
            size_str = size_str[:-len(unit) - 1]
            break

    try:
        return int(float(size_str) * multiplier)
    except ValueError as err:
        raise ValueError(f"Invalid size format: {size_str}") from err


def main():
    """Run the main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Split a Measurement Set by time to respect a size limit."
    )
    parser.add_argument("ms", help="Path to input Measurement Set")
    parser.add_argument("--limit", required=True, help="Size limit (e.g. 100MB, 2GB)")
    parser.add_argument(
        "--out-fmt",
        default="{ms}_p{idx:03d}.ms",
        help="Output filename format. Vars: ms (stem), idx",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Calculate splits but do not write files"
    )

    args = parser.parse_args()

    ms_path = Path(args.ms)
    if not ms_path.exists():
        parser.error(f"File {ms_path} not found")

    # MS is a directory usually
    total_size = get_tree_size(ms_path)
    try:
        limit_bytes = parse_size(args.limit)
    except ValueError as e:
        parser.error(str(e))

    print(f"Input MS: {ms_path}")
    print(f"Total size: {total_size / 1024**3:.3f} GB ({total_size} bytes)")
    print(f"Limit: {limit_bytes / 1024**3:.3f} GB ({limit_bytes} bytes)")

    # Get unique times
    print("Reading times...")
    try:
        t = taql(f"select TIME from '{ms_path}'")
        times = np.unique(t.getcol("TIME"))
        t.close()
    except RuntimeError as e:
        print(f"Error reading MS with taql: {e}")
        sys.exit(1)

    n_times = len(times)
    print(f"Total time steps: {n_times}")

    if n_times == 0:
        print("No times found in MS.")
        sys.exit(0)

    # Estimate size per time step
    bytes_per_time = total_size / n_times
    print(f"Approx. bytes per time step: {bytes_per_time / 1024**2:.2f} MB")

    # Calculate steps per chunk
    steps_per_chunk = int(limit_bytes // bytes_per_time)

    if steps_per_chunk < 1:
        print(
            "Warning: Single time step exceeds size limit. Splitting one step per file."
        )
        steps_per_chunk = 1

    # Clamp steps_per_chunk
    steps_per_chunk = min(steps_per_chunk, n_times)

    print(f"Time steps per chunk: {steps_per_chunk}")

    num_chunks = int(np.ceil(n_times / steps_per_chunk))
    print(f"Will split into {num_chunks} files.")

    if args.dry_run:
        print("Dry run finished.")
        return

    ms_stem = ms_path.stem

    for i in range(num_chunks):
        start_idx = i * steps_per_chunk
        end_idx = min((i + 1) * steps_per_chunk, n_times)

        chunk_times = times[start_idx:end_idx]
        t_min = chunk_times[0]
        t_max = chunk_times[-1]

        out_name = args.out_fmt.format(ms=ms_stem, idx=i + 1)

        print(
            f"Writing chunk {i+1}/{num_chunks}: {out_name} "
            f"(Times {start_idx} to {end_idx-1})"
        )

        if os.path.exists(out_name):
            print(f"  Output {out_name} exists, removing...")
            if os.path.isdir(out_name):
                shutil.rmtree(out_name)
            else:
                os.remove(out_name)

        # Using high precision for float formatting to ensure we catch the boundaries
        # TIME is double precision.
        query = (
            f"select * from '{ms_path}' where "
            f"TIME >= {t_min:.10f} AND TIME <= {t_max:.10f}"
        )

        try:
            t_sub = taql(query)
            t_sub.copy(out_name, deep=True)
            t_sub.close()
        except Exception as e:
            print(f"Failed to write {out_name}: {e}")
            sys.exit(1)

    print("Done.")


if __name__ == "__main__":
    main()
