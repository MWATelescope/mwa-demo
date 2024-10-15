#!/usr/bin/env python

# original WCS and einsum imaging code:
# https://colab.research.google.com/drive/1FT-yR4kDqHdEDkOMfu1p-92ydYZVZEqN
# by Danny C. Price

import numpy as np
from numpy import pi

import sys
from SSINS import SS
from os.path import dirname
from pyuvdata import UVData
from astropy.coordinates import EarthLocation
from astropy.time import Time
from astropy.wcs import WCS
from astropy.io import fits
import traceback
import matplotlib as mpl
import itertools
from matplotlib import pyplot as plt


def select_vis_matrix(uvd: UVData, **select_kwargs) -> np.ndarray:
    """
    Extract 1D visibility array (upper triangular) for first time, channel, pol
    selected and convert to correlation matrix.

    If select_kwargs doesn't select a single time, channel, pol then the first
    is picked.

    Args:
        uvd: Input UVData object
        select_kwargs: args for UVData.select.

    Returns:
        V (np.ndarray): (N_ant x N_ant x 4 pol) correlation matrix
    """
    sel = uvd.select(**select_kwargs, inplace=False)
    # if selection has multiple times or channels, select the first
    times = [Time(sel.time_array[0], format="jd").jd]
    freqs = [sel.freq_array[0]]
    pols = [sel.get_pols()[0]]
    if sel.Ntimes > 0 or sel.Nfreqs > 0 or sel.Npols > 0:
        sel.select(times=times, frequencies=freqs, polarizations=pols)
    d = sel.data_array.reshape((sel.Ntimes, sel.Nbls, sel.Nfreqs, sel.Npols))[
        0, :, 0, 0
    ]

    ix, iy = np.triu_indices(sel.Nants_data, 1)

    # Create empty NxN matrix
    V = np.zeros((sel.Nants_data, sel.Nants_data), dtype="complex64")

    # Fill in the upper triangle
    V[ix, iy] = np.conj(d).squeeze()
    # Fill in the lower triangle
    V[iy, ix] = d.squeeze()

    return V


def create_lmn_grid(n_pix):
    # Create an empty NxN grid for each (l,m,n)
    lmn = np.zeros((n_pix, n_pix, 3), dtype="float32")

    # Create regularly-spaced grid
    l = np.linspace(-1, 1, n_pix, dtype="float32")  # noqa: E741
    m = np.linspace(-1, 1, n_pix, dtype="float32")
    lg, mg = np.meshgrid(l, m)
    ng = np.sqrt(1 - lg**2 - mg**2)

    # Fill in lmn array
    lmn[..., 0] = lg
    lmn[..., 1] = mg
    lmn[..., 2] = ng

    return lmn.astype("float32")


def check_diff_uniformity(series, epsilon=0.001):
    if len(series) > 1:
        diff = series[1] - series[0]
        for a, b in itertools.pairwise(series):
            if np.abs((b - a) - diff) > epsilon:
                return False
    return True


def main():

    sys.path.insert(0, dirname(__file__))
    ssins_tools = __import__("04_ssins")
    parser = ssins_tools.get_parser()
    parser.add_argument("--pix", default=201, type=int, help="number of image pixels")
    parser.add_argument(
        "--thumbs",
        default=False,
        action="store_true",
        help="write thumbnails for each slice",
    )
    parser.add_argument(
        "--combine-freq",
        default=False,
        action="store_true",
        help="combine frequencies to a single channel",
    )
    parser.add_argument(
        "--combine-time",
        default=False,
        action="store_true",
        help="combine times together",
    )

    args = parser.parse_args()
    print(f"{args=}")
    n_pix = args.pix

    suffix = ssins_tools.get_suffix(args)

    # sky-subtract https://ssins.readthedocs.io/en/latest/sky_subtract.html
    ss = SS()

    try:
        base = ssins_tools.read_select(ss, args)
    except ValueError as exc:
        traceback.print_exception(exc)
        parser.print_usage()
        exit(1)

    # phase to zenith
    ss.phase(
        lon=0, lat=pi / 2, cat_name="zenith", phase_frame="altaz", cat_type="driftscan"
    )

    plt.style.use("dark_background")

    tel = ss.telescope
    ant_pos_enu = ss.get_ENU_antpos(pick_data_ants=True)[0]

    assert type(tel.location) is EarthLocation  # we're not on the moon yet
    eloc: EarthLocation = tel.location

    ss.print_phase_center_info()

    # Load time coord data
    times = Time(np.unique(ss.time_array), format="jd", scale="utc", location=eloc)
    t_delta = ss.integration_time[0]
    if args.diff:
        t_delta /= 2.0
    t_scale = times.scale.upper()
    # t_midpoint = times[ss.Ntimes // 2]
    jd_midnight = np.floor(ss.time_array[0] - 0.5) + 0.5
    t_ref = times[0]
    # t_ref_rdate_str = t_ref.strftime(r"%Y-%m-%d")
    # t_ref_zerohrs = Time(t_ref_rdate_str, format="iso", scale="utc")
    t_ref_iso_str = t_ref.strftime(r"%Y-%m-%dT%H:%M:%S")

    if not check_diff_uniformity(times.to_value("gps")):
        raise UserWarning("uniform spacing assumed in time axis")

    time_digits = int(np.ceil(np.log10(ss.Ntimes)))
    f_delta = ss.channel_width[0]
    if not check_diff_uniformity(ss.freq_array):
        raise UserWarning("uniform spacing assumed in freq axis")

    if ss.Npols > 1:
        pol_indexing = np.argsort(np.abs(ss.polarization_array))
        polarization_array = ss.polarization_array[pol_indexing]
        pol_spacing = polarization_array[1] - polarization_array[0]
        if not check_diff_uniformity(polarization_array):
            raise UserWarning("uniform spacing assumed in pol axis")
    else:
        pol_indexing = np.asarray([0])
        polarization_array = ss.polarization_array
        pol_spacing = 1

    lat, lon, height = tel.location_lat_lon_alt_degrees

    header = {
        "SIMPLE": "T",
        "NAXIS1": n_pix,
        "NAXIS2": n_pix,
        "CTYPE1": "ALON-SIN",
        "CTYPE2": "ALAT-SIN",
        "CRPIX1": n_pix // 2 + 1,
        "CRPIX2": n_pix // 2 + 1,
        "CRVAL1": 0.0,
        "CRVAL2": 90.0,
        "CDELT1": -360 / np.pi / n_pix,
        "CDELT2": 360 / np.pi / n_pix,
        "CUNIT1": "deg",
        "CUNIT2": "deg",
        "JDREF": jd_midnight,
        "DATE-OBS": t_ref_iso_str,
        "OBSGEO-X": eloc.geocentric[0].value,
        "OBSGEO-Y": eloc.geocentric[1].value,
        "OBSGEO-Z": eloc.geocentric[2].value,
        "TELESCOP": tel.name,
        "LAT     ": lat,
        "LON     ": lon,
        "ALT     ": height,
        "INSTRUME": tel.instrument,
        "SPECSYS": "TOPOCENT",
    }

    naxis = 2  # running count of axes
    extra_axes = [
        {
            "NAXIS": ss.Ntimes,
            "CTYPE": t_scale,
            "CRPIX": 1.0,
            "CRVAL": (times[0].jd - jd_midnight) / 86400,
            "CDELT": t_delta,
            "CUNIT": "s",
        },
        {
            "NAXIS": ss.Nfreqs,
            "CTYPE": "FREQ",
            "CRPIX": ss.Nfreqs // 2 + 1,
            "CRVAL": ss.freq_array[ss.Nfreqs // 2],
            "CDELT": f_delta,
            "CUNIT": "Hz",
        },
        {
            "NAXIS": ss.Npols,
            "CTYPE": "STOKES",
            "CRPIX": 1.0,
            "CRVAL": polarization_array[0],
            "CDELT": pol_spacing,
        },
    ]
    degenerate_axes = set()
    for ax in extra_axes:
        if ax["NAXIS"] == 1 and ax["CTYPE"] != "FREQ":
            print("degenerate axis " + ax["CTYPE"] + " dropped")
            degenerate_axes.add(ax["CTYPE"])
            continue
        naxis += 1
        header.update({f"{k}{naxis}": v for k, v in ax.items()})

    # You'll have to read FITS documentation to understand this,
    # The keywords are a little opaque
    # https://ui.adsabs.harvard.edu/abs/2002A%26A...395.1061G/abstract
    wcs = WCS(header)

    wcs.printwcs()
    print(f"{wcs.world_axis_physical_types=}")

    data = np.zeros(wcs.array_shape, dtype=np.complex64)
    print(f"{data.shape=}")

    cmap = mpl.colormaps.get_cmap(args.cmap)
    cmap.set_bad(color="#00000000")

    xy_slice = [slice(None)] * 2

    # Create lmn grid
    lmn = create_lmn_grid(n_pix)

    # Generate our weight vector
    # i,j: pixel indexes, a: antenna index, d: lmn/xyz index
    phs = np.einsum("ijd,ad", lmn, ant_pos_enu, optimize=True)

    for t_idx, t in enumerate(times):
        # Attach earth location and compute local sidereal time

        t_slice, t_suffix = [], ""
        if t_scale not in degenerate_axes:
            t_slice, t_suffix = [t_idx], f"-t{t_idx:0{time_digits}}"

        print(f"{t.iso} mjd={t.mjd:.6f} unix={t.unix:.3f}")

        for f_idx, f in enumerate(ss.freq_array):
            λ = 2.99e8 / f

            f_slice, f_suffix = [], ""
            if "FREQ" not in degenerate_axes:
                f_slice, f_suffix = [f_idx], f"-ch{f_idx}"

            w_vec = np.exp(1j * 2 * np.pi * phs / λ)
            for p_idx, pol in enumerate(ss.get_pols()):

                p_slice, p_suffix = [], ""
                if "STOKES" not in degenerate_axes:
                    p_slice, p_suffix = [p_idx], f"-{pol}"

                V_mat = select_vis_matrix(
                    ss, times=[t.jd], frequencies=[f], polarizations=[pol]
                )

                # Compute w_p V_pq w*_q contraction for each pixel (i, j)
                # p,q: antenna indexes, i,j: pixel indexes
                img = np.einsum(
                    "pij,pq,qij->ij", w_vec, V_mat, np.conj(w_vec), optimize=True
                )

                data_slice = (*(p_slice + f_slice + t_slice + xy_slice),)
                data[data_slice] = img[::-1]

                if args.thumbs:
                    plt.clf()
                    plt.suptitle(f"{base}.img1{t_suffix}{f_suffix}{p_suffix}")

                    plt.subplot(
                        projection=wcs,
                        frame_on=False,
                        slices=["x", "y"] + t_slice + f_slice + p_slice,
                    )

                    # Note a convention flip is done with the ::-1 indexing
                    plt.imshow(np.abs(img[::-1]))
                    plt.grid(color="white", ls="dotted")

                    plt.savefig(p := f"{base}.img1{t_suffix}{f_suffix}{p_suffix}.png")
                    print(p)

    axes_to_average = []
    for idx, phys in enumerate(reversed(wcs.world_axis_physical_types)):
        if args.combine_freq and phys == "em.freq":
            axes_to_average.append(idx)
            continue
        if args.combine_time and phys == "time":
            axes_to_average.append(idx)
            continue
    if len(axes_to_average):
        data = np.mean(data, axis=(*axes_to_average,))

    # With WCS we can write the image to FITS
    hdu = fits.PrimaryHDU(header=wcs.to_header(), data=np.abs(data))
    hdu.writeto(p := f"{base}{suffix}.img1.fits", overwrite=True)
    print(p)


if __name__ == "__main__":
    main()

# ffmpeg -r 10 -pattern_type glob -i 'demo/data/*/cal/hyp_cal_*.img1-t*.png' -vcodec libx264 -vf "scale='min(3840,iw)':'min(2160,ih)':force_original_aspect_ratio=decrease,pad=ceil(iw/2)*2:ceil(ih/2)*2" -pix_fmt yuv420p  img1.mp4  # noqa: E501
