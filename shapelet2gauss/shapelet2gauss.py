#!/usr/bin/env python
"""Replace shapelet components in a hyperdrive YAML source list with Gaussian sets.

DP3 can only predict point and Gaussian components, so shapelets (e.g. the EoR1
models in srclist_pumav3_EoR0LoBES_EoR1pietro_CenA-GP_2023-11-07.yaml) must be
converted. Each shapelet is fitted in the uv plane with a sign-constrained
matching pursuit over a small dictionary of Gaussian shapes:

* The shapelet and Gaussian visibility envelopes are implemented exactly as in
  mwa_hyperdrive `src/model/cpu.rs` (model_shapelets / model_gaussians) and were
  validated to 1e-5 against `hyperdrive vis-simulate` output.
* Atoms are picked from correlation maps on an FFT grid; their amplitudes are
  re-solved with bounded linear least squares on uv samples drawn from a real
  MWA baseline distribution (default: obs 1443210064, Phase II compact) plus a
  uniform fill out to --uvmax. The zero spacing carries 5% of the weight.
* Sign constraints make cancelling +/- pairs impossible. A free nonlinear fit
  produced +/-7000 Jy pairs for a 2 Jy source, which fell apart under the
  phase-centre uv projection hyperdrive/DP3 use for Gaussians.
* Shapelet models ring strongly beyond ~1500 wavelengths (negative lobes larger
  than the peak); that structure is only reproduced approximately.

Usage:
    shapelet2gauss.py in.yaml out.yaml [--nproc 20] [--uvmax 2000] [--tol 0.003] [--kmax 120]
                      [--only SRC ...] [--report out.report]
Everything that is not a shapelet component is copied through byte-for-byte.
Environment: MWA_BASELINES=<.npy of baseline lengths in metres> to weight for another array.
"""
import os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
import re
import sys
import copy
import time
import argparse
from multiprocessing import Pool

import numpy as np
import yaml
from scipy.special import eval_hermite, factorial
from scipy.optimize import lsq_linear

HERE = os.path.dirname(os.path.abspath(__file__))
K_SHAPELET = np.pi / np.sqrt(2 * np.log(2))     # hyperdrive SQRT_FRAC_PI_SQ_2_LN_2
GEXP = -(np.pi / 2) ** 2 / np.log(2)             # hyperdrive GAUSSIAN_EXP_CONST
AS = np.pi / 180 / 3600
FWHM2SIG = 1 / (2 * np.sqrt(2 * np.log(2)))
C = 299792458.0


# ----------------------------------------------------------------------------- forward models
def basis(n, x):
    return eval_hermite(n, x) * np.exp(-0.5 * x * x) / np.sqrt(2.0 ** n * factorial(n))


def shapelet_env(u, v, maj, mn, pa, coeffs):
    """hyperdrive shapelet envelope. u,v in wavelengths (component-centred), maj/min/pa in radians."""
    s, c = np.sin(pa), np.cos(pa)
    x = u * s + v * c
    y = u * c - v * s
    X = x * maj * K_SHAPELET
    Y = -y * mn * K_SHAPELET
    ns = sorted({n1 for n1, _, _ in coeffs} | {n2 for _, n2, _ in coeffs})
    BX = {n: basis(n, X) for n in ns}
    BY = {n: basis(n, Y) for n in ns}
    env = np.zeros(np.shape(u), complex)
    for n1, n2, val in coeffs:
        env += (1j) ** ((n1 + n2) % 4) * val * BX[n1] * BY[n2]
    return env


def gauss_env(u, v, maj, mn, pa):
    """hyperdrive Gaussian envelope (FWHM maj/min in radians, pa radians)."""
    s, c = np.sin(pa), np.cos(pa)
    kx = u * s + v * c
    ky = u * c - v * s
    return np.exp(GEXP * (maj * maj * kx * kx + mn * mn * ky * ky))


def gauss_vis(u, v, p):
    """Sum of Gaussians. p rows: dl, dm, flux, maj, min, pa. V = sum F G exp(+2 pi i (u dl + v dm))."""
    shp = np.shape(u)
    u = np.asarray(u).ravel()[:, None]
    v = np.asarray(v).ravel()[:, None]
    out = np.zeros(u.shape[0], complex)
    for a in range(0, len(p), 32):
        q = p[a:a + 32]
        out += (q[:, 2] * gauss_env(u, v, q[:, 3], q[:, 4], q[:, 5])
                * np.exp(2j * np.pi * (u * q[:, 0] + v * q[:, 1]))).sum(-1)
    return out.reshape(shp)


def lm_to_radec(dl, dm, ra0, dec0):
    """Inverse of marlu RADec::to_lmn (l east, m north)."""
    n = np.sqrt(1 - dl * dl - dm * dm)
    dec = np.arcsin(dm * np.cos(dec0) + n * np.sin(dec0))
    ra = ra0 + np.arctan2(dl, n * np.cos(dec0) - dm * np.sin(dec0))
    return ra, dec


def selftest():
    """Image/uv sign conventions: a point at (+dl,+dm) must land at +l (axis 1), +m (axis 0)."""
    dl0, dm0 = 30 * AS, -50 * AS
    pix, N = 5 * AS, 128
    du = 1.0 / (N * pix)
    k = (np.arange(N) - N // 2) * du
    U, V = np.meshgrid(k, k, indexing="xy")
    img = (np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(np.exp(2j * np.pi * (U * dl0 + V * dm0))))) * du * du).real
    j, i = np.unravel_index(np.argmax(img), img.shape)
    lax = (np.arange(N) - N // 2) * pix
    assert abs(lax[i] - dl0) < pix and abs(lax[j] - dm0) < pix


# ----------------------------------------------------------------------------- weights
def load_baselines():
    return np.load(os.environ.get("MWA_BASELINES", os.path.join(HERE, "mwa_baselines_1443210064_m.npy")))


def uv_weight(R, uvmax, bl):
    """Radial weight ~ MWA baseline density (170-230 MHz) with a 5% floor, zero beyond uvmax."""
    rng = np.random.default_rng(0)
    f = rng.uniform(170e6, 230e6, 200000)
    r = rng.choice(bl, 200000) * f / C
    edges = np.arange(0, uvmax + 50, 25.0)
    h, _ = np.histogram(r, edges)
    dens = h / (np.pi * (edges[1:] ** 2 - edges[:-1] ** 2))
    dens = np.convolve(dens, np.ones(3) / 3, mode="same")
    dens = dens / dens.max()
    w = np.interp(R, 0.5 * (edges[1:] + edges[:-1]), dens, left=1.0, right=0.0)
    return np.where(R < uvmax, np.maximum(w, 0.05), 0.0)


# ----------------------------------------------------------------------------- fit
def fit_component(maj_as, min_as, pa_deg, coeffs, uvmax=2000.0, tol=0.003, kmax=120,
                  solve_every=5, nuv=6000, seed=1, verbose=False):
    bl = load_baselines()
    maj, mn, pa = maj_as * AS, min_as * AS, np.deg2rad(pa_deg)
    nmax = max(max(n1, n2) for n1, n2, _ in coeffs)
    sig_min = min(maj, mn) * FWHM2SIG
    sig_max = max(maj, mn) * FWHM2SIG
    # image/uv grid, used only to pick atoms
    pixel = min(sig_min / 4, 1.0 / (2 * uvmax) / 1.5)
    fov = 2 * sig_max * (np.sqrt(2 * nmax + 1) * 1.3 + 3)
    N = max(int(2 ** np.ceil(np.log2(fov / pixel))), 64)
    du = 1.0 / (N * pixel)
    k = (np.arange(N) - N // 2) * du
    U, V = np.meshgrid(k, k, indexing="xy")
    E = shapelet_env(U, V, maj, mn, pa, coeffs)
    w = uv_weight(np.hypot(U, V), uvmax, bl)
    lax = (np.arange(N) - N // 2) * pixel
    # uv samples for the amplitude solve
    rng = np.random.default_rng(seed)
    n1 = int(0.7 * nuv)
    f = rng.uniform(170e6, 230e6, n1)
    r = np.concatenate([rng.choice(bl, n1) * f / C, rng.uniform(0, uvmax, nuv - n1)])
    th = rng.uniform(0, 2 * np.pi, nuv)
    us, vs = r * np.cos(th), r * np.sin(th)
    us[0] = vs[0] = 0.0
    wts = np.ones(nuv)
    wts[0] = np.sqrt(0.05 * nuv)
    E_s = shapelet_env(us, vs, maj, mn, pa, coeffs)
    norm = np.abs(E_s).max()
    b = np.concatenate([wts * E_s.real, wts * E_s.imag])
    # dictionary
    base = max(2.355 * sig_min / np.sqrt(nmax + 1), 2.5 * pixel)
    shapes = [(base * f_, base * f_, 0.0) for f_ in (1.0, 1.5, 2.2, 3.3)]
    shapes += [(maj * f_, mn * f_, pa) for f_ in (0.35, 0.5, 0.7, 1.0)]
    Gs = [gauss_env(U, V, *s) for s in shapes]
    Gnorm = [np.sum(w * G * G) for G in Gs]
    Gs_s = [gauss_env(us, vs, *s) for s in shapes]

    atoms, amps = [], np.zeros(0)

    def solve():
        A = np.array([Gs_s[si] * np.exp(2j * np.pi * (us * l + vs * m)) for (l, m, si, sg) in atoms]).T
        A = np.concatenate([wts[:, None] * A.real, wts[:, None] * A.imag])
        lo = np.array([0.0 if sg > 0 else -np.inf for (_, _, _, sg) in atoms])
        hi = np.array([np.inf if sg > 0 else 0.0 for (_, _, _, sg) in atoms])
        return lsq_linear(A, b, bounds=(lo, hi), method="trf", tol=1e-10, max_iter=3000).x

    def params_of(a):
        return np.array([[l, m, ak, shapes[si][0], shapes[si][1], shapes[si][2]]
                         for (l, m, si, sg), ak in zip(atoms, a)])

    def metrics(a):
        d = gauss_vis(us, vs, params_of(a)) - E_s if len(atoms) else -E_s
        rms = np.sqrt(np.sum(wts ** 2 * np.abs(d) ** 2) / np.sum(wts ** 2)) / norm
        return rms, np.abs(d).max() / norm, np.sqrt(np.mean(np.abs(d[r < 600]) ** 2)) / norm, abs(d[0]) / norm

    Ruv = E.copy()
    blocked = np.zeros((len(shapes), N, N), bool)
    n_iter = 0
    while len(atoms) < kmax and n_iter < 10 * kmax:
        n_iter += 1
        best = None
        for si, G in enumerate(Gs):
            c = np.fft.fftshift(np.fft.fft2(np.fft.ifftshift(w * G * Ruv)))
            score = c.real ** 2 / Gnorm[si]
            score[blocked[si]] = 0.0
            j, i = np.unravel_index(np.argmax(score), score.shape)
            if score[j, i] > 0 and (best is None or score[j, i] > best[0]):
                best = (score[j, i], i, j, si, 1 if c.real[j, i] > 0 else -1)
        if best is None:
            break
        _, i, j, si, sg = best
        blocked[si, j, i] = True
        atoms.append((lax[i], lax[j], si, sg))
        if len(atoms) % solve_every == 0 or len(atoms) >= kmax:
            a = solve()
            keep = np.abs(a) > 1e-9 * np.abs(a).max()     # bounded LSQ leaves ~1e-323 residues at the bounds
            atoms = [at for at, kp in zip(atoms, keep) if kp]
            amps = a[keep]
            Ruv = E - (gauss_vis(U, V, params_of(amps)) if len(atoms) else 0)
            rms, mx, rms_short, z = metrics(amps)
            if verbose:
                print(f"  K={len(atoms):3d} rms={rms:.4f} max={mx:.4f} rms<600={rms_short:.4f} zero={z:.4f}", flush=True)
            if rms < tol and rms_short < tol and z < tol:
                break
        else:
            l, m, si, sg = atoms[-1]
            A = Gs[si] * np.exp(2j * np.pi * (U * l + V * m))
            Ruv = Ruv - np.sum(w * (A.conj() * Ruv).real) / Gnorm[si] * A
    if len(atoms) % solve_every != 0:
        a = solve()
        keep = np.abs(a) > 1e-9 * np.abs(a).max()
        atoms = [at for at, kp in zip(atoms, keep) if kp]
        amps = a[keep]
    rms, mx, rms_short, z = metrics(amps)
    params = params_of(amps)
    info = dict(nmax=nmax, N=N, E0=E_s[0].real, sumabsF=float(np.abs(params[:, 2]).sum()),
                rms=rms, max=mx, rms_short=rms_short, zero=z)
    return params, info


# ----------------------------------------------------------------------------- yaml plumbing
def scale_flux(ft, f):
    ft = copy.deepcopy(ft)
    kind = list(ft)[0]

    def sc(fd):
        for k in ("i", "q", "u", "v"):
            if k in fd:
                fd[k] = float(fd[k] * f)
    if kind == "list":
        for fd in ft["list"]:
            sc(fd)
    else:
        sc(ft[kind]["fd"])
    return ft


def flux_i(comp):
    ft = comp["flux_type"]
    k = list(ft)[0]
    return ft["list"][0]["i"] if k == "list" else ft[k]["fd"]["i"]


def convert_component(c, **kw):
    s = c["comp_type"]["shapelet"]
    coeffs = [(int(k["n1"]), int(k["n2"]), float(k["value"])) for k in s["coeffs"]]
    params, info = fit_component(s["maj"], s["min"], s["pa"], coeffs, **kw)
    ra0, dec0 = np.deg2rad(c["ra"]), np.deg2rad(c["dec"])
    out = []
    for dl, dm, F, maj, mn, pa in params:
        if mn > maj:
            maj, mn, pa = mn, maj, pa + np.pi / 2
        ra, dec = lm_to_radec(dl, dm, ra0, dec0)
        out.append({"ra": float(np.rad2deg(ra) % 360), "dec": float(np.rad2deg(dec)),
                    "comp_type": {"gaussian": {"maj": float(maj / AS), "min": float(mn / AS),
                                               "pa": float(np.rad2deg(pa) % 180)}},
                    "flux_type": scale_flux(c["flux_type"], F)})
    return out, info


def _work(job):
    name, ci, c, kw = job
    t0 = time.time()
    g, info = convert_component(c, **kw)
    line = (f"{name:18s} comp{ci} nmax={info['nmax']:2d} N={info['N']:4d} ngauss={len(g):3d} "
            f"rms={info['rms']:.4f} max={info['max']:.4f} rms<600={info['rms_short']:.4f} zero={info['zero']:.4f} "
            f"E0={info['E0']:.4f} sumF={sum(flux_i(x) for x in g):.3f} sum|F|/F={info['sumabsF']/abs(info['E0']):.2f} "
            f"t={time.time()-t0:.1f}s")
    print(line, flush=True)
    return name, ci, g, line


def source_blocks(lines):
    """(name, start, end) line ranges of top-level sources in a hyperdrive yaml."""
    starts = [i for i, l in enumerate(lines) if re.match(r"^[^\s#-][^:]*:$", l)]
    starts.append(len(lines))
    return [(lines[a][:-1], a, b) for a, b in zip(starts[:-1], starts[1:])]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("infile")
    ap.add_argument("outfile")
    ap.add_argument("--only", nargs="*", help="only convert these sources (others copied unchanged)")
    ap.add_argument("--tol", type=float, default=0.003)
    ap.add_argument("--kmax", type=int, default=120)
    ap.add_argument("--uvmax", type=float, default=2000.0)
    ap.add_argument("--nproc", type=int, default=16)
    ap.add_argument("--report", default=None, help="write per-component fit report here (default: outfile + .report)")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    selftest()
    text = open(a.infile).read()
    lines = text.split("\n")
    blocks = [(n, s, e) for n, s, e in source_blocks(lines)
              if any("shapelet:" in l for l in lines[s:e]) and (not a.only or n in a.only)]
    print(f"{len(blocks)} sources with shapelet components", flush=True)
    srcs = {n: yaml.load("\n".join(lines[s:e]), Loader=yaml.CSafeLoader)[n] for n, s, e in blocks}
    kw = dict(tol=a.tol, kmax=a.kmax, uvmax=a.uvmax, verbose=a.verbose)
    jobs = [(n, ci, c, kw) for n in srcs for ci, c in enumerate(srcs[n]) if "shapelet" in c["comp_type"]]
    if a.nproc == 1 or a.verbose:
        results = [_work(j) for j in jobs]
    else:
        with Pool(a.nproc) as pool:
            results = pool.map(_work, jobs, chunksize=1)
    conv = {(r[0], r[1]): r[2] for r in results}
    pieces, pos = [], 0
    for n, s, e in blocks:
        pieces.append("\n".join(lines[pos:s]))
        comps = [x for ci, c in enumerate(srcs[n]) for x in conv.get((n, ci), [c])]
        pieces.append(yaml.dump({n: comps}, Dumper=yaml.CSafeDumper, default_flow_style=False, sort_keys=False).rstrip("\n"))
        pos = e
    pieces.append("\n".join(lines[pos:]))
    with open(a.outfile, "w") as f:
        f.write("\n".join(p for p in pieces if p != "") + ("" if lines[-1] == "" else "\n"))
    with open(a.report or a.outfile + ".report", "w") as f:
        f.write("\n".join(r[3] for r in results) + "\n")
    ng = sum(len(r[2]) for r in results)
    print(f"wrote {a.outfile}: {len(jobs)} shapelet components -> {ng} gaussians", flush=True)


if __name__ == "__main__":
    main()
