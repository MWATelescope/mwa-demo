#!/usr/bin/env python
"""
Make a "negdec" sky model: a LoTSS-DR2 field mirrored into the southern sky.

This reproduces the transform behind ``lotss_p129+33_negdec.skymodel`` (the
sky model of the SP-5941 AA2 simulation) and applies it to make a field
centred on EoR1.

The transform, reverse-engineered by matching every component of
``lotss_p129+33_negdec.skymodel`` to LoTSS-DR2 (Shimwell et al. 2022,
VizieR J/A+A/659/A1/catalog):

1. select LoTSS-DR2 sources within ``--radius`` (8.5 deg) of the field centre
   (129.3395, +32.8915 for the original;
   this centre and radius select exactly the 135,732 published components);
2. negate the declination, keep the right ascension (a mirror in the equator,
   so the field lands at Dec -32.8915 and the source pattern is mirrored);
3. Stokes I = ``SpeakTot`` (total flux density at 144 MHz, mJy -> Jy); Q=U=V=0;
4. shape = deconvolved size ``DCMaj``, ``DCMin`` (arcsec) and the fitted
   position angle ``PA`` (deg; equal to ``DCPA`` except for unresolved
   sources, whose ``DCPA`` is 0), not mirrored; ``POINT`` when ``DCMaj`` = 0,
   otherwise ``GAUSSIAN``;
5. reference frequency 144 MHz, spectral index -0.7 for every source, RM 0.

LoTSS-DR2 does not cover RA 60 deg, and near RA 129 it stops at Dec +25, so a
cone at (129.3, +27) is half empty. The EoR1 version therefore takes the fully
covered LoTSS field at (0, +27) (``--field 0 27``), applies steps 1-5, which
puts it on EoR0 (0, -27), then rotates it to EoR1 (``--target 60 -27``). As the
flipped centre already has Dec -27, the rotation is a pure shift of +60 deg in
right ascension, which preserves all source separations exactly.

Outputs ``<name>.skymodel`` (DP3/makesourcedb, read by DP3, rapthor and
``hyperdrive -i dp3``) and ``<name>.osm`` (OSKAR sky model).

usage:
  20_oskar_skymodel.py --field 0 27 --target 60 -27 --name eor1_negdec
  # reproduce SP-5941's model and compare it with the published one
  20_oskar_skymodel.py --field 129.3395 32.8915 --name p129+33_negdec \
      --compare lotss_p129+33_negdec.skymodel
"""

import argparse
import os
import urllib.parse
import urllib.request

import numpy as np

VIZIER = "https://vizier.cds.unistra.fr/viz-bin/asu-tsv"
CATALOG = "J/A+A/659/A1/catalog"
COLUMNS = ["Source", "RAJ2000", "DEJ2000", "SpeakTot", "DCMaj", "DCMin", "PA"]
FORMAT = (
    "FORMAT = Name, Type, Ra, Dec, I, Q, U, V, MajorAxis, MinorAxis, "
    "Orientation, ReferenceFrequency, SpectralIndex='[]', RotationMeasure"
)
REF_FREQ_HZ = 144e6
SPECTRAL_INDEX = -0.7


def query_lotss(ra, dec, radius, cache):
    """Cone search LoTSS-DR2 on VizieR, caching the TSV."""
    if not os.path.exists(cache):
        params = {
            "-source": CATALOG,
            "-c": f"{ra:+.5f}{dec:+.5f}",
            "-c.rd": f"{radius}",
            "-out": ",".join(COLUMNS),
            "-out.max": "unlimited",
            "-sort": "_r",
        }
        url = f"{VIZIER}?{urllib.parse.urlencode(params)}"
        print(f"querying {url}")
        with urllib.request.urlopen(url, timeout=600) as resp:
            data = resp.read()
        with open(cache, "wb") as f:
            f.write(data)
    rows = []
    with open(cache) as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) != len(COLUMNS) or not parts[0].startswith("ILTJ"):
                continue
            rows.append(parts)
    cat = {c: np.array([r[i].strip() for r in rows]) for i, c in enumerate(COLUMNS)}
    for c in COLUMNS[1:]:
        cat[c] = cat[c].astype(float)
    print(f"{len(rows)} LoTSS-DR2 sources within {radius} deg of {ra}, {dec}")
    return cat


def rotate_field(ra, dec, centre, target):
    """Rotate positions so that centre lands on target, preserving offsets."""
    from astropy import units as u
    from astropy.coordinates import SkyCoord

    src = SkyCoord(ra * u.deg, dec * u.deg)
    c0 = SkyCoord(centre[0] * u.deg, centre[1] * u.deg)
    c1 = SkyCoord(target[0] * u.deg, target[1] * u.deg)
    off = src.transform_to(c0.skyoffset_frame())
    out = SkyCoord(off.lon, off.lat, frame=c1.skyoffset_frame()).icrs
    return out.ra.deg, out.dec.deg


def fmt_ra(deg):
    """Format RA as hh:mm:ss.ssss."""
    s = (deg % 360) / 15 * 3600
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if round(s, 4) >= 60:
        s, m = 0.0, m + 1
    return f"{int(h):02d}:{int(m):02d}:{s:07.4f}"


def fmt_dec(deg):
    """Format Dec as sdd.mm.ss.ssss (DP3's dotted format)."""
    sign = "-" if deg < 0 else "+"
    s = abs(deg) * 3600
    d, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    if round(s, 4) >= 60:
        s, m = 0.0, m + 1
    return f"{sign}{int(d):02d}.{int(m):02d}.{s:07.4f}"


def write_dp3(path, ra, dec, flux, maj, mnr, pa):
    """Write a DP3 (makesourcedb) sky model in the SP-5941 layout."""
    with open(path, "w") as f:
        f.write(FORMAT + "\n\n")
        for i in range(len(ra)):
            kind = "POINT" if maj[i] == 0 else "GAUSSIAN"
            f.write(
                f"src{i}, {kind}, {fmt_ra(ra[i])}, {fmt_dec(dec[i])}, "
                f"{flux[i]:.6f}, 0.0, 0.0, 0.0, {maj[i]:.6f}, {mnr[i]:.6f}, "
                f"{pa[i]:.6f}, {REF_FREQ_HZ:.1f}, [{SPECTRAL_INDEX}], 0.0\n"
            )


def write_osm(path, ra, dec, flux, maj, mnr, pa):
    """Write an OSKAR sky model (RA, Dec, I, Q, U, V, f0, SI, RM, maj, min, PA)."""
    n = len(ra)
    zeros = np.zeros(n)
    data = np.column_stack(
        [ra % 360, dec, flux, zeros, zeros, zeros]
        + [np.full(n, REF_FREQ_HZ), np.full(n, SPECTRAL_INDEX), zeros]
        + [maj, mnr, pa]
    )
    header = (
        f"Number of sources: {n}\n"
        "RA (deg), Dec (deg), I (Jy), Q (Jy), U (Jy), V (Jy), Ref. freq. (Hz), "
        "Spectral index, Rotation measure (rad/m^2), FWHM major (arcsec), "
        "FWHM minor (arcsec), Position angle (deg)"
    )
    np.savetxt(path, data, fmt="%.8f", header=header)


def read_dp3(path):
    """Read positions, flux and shape from a DP3 sky model (SP-5941 layout)."""
    out = []
    with open(path) as f:
        lines = f.readlines()
    for line in lines:
        if line.startswith(("#", "FORMAT")) or not line.strip():
            continue
        p = [x.strip() for x in line.split(",")]
        h, m, s = p[2].split(":")
        ra = 15 * (int(h) + int(m) / 60 + float(s) / 3600)
        sign = -1 if p[3].startswith("-") else 1
        d, dm, ds = p[3].lstrip("+-").split(".", 2)
        dec = sign * (int(d) + int(dm) / 60 + float(ds) / 3600)
        out.append([ra, dec, float(p[4]), float(p[8]), float(p[9]), float(p[10])])
    return np.array(out)


def compare(path, ra, dec, flux, maj, mnr, pa):
    """Match a reference sky model to ours by position and report differences."""
    ref = read_dp3(path)
    ours = np.column_stack([ra, dec, flux, maj, mnr, pa])
    print(f"reference {path}: {len(ref)} sources, ours: {len(ours)}")
    key = lambda a: np.round(a[:, 0] * 3600, 1) * 1e7 + np.round(a[:, 1] * 3600, 1)  # noqa: E731
    k_ref, k_our = key(ref), key(ours)
    common, i_ref, i_our = np.intersect1d(k_ref, k_our, return_indices=True)
    print(f"matched to 0.1 arcsec: {len(common)}")
    for j, name in enumerate(["I (Jy)", "maj", "min", "PA"], start=2):
        diff = np.abs(ref[i_ref, j] - ours[i_our, j])
        print(f"  max |diff| {name}: {diff.max():.3g}")
    print(f"  total flux ref {ref[:, 2].sum():.3f} Jy, ours {flux.sum():.3f} Jy")


def main():
    """Query, transform and write the sky model."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--field",
        nargs=2,
        type=float,
        required=True,
        metavar=("RA", "DEC"),
        help="LoTSS field centre (deg)",
    )
    parser.add_argument("--radius", type=float, default=8.5, help="cone (deg)")
    parser.add_argument(
        "--target",
        nargs=2,
        type=float,
        metavar=("RA", "DEC"),
        help="rotate the flipped field centre to here (deg)",
    )
    parser.add_argument("--name", required=True, help="output basename")
    parser.add_argument("--outdir", default=".")
    parser.add_argument("--compare", help="reference DP3 sky model to compare")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    ra0, dec0 = args.field
    cache = f"{args.outdir}/lotss_dr2_{ra0:.4f}{dec0:+.4f}_r{args.radius}.tsv"
    cat = query_lotss(ra0, dec0, args.radius, cache)
    ra, dec = cat["RAJ2000"], -cat["DEJ2000"]
    if args.target:
        ra, dec = rotate_field(ra, dec, (ra0, -dec0), args.target)
    flux = cat["SpeakTot"] / 1e3
    maj, mnr, pa = cat["DCMaj"], cat["DCMin"], cat["PA"]

    base = f"{args.outdir}/{args.name}"
    write_dp3(f"{base}.skymodel", ra, dec, flux, maj, mnr, pa)
    write_osm(f"{base}.osm", ra, dec, flux, maj, mnr, pa)
    n_g = int((maj > 0).sum())
    print(
        f"wrote {base}.skymodel and {base}.osm: {len(ra)} sources "
        f"({n_g} Gaussian), {flux.sum():.1f} Jy at 144 MHz"
    )
    if args.compare:
        compare(args.compare, ra, dec, flux, maj, mnr, pa)


if __name__ == "__main__":
    main()
