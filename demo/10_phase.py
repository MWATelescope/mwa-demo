#!/usr/bin/env python

# original WCS and einsum imaging code:
# https://colab.research.google.com/drive/1FT-yR4kDqHdEDkOMfu1p-92ydYZVZEqN
# by Danny C. Price

import re
import sys
import traceback
from os.path import dirname

import numpy as np
from astropy import units as u
from astropy.coordinates import Angle
from astropy.units.core import UnitsError
from numpy import pi
from SSINS import SS

from pyuvdata import UVData


def get_parser():
    sys.path.insert(0, dirname(__file__))
    ssins_tools = __import__("04_ssins")
    # ^ this is bad practice.

    parser = ssins_tools.get_parser_common(diff=False)
    group_phase = parser.add_argument_group("phase")
    group_phase.add_argument(
        "--phase-centre",
        metavar="PC",
        default=None,
        help="zenith or ra=X,dec=Y or alt=X,az=Y",
    )
    group_phase.add_argument(
        "--avg-freq",
        default=None,
        help=(
            "Frequency resolution to average to with units (e.g. 1MHz) "
            "or number of samples"
        ),
    )
    group_phase.add_argument(
        "--avg-time",
        default=None,
        help="Time resolution to average to with units (e.g. 1s)",
    )
    return parser


def get_suffix(args):
    sys.path.insert(0, dirname(__file__))
    ssins_tools = __import__("04_ssins")
    # ^ this is bad practice.
    suffix = ssins_tools.get_suffix(args)
    if args.phase_centre:
        suffix += f".{args.phase_centre}"
    if args.avg_time:
        suffix += f".{args.avg_time}"
    if args.avg_freq:
        suffix += f".{args.avg_freq}"
    return suffix


def _parse_angle_d2r(angle):
    """
    Specify an angle in degrees, or another unit but return it in radians
    """
    try:
        angle = Angle(angle)
    except UnitsError:  # No unit specified
        angle = float(angle) * u.deg
    return angle.to(u.rad).value


def display_pc_catalog(uvd: UVData, pc_id=None):
    if pc_id is None:
        pc_id = uvd.phase_center_id_array[0]
    pc = uvd.phase_center_catalog[pc_id]
    name, type, frame, epoch, lat, lon = (
        pc["cat_name"],
        pc["cat_type"],
        pc["cat_frame"],
        pc["cat_epoch"],
        pc["cat_lat"],
        pc["cat_lon"],
    )
    lat, lon = Angle(lat, u.rad).to(u.deg), Angle(lon, u.rad).to(u.deg)
    print(f"Phase centre {name=}, {type=}, {frame=}, {epoch=}, {lat=}, {lon=}")


def phase_resample(uvd: UVData, args):
    cat_name = args.phase_centre
    uvd.print_phase_center_info()
    display_pc_catalog(uvd)
    if cat_name is None:
        pass
    elif cat_name == "zenith":
        uvd.phase(
            lon=0,
            lat=pi / 2,
            cat_name=cat_name,
            phase_frame="altaz",
            cat_type="driftscan",
        )
    elif m := re.match(r"ra=(.*),dec=(.*)", cat_name):
        ra, dec = m.groups()
        uvd.phase(
            lon=_parse_angle_d2r(ra),
            lat=_parse_angle_d2r(dec),
            cat_name=cat_name,
            phase_frame="fk5",
            cat_type="sidereal",
        )
    elif m := re.match(r"alt=(.*),az=(.*)", cat_name):
        alt, az = m.groups()
        uvd.phase(
            lon=_parse_angle_d2r(az),
            lat=_parse_angle_d2r(alt),
            cat_name=cat_name,
            phase_frame="altaz",
            epoch="j2000",
            cat_type="driftscan",
        )
    uvd.print_phase_center_info()
    display_pc_catalog(uvd)

    if (time := args.avg_time) is not None:
        # figure out what frequency resolution the data is in
        time_res = np.median(uvd.integration_time) * u.s
        try:
            # figure out what frequency resolution we want from freq (str)
            time_res_new = u.Quantity(time)
        except UnitsError:  # No unit specified
            time_res_new = float(time) * u.s
        if np.abs(time_res_new - time_res) < 1e-6 * u.s:
            # nothing to do
            pass
        elif time_res_new < time_res:
            uvd.upsample_in_time(max_int_time=time_res_new.to(u.s).value)
        elif time_res_new > time_res:
            uvd.downsample_in_time(min_int_time=time_res_new.to(u.s).value)
    if (freq := args.avg_freq) is not None:
        # figure out what frequency resolution the data is in
        freq_res = np.median(uvd.channel_width) * u.Hz
        # figure out how many channels we need to average together
        try:
            # figure out what frequency resolution we want from freq (str)
            freq_res_new = u.Quantity(freq)
            if freq_res_new < freq_res:
                raise ValueError(f"Cannot upsample data, {freq_res_new=} < {freq_res=}")
            n_chan = int(freq_res_new / freq_res)
        except UnitsError:  # No unit specified
            n_chan = int(freq)
        uvd.frequency_average(n_chan)


def main():
    sys.path.insert(0, dirname(__file__))
    ssins_tools = __import__("04_ssins")
    # ^ this is bad practice.

    parser = get_parser()
    args = parser.parse_args()
    print(f"{args=}")
    if args.diff:
        print("diff not supported")
        exit(1)

    suffix = get_suffix(args)

    # sky-subtract https://ssins.readthedocs.io/en/latest/sky_subtract.html
    ss = SS()

    try:
        base = ssins_tools.read_select(ss, args)
    except ValueError as exc:
        traceback.print_exception(exc)
        parser.print_usage()
        exit(1)

    phase_resample(ss, args)

    out_path = f"{base}{suffix}.uvfits"
    print(f"Writing to {out_path}")
    ss.write_uvfits(out_path)

    # for n in range(2, ss.Nants_data):
    #     plt.clf()
    #     waterfall_data = ss.get_data((1, n, ss.polarization_array[0]))
    #     fig, ax = plt.subplots(1, 1)
    #     ax.imshow(np.abs(waterfall_data), interpolation="none", origin="lower")
    #     fig.savefig(f"{base}{suffix}_amps_{n}.png")


if __name__ == "__main__":
    main()

# how to test
"""
cat <<EOF > single_source.yaml
single:
- ra: 349.57645833
  dec: -31.22952778
  comp_type: point
  flux_type:
    power_law:
      si: 0.0
      fd:
        freq: 170000000.0
        i: 1.0
EOF
hyperdrive vis-simulate \
    --metafits ./demo/data/1088806248/raw/1088806248.metafits \
    --output-model-files 1088806248_sim.uvfits \
    --source-list single_source.yaml \
    --no-beam \
    --num-timesteps 2 \
    --num-fine-channels 2 \
    --freq-res 40

cat <<EOF > dump_data.py
uvd = __import__('pyuvdata').UVData()
uvd.read(__import__('sys').argv[-1])
print(uvd.data_array)
EOF
python dump_data.py 1088806248_sim.uvfits

[[[ 0.25002787+0.96823865j  0.25002787+0.96823865j
    0.        +0.j          0.        +0.j        ]
  [ 0.25641403+0.96656704j  0.25641403+0.96656704j
    0.        +0.j          0.        +0.j        ]]

python demo/10_phase.py 1088806248_sim.uvfits \
    --phase-centre ra=23h18m18.35s,dec=-31d13m46.3s --avg-freq 40kHz --avg-time 16s

python dump_data.py 1088806248_sim.ra=23h18m18.35s,dec=-31d13m46.3s.16s.40kHz.uvfits

[[[0.99999344+0.00363045j 0.99999344+0.00363045j 0.        +0.j
   0.        +0.j        ]
  [0.9999934 +0.00363123j 0.9999934 +0.00363123j 0.        +0.j
   0.        +0.j        ]]
"""
