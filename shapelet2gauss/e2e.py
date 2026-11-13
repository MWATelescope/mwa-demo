#!/usr/bin/env python
"""End-to-end check: simulate one source with `hyperdrive vis-simulate` from the original
(shapelet) and converted (Gaussian) source lists and compare the visibilities.

    e2e.py <source name> <original.yaml> <converted.yaml> [--metafits F] [--ra R --dec D] [--outdir D]

The metafits of obs 1443210064 (EoR1, Phase II compact) is downloaded from the MWA metadata
service if --metafits is not given. Requires hyperdrive on PATH and pyuvdata.
"""
import argparse
import os
import re
import subprocess
import sys
import urllib.request

import numpy as np
import yaml
from pyuvdata import UVData


def extract(yaml_path, name):
    lines = open(yaml_path).read().split("\n")
    starts = [i for i, l in enumerate(lines) if re.match(r"^[^\s#-][^:]*:$", l)] + [len(lines)]
    for a, b in zip(starts[:-1], starts[1:]):
        if lines[a][:-1] == name:
            return yaml.load("\n".join(lines[a:b]), Loader=yaml.CSafeLoader)
    sys.exit(f"{name} not found in {yaml_path}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name")
    ap.add_argument("original")
    ap.add_argument("converted")
    ap.add_argument("--metafits", default=None)
    ap.add_argument("--ra", default=None)
    ap.add_argument("--dec", default=None)
    ap.add_argument("--outdir", default="e2e_out")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    metafits = a.metafits or os.path.join(a.outdir, "1443210064.metafits")
    if not os.path.exists(metafits):
        urllib.request.urlretrieve("https://ws.mwatelescope.org/metadata/fits?obs_id=1443210064", metafits)
    outs = []
    for tag, src in (("shape", a.original), ("gauss", a.converted)):
        d = extract(src, a.name)
        f = os.path.join(a.outdir, f"{a.name}_{tag}.yaml")
        yaml.dump(d, open(f, "w"), Dumper=yaml.CSafeDumper, default_flow_style=False, sort_keys=False)
        o = f.replace(".yaml", ".uvfits")
        if os.path.exists(o):
            os.remove(o)
        cmd = ["hyperdrive", "vis-simulate", "-s", f, "-m", metafits, "--no-beam", "--cpu",
               "-t", "1", "-c", "16", "-o", o, "--no-progress-bars"]
        if a.ra is not None:
            cmd += [f"--ra={a.ra}", f"--dec={a.dec}"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stderr[-2000:])
        outs.append((o, sum(len(v) for v in d.values())))
    ua = UVData.from_file(outs[0][0])
    ub = UVData.from_file(outs[1][0])
    xa = ua.data_array[..., 0]
    xb = ub.data_array[..., 0]
    dd = xb - xa
    uv = np.hypot(ua.uvw_array[:, 0], ua.uvw_array[:, 1])[:, None] * ua.freq_array[None, :] / 299792458.0
    rms = np.sqrt(np.mean(np.abs(dd) ** 2))
    print(f"{a.name}: {outs[0][1]} -> {outs[1][1]} components; |V| max {np.abs(xa).max():.3f} Jy; "
          f"diff rms {rms:.4f} max {np.abs(dd).max():.4f} -> rel rms {rms/np.abs(xa).max():.3%} "
          f"rel max {np.abs(dd).max()/np.abs(xa).max():.3%}")
    for lo, hi in [(0, 100), (100, 300), (300, 700), (700, 1500), (1500, 5000)]:
        m = (uv >= lo) & (uv < hi)
        if m.any():
            print(f"  |uv| {lo:5d}-{hi:5d} wavelengths: n={m.sum():6d} |V| mean {np.abs(xa[m]).mean():.4f} "
                  f"diff rms {np.sqrt(np.mean(np.abs(dd[m]) ** 2)):.4f}")


if __name__ == "__main__":
    main()
