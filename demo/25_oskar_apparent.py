#!/usr/bin/env python
"""
Write an apparent-flux sky model for a simulation, using OSKAR's own beam.

hyperdrive's beam models are MWA-only (FEE / analytic), and the OSKAR MWA tile
in this workshop is a 4x4 grid of OSKAR dipoles, not the MWA FEE beam, so we
peel with ``--no-beam`` against a model whose fluxes already include the
station beam that OSKAR used. ``oskar_sim_beam_pattern`` evaluates the
station-averaged Stokes I beam (normalised at the phase centre, as
in the simulation) at every sky-model source, at a few times across the
observation and at the band edges and centre. We use the station auto-power
(Stokes I of J_i J_i^H) averaged over stations rather than the cross-power,
because the cross-power of two rotated AA2 stations also carries their feed
rotation, which 27_oskar_derotate.py removes before peeling. The apparent flux
is the time-averaged beam times the true flux at the centre frequency; the
apparent spectral index adds the beam's slope between the band edges.

Everything (telescope, sky, phase centre, time, flux cut) is read from the
``.ini`` written by 23_oskar_sim.sh. Runs in the OSKAR container.

A second file (``--out-true``) lists the same sources, in the same order and
with the same names, at their true flux; rapthor takes the pair as its
``input_skymodel`` and ``apparent_skymodel``. ``--num-sources`` keeps only the
apparently brightest N sources in both.

usage: 25_oskar_apparent.py --sim-ini vis/aa2_120s.ini --out aa2_120s_app.skymodel
"""

import argparse
import configparser
import glob
import os
import subprocess
import tempfile
from datetime import datetime, timedelta

import numpy as np

FORMAT = (
    "FORMAT = Name, Type, Patch, Ra, Dec, I, MajorAxis, MinorAxis, Orientation, "
    "ReferenceFrequency, SpectralIndex='[]'"
)


def fmt_ra(deg):
    """Format RA as hh:mm:ss.ssss."""
    s = (deg % 360) / 15 * 3600
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:07.4f}"


def fmt_dec(deg):
    """Format Dec as sdd.mm.ss.ssss."""
    sign = "-" if deg < 0 else "+"
    s = abs(deg) * 3600
    d, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{sign}{int(d):02d}.{int(m):02d}.{s:07.4f}"


def main():
    """Evaluate the beam at each source and write the apparent sky model."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--sim-ini", required=True)
    parser.add_argument("--telescope", help="override the simulated telescope")
    parser.add_argument("--num-times", type=int, default=5)
    parser.add_argument("--max-stations", type=int, default=68)
    parser.add_argument("--out", required=True, help="apparent sky model")
    parser.add_argument("--out-true", help="true-flux sky model, same sources")
    parser.add_argument("--num-sources", type=int, help="keep the brightest N")
    args = parser.parse_args()

    ini = configparser.ConfigParser()
    ini.read(args.sim_ini)
    obs, tel, sky = ini["observation"], ini["telescope"], ini["sky"]
    telescope = args.telescope or tel["input_directory"]
    f0 = float(obs["start_frequency_hz"])
    nchan = int(obs["num_channels"])
    df = float(obs["frequency_inc_hz"])
    f_edges = [f0, f0 + df * (nchan - 1) / 2, f0 + df * (nchan - 1)]
    length = float(obs["length"])

    with open(f"{telescope}/layout_ecef.txt") as f:
        num_stations = sum(1 for line in f if line.strip())
    station_ids = np.unique(
        np.linspace(0, num_stations - 1, min(num_stations, args.max_stations)).astype(
            int
        )
    )

    data = np.loadtxt(sky["oskar_sky_model/file"], ndmin=2)
    flux_min = sky.get("oskar_sky_model/filter/flux_min", "min")
    if flux_min not in ("min", ""):
        data = data[data[:, 2] >= float(flux_min)]
    ra, dec, flux = data[:, 0], data[:, 1], data[:, 2]
    f_ref, si = data[:, 6], data[:, 7]
    maj, mnr, pa = data[:, 9], data[:, 10], data[:, 11]

    # sample the beam at the middle of num_times equal slices of the observation
    start = datetime.strptime(obs["start_time_utc"][:19], "%Y-%m-%d %H:%M:%S")
    step = length / args.num_times
    bp_start = start + timedelta(seconds=step / 2)

    with tempfile.TemporaryDirectory(dir=os.path.dirname(args.out) or ".") as tmp:
        osm = f"{tmp}/sky.osm"
        np.savetxt(osm, data[:, :12], fmt="%.8f")
        bp_ini = f"{tmp}/bp.ini"
        open(bp_ini, "w").close()
        settings = {
            "simulator/use_gpus": "false",
            "observation/phase_centre_ra_deg": obs["phase_centre_ra_deg"],
            "observation/phase_centre_dec_deg": obs["phase_centre_dec_deg"],
            "observation/start_frequency_hz": f"{f_edges[0]}",
            "observation/frequency_inc_hz": f"{f_edges[1] - f_edges[0]}",
            "observation/num_channels": "3",
            "observation/start_time_utc": bp_start.strftime("%Y-%m-%d %H:%M:%S"),
            "observation/length": f"{step * (args.num_times - 1) or 1}",
            "observation/num_time_steps": f"{args.num_times}",
            "telescope/input_directory": telescope,
            "telescope/normalise_beams_at_phase_centre": "true",
            "beam_pattern/coordinate_type": "Sky model",
            "beam_pattern/sky_model/file": osm,
            # up to --max-stations evenly spaced stations (OSKAR opens 4 files
            # per station, which runs into the open-file limit for 256 tiles)
            "beam_pattern/all_stations": "false",
            "beam_pattern/station_ids": ",".join(map(str, station_ids)),
            "beam_pattern/root_path": f"{tmp}/bp",
            "beam_pattern/station_outputs/text_file/auto_power": "true",
        }
        for key, value in settings.items():
            subprocess.run(
                ["oskar_sim_beam_pattern", "-q", "--set", bp_ini, key, value],
                check=True,
            )
        # (-q makes oskar_sim_beam_pattern exit non-zero, so discard the log)
        subprocess.run(
            ["oskar_sim_beam_pattern", bp_ini], check=True, stdout=subprocess.DEVNULL
        )
        files = sorted(
            glob.glob(f"{tmp}/bp_S*_TIME_SEP_CHAN_SEP_AUTO_POWER_AMP_I_I.txt")
        )
        # each file is [time][channel][source]; average stations and times
        beam = np.mean([np.loadtxt(f) for f in files], axis=0)
    beam = beam.reshape(args.num_times, 3, len(ra)).mean(axis=0)
    beam = np.clip(beam, 1e-12, None)

    f_mid = f_edges[1]
    true_mid = flux * (f_mid / f_ref) ** si
    app = true_mid * beam[1]
    app_si = si + np.log(beam[2] / beam[0]) / np.log(f_edges[2] / f_edges[0])
    order = np.argsort(app)[::-1][: args.num_sources]
    outputs = [(args.out, app, app_si)]
    if args.out_true:
        outputs.append((args.out_true, true_mid, si))
    for path, flux_mid, spec in outputs:
        with open(path, "w") as f:
            f.write(FORMAT + "\n\n")
            for n, i in enumerate(order):
                kind = "POINT" if maj[i] == 0 else "GAUSSIAN"
                f.write(
                    f"app{n}, {kind}, , {fmt_ra(ra[i])}, {fmt_dec(dec[i])}, "
                    f"{flux_mid[i]:.8f}, {maj[i]:.6f}, {mnr[i]:.6f}, {pa[i]:.6f}, "
                    f"{f_mid:.1f}, [{spec[i]:.6f}]\n"
                )
    print(
        f"wrote {args.out}: {len(order)} of {len(ra)} sources, true "
        f"{true_mid[order].sum():.1f} Jy, apparent {app[order].sum():.1f} Jy "
        f"(all sources: {app.sum():.1f} Jy) at {f_mid / 1e6:.3f} MHz; "
        f"beam at brightest apparent source {beam[1][order[0]]:.3f}"
    )


if __name__ == "__main__":
    main()
