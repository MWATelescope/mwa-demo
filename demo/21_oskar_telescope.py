#!/usr/bin/env python
"""
Write OSKAR telescope models for SKA-Low AA2, MWA Phase III (256T) and both.

AA2 is rebuilt from the metadata of the SP-5941 simulation
(``SP-5941_AA2_25G.zip`` on the srcnet Pawsey bucket). That zip holds a single
OSKAR-written MeasurementSet and no telescope model, but OSKAR >= 2.12 writes
everything needed to rebuild one:

- ``ANTENNA/POSITION``: station centres (ITRF/ECEF, metres)
- ``PHASED_ARRAY/COORDINATE_AXES``: per-station PQR -> ECEF rotation
- ``PHASED_ARRAY/ELEMENT_OFFSET``: element offsets in ECEF, so that
  ``COORDINATE_AXES.T @ ELEMENT_OFFSET`` is the station's ``layout.txt``
- ``FEED/RECEPTOR_ANGLE``: the feed angles (``feed_angle.txt``)
- ``OBSERVATION/ARRAY_CENTER``: the telescope reference position

Only these small subtables are needed, so by default they are read straight out
of the remote zip with HTTP range requests (about 1 MB instead of 25.6 GB).

The MWA 256T layout comes from a Phase III (MWAX, 256 tile) metafits via
mwalib. Each tile is a 4x4 grid of dipoles with 1.1 m spacing.

The combined model ("case h") puts the 68 AA2 stations and the 256 MWA tiles in
one OSKAR telescope with heterogeneous station types; each station has its own
directory, so OSKAR evaluates a different station beam for each type.

usage: 21_oskar_telescope.py --metafits 1476560224.metafits --outdir telescopes/
"""

import argparse
import io
import os
import shutil
import tempfile
import urllib.request
import zipfile

import numpy as np

SP5941_URL = "https://projects.pawsey.org.au/srcnet/SP-5941_AA2_25G.zip"
SP5941_MS = "visibility.scan-400.ms"
SUBTABLES = ["ANTENNA", "FEED", "PHASED_ARRAY", "OBSERVATION", "FIELD"]

# MWA array centre (mwalib / Marlu constants)
MWA_LON_DEG = 116.67081523611111
MWA_LAT_DEG = -26.703319405555554
MWA_ALT_M = 377.827
MWA_DIPOLE_SEP_M = 1.1

# WGS84
WGS84_A = 6378137.0
WGS84_F = 1 / 298.257223563
WGS84_E2 = WGS84_F * (2 - WGS84_F)


class HttpRangeFile(io.RawIOBase):
    """Seekable read-only file over HTTP range requests (enough for zipfile)."""

    def __init__(self, url):
        """Open url, using a HEAD request to get its size."""
        self.url = url
        self.pos = 0
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req) as resp:
            self.size = int(resp.headers["Content-Length"])

    def seekable(self):
        """Is seekable."""
        return True

    def readable(self):
        """Is readable."""
        return True

    def tell(self):
        """Return the current position."""
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        """Move the position."""
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        else:
            self.pos = self.size + offset
        return self.pos

    def read(self, n=-1):
        """Read n bytes from the current position."""
        if n is None or n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        end = min(self.pos + n, self.size) - 1
        req = urllib.request.Request(
            self.url, headers={"Range": f"bytes={self.pos}-{end}"}
        )
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
        self.pos += len(data)
        return data

    def readinto(self, b):
        """Read into a buffer."""
        data = self.read(len(b))
        b[: len(data)] = data
        return len(data)


def fetch_sp5941_subtables(src, dest):
    """Extract the MS subtables we need from a local or remote SP-5941 zip."""
    if src.startswith("http"):
        src = HttpRangeFile(src)
    with zipfile.ZipFile(src) as zf:
        for info in zf.infolist():
            parts = info.filename.split("/")
            if len(parts) > 2 and parts[1] in SUBTABLES and not info.is_dir():
                zf.extract(info, dest)
    return os.path.join(dest, SP5941_MS)


def ecef_to_geodetic(xyz):
    """Convert ECEF (m) to WGS84 longitude, latitude (deg) and height (m)."""
    x, y, z = xyz
    lon = np.arctan2(y, x)
    r = np.hypot(x, y)
    lat = np.arctan2(z, r * (1 - WGS84_E2))
    for _ in range(10):
        n = WGS84_A / np.sqrt(1 - WGS84_E2 * np.sin(lat) ** 2)
        h = r / np.cos(lat) - n
        lat = np.arctan2(z, r * (1 - WGS84_E2 * n / (n + h)))
    n = WGS84_A / np.sqrt(1 - WGS84_E2 * np.sin(lat) ** 2)
    h = r / np.cos(lat) - n
    return np.degrees(lon), np.degrees(lat), h


def geodetic_to_ecef(lon_deg, lat_deg, h):
    """Convert WGS84 longitude, latitude (deg) and height (m) to ECEF (m)."""
    lon, lat = np.radians(lon_deg), np.radians(lat_deg)
    n = WGS84_A / np.sqrt(1 - WGS84_E2 * np.sin(lat) ** 2)
    return np.array(
        [
            (n + h) * np.cos(lat) * np.cos(lon),
            (n + h) * np.cos(lat) * np.sin(lon),
            (n * (1 - WGS84_E2) + h) * np.sin(lat),
        ]
    )


def enu_to_ecef_matrix(lon_deg, lat_deg):
    """Return the matrix whose columns are local East, North, Up in ECEF."""
    lon, lat = np.radians(lon_deg), np.radians(lat_deg)
    east = [-np.sin(lon), np.cos(lon), 0.0]
    north = [-np.sin(lat) * np.cos(lon), -np.sin(lat) * np.sin(lon), np.cos(lat)]
    up = [np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)]
    return np.array([east, north, up]).T


def read_aa2(ms):
    """Read AA2 stations from the SP-5941 MS subtables."""
    from casacore.tables import table

    ant = table(f"{ms}/ANTENNA", ack=False)
    feed = table(f"{ms}/FEED", ack=False)
    pa = table(f"{ms}/PHASED_ARRAY", ack=False)
    obs = table(f"{ms}/OBSERVATION", ack=False)
    names = ant.getcol("NAME")
    pos = ant.getcol("POSITION")
    receptor = np.degrees(feed.getcol("RECEPTOR_ANGLE"))
    axes = pa.getcol("COORDINATE_AXES")
    offsets = pa.getcol("ELEMENT_OFFSET")
    centre = obs.getcol("ARRAY_CENTER")[0]
    stations = []
    for i, name in enumerate(names):
        # python-casacore returns OSKAR's row-major pqr_to_ecef transposed
        pqr_to_ecef = axes[i].T
        pqr = pqr_to_ecef.T @ offsets[i]
        lon, lat, _ = ecef_to_geodetic(pos[i])
        pqr_to_enu = enu_to_ecef_matrix(lon, lat).T @ pqr_to_ecef
        rotation = np.degrees(np.arctan2(pqr_to_enu[1, 0], pqr_to_enu[0, 0]))
        # "s0000 (station315_E8-1)" -> "station315_E8-1"
        label = name.split("(")[-1].rstrip(")") if "(" in name else name
        stations.append(
            {
                "name": label,
                "ecef": pos[i],
                "layout": np.round(pqr[:2].T, 6),
                "feed_x": receptor[i, 0],
                "feed_y": receptor[i, 1],
                "rotation": rotation,
            }
        )
    return stations, centre


def read_mwa(metafits):
    """Read MWA tile positions from a metafits file with mwalib."""
    from mwalib import MetafitsContext

    ctx = MetafitsContext(metafits)
    centre = geodetic_to_ecef(MWA_LON_DEG, MWA_LAT_DEG, MWA_ALT_M)
    rot = enu_to_ecef_matrix(MWA_LON_DEG, MWA_LAT_DEG)
    grid = (np.arange(4) - 1.5) * MWA_DIPOLE_SEP_M
    # dipole order as in the MWA beamformer: rows from north to south
    xx, yy = np.meshgrid(grid, grid[::-1])
    tile_layout = np.stack([xx.ravel(), yy.ravel()], axis=1)
    stations = []
    for ant in ctx.antennas:
        enu = np.array([ant.east_m, ant.north_m, ant.height_m - MWA_ALT_M])
        stations.append(
            {
                "name": f"tile{len(stations):03d}_{ant.tile_name}",
                "ecef": centre + rot @ enu,
                "layout": tile_layout,
                "feed_x": None,
                "feed_y": None,
                "rotation": 0.0,
            }
        )
    return stations


def write_model(path, stations, centre_ecef):
    """Write an OSKAR telescope model directory."""
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)
    lon, lat, h = ecef_to_geodetic(centre_ecef)
    with open(f"{path}/position.txt", "w") as f:
        f.write(f"{lon:.10f} {lat:.10f} {h:.4f}\n")
    np.savetxt(
        f"{path}/layout_ecef.txt", np.array([s["ecef"] for s in stations]), fmt="%.6f"
    )
    # OSKAR reads station directories in sorted order, which must match the
    # order of layout_ecef.txt: AA2 names are "stationNNN_*", MWA "tileNNN_*"
    names = [s["name"] for s in stations]
    assert names == sorted(names), "station directories would be reordered"
    for s in stations:
        sdir = f"{path}/{s['name']}"
        os.makedirs(sdir)
        np.savetxt(f"{sdir}/layout.txt", s["layout"], fmt="%.6f")
        if s["feed_x"] is not None:
            # OSKAR reports the X receptor angle as the X feed angle + 90 deg,
            # so SP-5941's (X, Y) = (Y + 90, Y) came from one feed_angle.txt
            # holding Y; write X and Y separately only if that does not hold.
            if np.isclose((s["feed_x"] - s["feed_y"]) % 360, 90):
                with open(f"{sdir}/feed_angle.txt", "w") as f:
                    f.write(f"{s['feed_y']:.6f}\n")
            else:
                with open(f"{sdir}/feed_angle_x.txt", "w") as f:
                    f.write(f"{s['feed_x'] - 90:.6f}\n")
                with open(f"{sdir}/feed_angle_y.txt", "w") as f:
                    f.write(f"{s['feed_y']:.6f}\n")
    with open(f"{path}/stations.csv", "w") as f:
        f.write("index,name,x_ecef,y_ecef,z_ecef,n_elements,rotation_deg\n")
        # rotation_deg: angle of the station P axis from East towards North
        for i, s in enumerate(stations):
            x, y, z = s["ecef"]
            f.write(
                f"{i},{s['name']},{x:.3f},{y:.3f},{z:.3f},"
                f"{len(s['layout'])},{s['rotation']:.2f}\n"
            )
    print(f"wrote {path}: {len(stations)} stations")


def main():
    """Write the AA2, MWA 256T and combined telescope models."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--sp5941",
        default=SP5941_URL,
        help="SP-5941 zip (URL or local path), or an extracted MS directory",
    )
    parser.add_argument("--metafits", required=True, help="MWA 256T metafits")
    parser.add_argument("--outdir", required=True, help="output directory")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.outdir) as tmp:
        if os.path.isdir(args.sp5941):
            ms = args.sp5941
        else:
            print(f"reading MS subtables from {args.sp5941}")
            ms = fetch_sp5941_subtables(args.sp5941, tmp)
        aa2, aa2_centre = read_aa2(ms)
    mwa = read_mwa(args.metafits)

    write_model(f"{args.outdir}/aa2.tm", aa2, aa2_centre)
    # All three models share the AA2 reference position. OSKAR places the TEC
    # screen relative to it, so the same screen is then the same ionosphere
    # for every configuration, and the AA2 and MWA baselines of case (h) are
    # identical to the AA2-only and MWA-only simulations.
    write_model(f"{args.outdir}/mwa256t.tm", mwa, aa2_centre)
    # case (h): one telescope, AA2 stations first, then the MWA tiles.
    write_model(f"{args.outdir}/aa2_mwa256t.tm", aa2 + mwa, aa2_centre)


if __name__ == "__main__":
    main()
