#!/usr/bin/env python
"""Convert a hyperdrive YAML source list (points + Gaussians only) to a DP3 / BBS text sky model.

    yaml2dp3.py in.yaml out.skymodel [--patch source|single] [--patch-name NAME]

Spectral models:
  power_law         S = S0 (nu/nu0)^a                       -> LogarithmicSI=true, SpectralIndex=[a]
  curved_power_law  S = S0 (nu/nu0)^a exp(q ln^2(nu/nu0))   -> SpectralIndex=[a, q*ln(10)]
     (DP3: S = S0 (nu/nu0)^(c0 + c1 log10(nu/nu0) + ...), base/PointSource.cc)
  list              not supported (none in the MWA srclists); raises.
Gaussians: MajorAxis/MinorAxis are FWHM in arcsec and Orientation is the position angle in
degrees, as in hyperdrive. OrientationIsAbsolute is left at DP3's default (false): hyperdrive
also evaluates Gaussian envelopes in the phase-centre frame.
Shapelets raise: convert them first with shapelet2gauss.py.
Patches: one per hyperdrive source by default (the natural direction-dependent unit), or a
single patch containing everything (--patch single).
"""
import argparse
import math
import re
import sys

import yaml

LN10 = math.log(10.0)


def fmt_ra(deg):
    h = (deg % 360) / 15.0
    hh = int(h); m = (h - hh) * 60; mm = int(m); ss = (m - mm) * 60
    if ss >= 59.9995:
        ss = 0.0; mm += 1
    if mm == 60:
        mm = 0; hh = (hh + 1) % 24
    return f"{hh:02d}:{mm:02d}:{ss:08.5f}"


def fmt_dec(deg):
    sgn = "-" if deg < 0 else "+"
    d = abs(deg)
    dd = int(d); m = (d - dd) * 60; mm = int(m); ss = (m - mm) * 60
    if ss >= 59.9995:
        ss = 0.0; mm += 1
    if mm == 60:
        mm = 0; dd += 1
    return f"{sgn}{dd:02d}.{mm:02d}.{ss:08.5f}"


def spectral(ft):
    kind = list(ft)[0]
    if kind == "power_law":
        fd = ft[kind]["fd"]; terms = [ft[kind]["si"]]
    elif kind == "curved_power_law":
        fd = ft[kind]["fd"]; terms = [ft[kind]["si"], ft[kind]["q"] * LN10]
    else:
        raise ValueError(f"flux type {kind} not supported")
    stokes = [fd.get("i", 0.0), fd.get("q", 0.0), fd.get("u", 0.0), fd.get("v", 0.0)]
    stokes = [0.0 if abs(x) < 1e-30 else x for x in stokes]      # DP3 rejects denormals
    return stokes, fd["freq"], terms


def iter_sources(path):
    """Stream (name, components) without loading the whole file into one object."""
    lines = open(path).read().split("\n")
    starts = [i for i, l in enumerate(lines) if re.match(r"^[^\s#-][^:]*:$", l)] + [len(lines)]
    for a, b in zip(starts[:-1], starts[1:]):
        name = lines[a][:-1]
        yield name, yaml.load("\n".join(lines[a:b]), Loader=yaml.CSafeLoader)[name]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("infile")
    ap.add_argument("outfile")
    ap.add_argument("--patch", choices=["source", "single"], default="source")
    ap.add_argument("--patch-name", default="sky")
    a = ap.parse_args()
    n_src = n_comp = 0
    with open(a.outfile, "w") as out:
        out.write("Format = Name, Type, Patch, Ra, Dec, I, Q, U, V, ReferenceFrequency, "
                  "SpectralIndex, LogarithmicSI, MajorAxis, MinorAxis, Orientation\n")
        if a.patch == "single":
            out.write(f" , , {a.patch_name}, 00:00:00.0, +00.00.00.0\n")
        for name, comps in iter_sources(a.infile):
            pname = re.sub(r"[^A-Za-z0-9_+.-]", "_", name)
            if a.patch == "source":
                # patch position: brightest component
                c0 = max(comps, key=lambda c: spectral(c["flux_type"])[0][0])
                out.write(f" , , {pname}, {fmt_ra(c0['ra'])}, {fmt_dec(c0['dec'])}\n")
                patch = pname
            else:
                patch = a.patch_name
            for ci, c in enumerate(comps):
                ct = list(c["comp_type"])[0] if isinstance(c["comp_type"], dict) else c["comp_type"]
                stokes, f0, terms = spectral(c["flux_type"])
                if ct == "point":
                    typ, shape = "POINT", ", , , "
                elif ct == "gaussian":
                    g = c["comp_type"]["gaussian"]
                    typ, shape = "GAUSSIAN", f"{g['maj']:.6g}, {g['min']:.6g}, {g['pa']:.6g}"
                else:
                    sys.exit(f"{name}: component type {ct} not supported; run shapelet2gauss.py first")
                out.write(f"{pname}_{ci}, {typ}, {patch}, {fmt_ra(c['ra'])}, {fmt_dec(c['dec'])}, "
                          f"{stokes[0]:.8g}, {stokes[1]:.6g}, {stokes[2]:.6g}, {stokes[3]:.6g}, {f0:.8g}, "
                          f"[{', '.join(f'{t:.8g}' for t in terms)}], true, {shape}\n")
                n_comp += 1
            n_src += 1
    print(f"wrote {a.outfile}: {n_src} sources, {n_comp} components")


if __name__ == "__main__":
    main()
