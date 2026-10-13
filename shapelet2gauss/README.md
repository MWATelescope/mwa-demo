# shapelet2gauss

Convert the shapelet components of a hyperdrive YAML source list into sets of Gaussians,
so the model can be predicted by software that only supports point and Gaussian
components (DP3 in particular: `sky_model/SkyModelFunctions.cc` throws
"Only point sources and Gaussian sources are supported" for anything else).

Produced `srclist_pumav3_EoR0LoBES_EoR1pietro_CenA-GP_2023-11-07_no-shapelets.yaml`
(see the srclists fork at <https://github.com/d3v-null/srclists>) from
[JLBLine/srclists](https://github.com/JLBLine/srclists)
`srclist_pumav3_EoR0LoBES_EoR1pietro_CenA-GP_2023-11-07.yaml` on 2026-10-13.

## What was done to that catalogue

1. **Fornax A** (2 shapelet components with 3828 coefficients each, plus 5 small Gaussians
   totalling 2.2 Jy) was replaced by the WODEN multiscale-CLEAN model
   [`examples/FornaxA/srclist_msclean_fornaxA_phase1+2.txt`](https://github.com/JLBLine/WODEN/blob/master/examples/FornaxA/srclist_msclean_fornaxA_phase1%2B2.txt),
   converted with `hyperdrive srclist-convert -i woden` (4544 points + 1736 Gaussians,
   reference frequency 188.79 MHz, default spectral index -0.8 because the WODEN file has a
   single frequency per component). **Caveat:** that model integrates to 468 Jy at 200 MHz,
   while the shapelet model integrates to 559 Jy (its zero-spacing envelope is 0.993 x the
   catalogue flux density), i.e. the Gaussian version is ~17% fainter.
2. The remaining **59 shapelet components** (55 sources, all in EoR1, 135 Jy in total, mostly
   45 coefficients / order 8) were fitted with Gaussians by `shapelet2gauss.py` as below:
   6114 Gaussians, median 107 per component.

Everything else in the catalogue (337k points, 15k Gaussians) is byte-for-byte unchanged.

## Method

* The shapelet and Gaussian visibility envelopes are implemented exactly as
  mwa_hyperdrive's `src/model/cpu.rs` (`model_shapelets`, `model_gaussians`), including the
  `i^(n1+n2)` factors, the `-min` sign on the second axis and the FWHM-based scale constant.
  Both were validated against `hyperdrive vis-simulate` output to 1e-5 before any fitting.
* Each shapelet is fitted in the uv plane with a **sign-constrained matching pursuit** over a
  dictionary of 8 Gaussian shapes (4 circular at the shapelet's finest scale, 4 elliptical
  with the shapelet's axes and position angle). Atoms are chosen from correlation maps on an
  FFT grid; amplitudes are re-solved every 5 atoms with bounded linear least squares
  (`scipy.optimize.lsq_linear`) on 6000 uv samples, 70% drawn from the real baseline-length
  distribution of MWA obs 1443210064 (Phase II compact, max 741 m) over 170-230 MHz and 30%
  uniform out to `--uvmax` (2000 wavelengths). The zero spacing carries 5% of the weight.
* The fit stops when the weighted rms, the rms on |uv| < 600 and the zero-spacing error are all
  below `--tol` (0.3% of the peak visibility), or at `--kmax` (120) atoms.
* Why not a free nonlinear multi-Gaussian fit: it converges on paper but finds cancelling
  pairs (+/-7000 Jy for a 2 Jy source). hyperdrive and DP3 evaluate Gaussian envelopes with
  the *phase-centre* uv coordinates while hyperdrive evaluates shapelets with
  component-centred ones, and that small projection difference destroys any cancellation,
  giving 100% errors. Sign constraints on a fixed dictionary make cancelling pairs impossible
  (sum|F| / F is typically 2-7).
* Limitations: the shapelet models ring strongly beyond ~1500 wavelengths (band-limited to
  5000 wavelengths their images have negative lobes larger than the peak). That structure is
  only reproduced approximately (weighted rms 0.5-1% out to 2000 wavelengths). For Phase II
  extended data, re-run with `MWA_BASELINES` pointing at a `.npy` of that array's baseline
  lengths (metres) and a larger `--uvmax`.

## Results

`fit_report_2023-11-07_srclist.txt` lists every component. Across the 59 components:
rms on |uv| < 600 wavelengths median 0.06%, worst 0.14%; zero-spacing error < 0.05%.
`e2e.py` (hyperdrive simulation of the shapelet vs Gaussian version of a source, obs
1443210064 phase centre, no beam) on 7 sources including the three brightest gives
0.04-0.17% rms and < 0.9% maximum visibility differences.

## Usage

```bash
# karabo-style env: numpy, scipy, pyyaml (C loader), pyuvdata; hyperdrive on PATH for e2e.py
python shapelet2gauss.py in.yaml out.yaml --nproc 20            # ~25 s for the 59 components
python shapelet2gauss.py in.yaml out.yaml --only nEXT035140-2743 --verbose
python e2e.py nEXT035140-2743 in.yaml out.yaml                  # downloads the metafits
python yaml2dp3.py out.yaml out.skymodel                         # DP3 / BBS text sky model
```

## Converting the YAML to a DP3 sky model

`hyperdrive srclist-convert -o ao` is not usable for this: the AO writer skips every source
with a curved power law, which is 77% of this catalogue's components. `yaml2dp3.py` writes the
DP3/BBS text format directly (DP3 reads it straight from `predict.sourcedb=file.skymodel`,
no `makesourcedb` needed):

* `power_law` (S0 (nu/nu0)^a) -> `LogarithmicSI=true, SpectralIndex=[a]`
* `curved_power_law` (S0 (nu/nu0)^a exp(q ln^2(nu/nu0))) -> `SpectralIndex=[a, q*ln(10)]`,
  because DP3 evaluates S0 (nu/nu0)^(c0 + c1 log10(nu/nu0)) (`base/PointSource.cc`)
* Gaussians: FWHM arcsec and position angle carry over unchanged; `OrientationIsAbsolute` is
  left false because hyperdrive also evaluates Gaussians in the phase-centre frame
* one patch per hyperdrive source (`--patch single` puts everything in one patch); shapelets
  raise, so run `shapelet2gauss.py` first
* fluxes below 1e-30 are zeroed (DP3 refuses denormals)

Validation: the 300 brightest sources for obs 1443210064 (`hyperdrive srclist-by-beam`,
12758 components, Fornax A included) were simulated into an MS with
`hyperdrive vis-simulate --no-beam` and predicted again by DP3 (`predict.usebeammodel=false`)
from the converted sky model. The two agree to 0.23% rms (phase residual < 0.75 deg, growing
with baseline length). With `--no-precession` in hyperdrive the disagreement is 30%, so the
remaining 0.2% is the difference between hyperdrive's precession and casacore's J2000
handling, not the sky-model conversion. Per-channel power ratios are 1.00000-1.00001, which
checks the curved-power-law mapping.
