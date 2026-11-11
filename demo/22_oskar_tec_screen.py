#!/usr/bin/env python
"""
Write a mild, frozen-flow ionospheric TEC screen for OSKAR.

The screen is a single Kolmogorov layer: a Gaussian random field with power
spectrum P(k) ~ (k^2 + k0^2)^(-11/6), k0 = 2 pi / outer_scale, scaled so that
the standard deviation of delta-TEC over the whole generated screen is
``--rms-tecu`` (0.01 TECU by default, "mild"). The layer moves rigidly
("frozen flow") at ``--speed-kmh`` towards ``--direction-deg`` (east of north),
and OSKAR samples it every ``--interval-s`` seconds.

OSKAR reads the cube (axes XX, YY, TIME) as delta-TEC in TECU and applies the
phase -8.44797245e9 * dTEC / freq_Hz per station and source at the pierce
point of a screen at ``telescope/external_tec_screen/screen_height_km``
(300 km here); see OSKAR's docs/theory/tec_screens.rst.

usage: 22_oskar_tec_screen.py --duration-s 120 --out screen.fits
"""

import argparse

import numpy as np
from astropy.io import fits

PHASE_PER_TECU_HZ = 8.44797245e9


def kolmogorov(n, pixel_m, outer_scale_m, rng):
    """Return an n x n Kolmogorov phase screen with unit variance."""
    k = 2 * np.pi * np.fft.fftfreq(n, d=pixel_m)
    kx, ky = np.meshgrid(k, k)
    k0 = 2 * np.pi / outer_scale_m
    psd = (kx**2 + ky**2 + k0**2) ** (-11.0 / 6.0)
    psd[0, 0] = 0.0
    noise = rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n))
    screen = np.fft.ifft2(noise * np.sqrt(psd)).real
    screen -= screen.mean()
    return screen / screen.std()


def main():
    """Generate and write the TEC screen cube."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--duration-s", type=float, required=True)
    parser.add_argument(
        "--interval-s",
        type=float,
        default=8.0,
        help="time between screens (OSKAR picks the nearest)",
    )
    parser.add_argument("--rms-tecu", type=float, default=0.01)
    parser.add_argument("--outer-scale-km", type=float, default=100.0)
    parser.add_argument("--speed-kmh", type=float, default=100.0)
    parser.add_argument("--direction-deg", type=float, default=60.0)
    parser.add_argument(
        "--width-km",
        type=float,
        default=200.0,
        help="width of each screen (covers 65 km AA2 + 8.5 deg field at 300 km)",
    )
    parser.add_argument("--pixel-m", type=float, default=250.0)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    num_times = int(np.ceil(args.duration_s / args.interval_s)) + 1
    width = int(round(args.width_km * 1e3 / args.pixel_m))
    speed = args.speed_kmh / 3.6
    drift_m = speed * args.interval_s * (num_times - 1)
    big = int(2 ** np.ceil(np.log2(width + drift_m / args.pixel_m + 2)))
    rng = np.random.default_rng(args.seed)
    base = kolmogorov(big, args.pixel_m, args.outer_scale_km * 1e3, rng)
    base *= args.rms_tecu

    theta = np.radians(args.direction_deg)
    vx, vy = speed * np.sin(theta), speed * np.cos(theta)
    # start in the corner the flow moves away from
    x0 = 0 if vx >= 0 else big - width - 1
    y0 = 0 if vy >= 0 else big - width - 1
    cube = np.zeros((1, num_times, width, width), dtype=np.float32)
    for t in range(num_times):
        dx = int(round(vx * t * args.interval_s / args.pixel_m))
        dy = int(round(vy * t * args.interval_s / args.pixel_m))
        cube[0, t] = base[y0 + dy : y0 + dy + width, x0 + dx : x0 + dx + width]

    hdr = fits.Header()
    for i, (ctype, cdelt, crpix) in enumerate(
        [
            ("XX", args.pixel_m, width // 2 + 1),
            ("YY", args.pixel_m, width // 2 + 1),
            ("TIME", args.interval_s, 1),
            ("FREQ", 1.0, 1),
        ],
        start=1,
    ):
        hdr[f"CTYPE{i}"] = ctype
        hdr[f"CDELT{i}"] = cdelt
        hdr[f"CRPIX{i}"] = crpix
        hdr[f"CRVAL{i}"] = 1.5e8 if ctype == "FREQ" else 0.0
    hdr["BUNIT"] = "TECU"
    hdr["COMMENT"] = (
        f"Kolmogorov dTEC, rms {args.rms_tecu} TECU, L0 {args.outer_scale_km} km,"
        f" {args.speed_kmh} km/h towards {args.direction_deg} deg, seed {args.seed}"
    )
    fits.writeto(args.out, cube, hdr, overwrite=True)

    # structure of the first screen, for the docs
    s0 = cube[0, 0].astype(float)
    print(
        f"wrote {args.out}: {num_times} x {width} x {width} px, "
        f"{args.pixel_m} m/px, every {args.interval_s} s"
    )
    print(f"dTEC rms {s0.std():.4f} TECU, peak-to-peak {np.ptp(s0):.4f} TECU")
    for sep_km in [1, 10, 65]:
        lag = max(1, int(round(sep_km * 1e3 / args.pixel_m)))
        if lag >= width:
            continue
        d = s0[:, lag:] - s0[:, :-lag]
        phase = PHASE_PER_TECU_HZ * d.std() / 150e6
        print(
            f"  differential dTEC rms over {sep_km:3d} km: {d.std():.5f} TECU"
            f" = {np.degrees(phase):.1f} deg at 150 MHz"
        )


if __name__ == "__main__":
    main()
