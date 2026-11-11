# Workshop Part 6: Simulated configurations (SKA-Low AA2 and MWA 256T)

[Part 1](WORKSHOP_01.md) compared real MWA configurations. Here we simulate
them instead, with [OSKAR](https://github.com/OxfordSKA/OSKAR), so that we know
the true sky exactly, and compare three arrays observing the same sky, through
the same ionosphere, at the same time:

1. **AA2**: the 68-station SKA-Low AA2 array with its rotated stations,
   rebuilt from the SP-5941 simulation;
2. **MWA 256T**: the 256-tile MWA Phase III (MWAX) array;
3. **case (h)**: both arrays in one OSKAR telescope, combined incoherently.

We then image each with wsclean and peel each with hyperdrive and rapthor, and
measure how much of the simulated sky the subtraction model removed.

## Results at a glance (2 minutes)

Fraction of the simulated sky's visibility power that the subtraction removed
(1 is perfect; definitions in [step 6](#how-much-did-each-one-peel)):

| configuration | hyperdrive peel | rapthor (DP3 subtract) |
|---|---|---|
| AA2 | 0.874 | 0.974 |
| MWA 256T | 0.946 | 0.945 |
| case (h), MWA 256T + AA2 | 0.946 (AA2 half 0.899, MWA half 0.946) | 0.944 |

## Software

Three containers are used. They are big, so pull them before the workshop.

```bash
docker pull fdulwich/oskar-python3:2.12.0          # OSKAR 2.12 (CPU)
docker pull mwatelescope/mwa-demo:latest           # wsclean, python-casacore, mwalib
docker pull ghcr.io/d3v-null/rapthor-mwa:sha-e27456d-pass   # rapthor, DP3, EveryBeam
export outdir=${outdir:-${PWD}/demo/data/}
export oskar_dir=${outdir}/oskar
alias oskar='docker run --rm -v ${PWD}:${PWD} -w ${PWD} -e outdir -e oskar_dir fdulwich/oskar-python3:2.12.0'
alias demo='docker run --rm -v ${PWD}:${PWD} -w ${PWD} -e outdir -e oskar_dir mwatelescope/mwa-demo:latest -c'
alias rapthor='docker run --rm -v ${PWD}:${PWD} -w ${PWD} -e outdir -e oskar_dir ghcr.io/d3v-null/rapthor-mwa:sha-e27456d-pass'
```

Add `-e config -e duration_s ...` to an alias to pass the other variables used
below into the container.

The peeling step needs a newer hyperdrive than the one in `mwa-demo:latest`
(0.7.0): one that reads DP3 sky models (`--source-list-type dp3`) and
MeasurementSets from non-MWA telescopes, and that knows OSKAR's conventions
(`--convention oskar`, picked automatically when OSKAR wrote the MS). Until
[MWATelescope/mwa_hyperdrive#92](https://github.com/MWATelescope/mwa_hyperdrive/pull/92)
is released, build it from the `feat/conventions` branch inside the demo
image (CPU only, about 10 minutes):

```bash
demo "cargo install --locked --git https://github.com/MWATelescope/mwa_hyperdrive \
  --branch feat/conventions --root ${outdir}/hyperdrive-conventions"
export hyperdrive=${outdir}/hyperdrive-conventions/bin/hyperdrive
```

## 1. Sky model: LoTSS, mirrored onto EoR1

The SP-5941 simulation used `lotss_p129+33_negdec.skymodel`
([download](https://projects.pawsey.org.au/srcnet/lotss_p129+33_negdec.skymodel)):
LoTSS-DR2, mirrored into the southern sky. Matching all 135,732 of its
components against LoTSS-DR2 ([Shimwell et al. 2022](https://vizier.cds.unistra.fr/viz-bin/VizieR?-source=J/A%2BA/659/A1))
gives the transform exactly:

| step | rule |
|---|---|
| selection | every LoTSS-DR2 source within 8.5° of (129.3395°, +32.8915°) |
| position | RA unchanged, Dec → −Dec (a mirror in the equator; the PA is not mirrored) |
| Stokes I | `SpeakTot` (total flux density at 144 MHz), mJy → Jy; Q = U = V = 0 |
| shape | `DCMaj` × `DCMin` (deconvolved, arcsec) at position angle `PA`; `POINT` if `DCMaj` = 0 |
| spectrum | reference 144 MHz, spectral index −0.7 for every source, RM 0 |

[`demo/20_oskar_skymodel.py`](demo/20_oskar_skymodel.py) queries VizieR and
applies it. Rebuild SP-5941's model and check it against the published one:

```bash
demo "python demo/20_oskar_skymodel.py --field 129.3395 32.8915 --name p129+33_negdec \
  --outdir ${oskar_dir}/sky --compare lotss_p129+33_negdec.skymodel"
# matched to 0.1 arcsec: 135732; max |diff| I, maj, min, PA: 0
```

LoTSS-DR2 has nothing at RA 60°, and near RA 129° it stops at Dec +25°, so the
EoR1 field takes the fully covered LoTSS field at (0°, +27°), mirrors it onto
EoR0 (0°, −27°) and shifts it by +60° in RA onto EoR1. A shift in RA is a
rotation about the celestial pole, so every source separation is preserved.

```bash
demo "python demo/20_oskar_skymodel.py --field 0 27 --target 60 -27 \
  --name eor1_negdec --outdir ${oskar_dir}/sky"
# 125988 LoTSS-DR2 sources within 8.5 deg of 0.0, 27.0 ... 1553.4 Jy at 144 MHz
```

This writes `eor1_negdec.skymodel` (DP3 format, read by DP3, rapthor and
`hyperdrive --source-list-type dp3`) and `eor1_negdec.osm` (OSKAR). Use
`hyperdrive srclist-convert -i dp3` to turn it into a hyperdrive yaml or fits
list.

## 2. Telescopes

```bash
mkdir -p ${outdir}/1476560224/raw
curl -L -o ${outdir}/1476560224/raw/1476560224.metafits \
  'http://ws.mwatelescope.org/metadata/fits?obs_id=1476560224'
demo "python demo/21_oskar_telescope.py --metafits ${outdir}/1476560224/raw/1476560224.metafits \
  --outdir ${oskar_dir}/telescopes"
```

**AA2.** The SP-5941 zip
([SP-5941_AA2_25G.zip](https://projects.pawsey.org.au/srcnet/SP-5941_AA2_25G.zip),
25.6 GB) holds one OSKAR 2.12.0-dev MeasurementSet and no telescope model or
README. OSKAR 2.12 records the whole station layout in the MS, though, so
[`demo/21_oskar_telescope.py`](demo/21_oskar_telescope.py) rebuilds the model
from about 1 MB of subtables, read straight out of the remote zip with HTTP
range requests:

- station centres from `ANTENNA/POSITION` (`layout_ecef.txt`), the reference
  position from `OBSERVATION/ARRAY_CENTER`;
- each station's 256 element positions from `PHASED_ARRAY`
  (`COORDINATE_AXES`ᵀ · `ELEMENT_OFFSET`, `layout.txt`);
- each station's rotation from `FEED/RECEPTOR_ANGLE` (`feed_angle.txt`).

The 68 stations are E8–E13, S8–S16 and N8–N16 clusters (station315_E8-1 to
station510_N16-4). Their element layouts are the SKA-Low station layouts
*unrotated*: the same as the stations in `SKA_Low_AA1_SP4964.tm` once rotated
by the station angle (to 0.7 mm), and the rotation is applied only to the
dipoles, through `feed_angle.txt`. Rotations range from −178° to +179° and
come in ± pairs (S8-1 −108.7°, S8-2 +108.7°, ...).

**MWA 256T.** Tile positions come from the metafits of a Phase III (MWAX,
256-tile) observation, 1476560224, via mwalib. Each tile is a 4 × 4 grid of
OSKAR dipoles at 1.1 m spacing, unrotated. This is not the MWA FEE beam: there
is no ground screen or mutual coupling.

**Case (h).** One telescope with the 68 AA2 stations followed by the 256 MWA
tiles; each station has its own directory, so OSKAR evaluates a 256-element
SKA-Low beam for the first 68 and a 16-dipole MWA tile beam for the rest. All
three models use the AA2 reference position, so the TEC screen (below) sits in
the same place over the site for every configuration.

## 3. Ionosphere

A mild, single-layer, frozen-flow Kolmogorov screen:

```bash
oskar python3 demo/22_oskar_tec_screen.py --duration-s 120 --out ${oskar_dir}/screen/tec_120s.fits
```

| parameter | value |
|---|---|
| dTEC rms over the screen | 0.01 TECU |
| spectrum | Kolmogorov, (k² + k₀²)^(−11/6), outer scale 100 km |
| height | 300 km (OSKAR `screen_height_km`) |
| size, pixel | 200 km × 200 km, 250 m |
| motion | frozen flow, 100 km/h towards 60° (E of N) |
| time step | 8 s (one screen per integration) |
| differential dTEC rms | 0.0016 TECU over 1 km, 0.0076 over 10 km, 0.010 over 65 km |
| phase at 150 MHz | 5° over 1 km, 25° over 10 km, 33° over 65 km |

OSKAR applies phase = −8.44797245×10⁹ · dTEC / ν per station and source at the
pierce point ([OSKAR docs](https://github.com/OxfordSKA/OSKAR/blob/master/docs/theory/tec_screens.rst)).

## 4. Simulate

| parameter | value |
|---|---|
| phase centre | EoR1, RA 60°, Dec −27° |
| date | 2000-01-01 (SP-5941's date), centred on EoR1's transit at the SKA-Low site (13:30:51 UTC) |
| duration | `duration_s`, 120 s (2 min); 7200 s for the 2-hour run |
| integration | 8 s |
| channels | 416 × 48 kHz, centres 140.000–159.920 MHz (as SP-5941) |
| correlations | XX, XY, YX, YY, cross-correlations only |
| smearing | 48 kHz bandwidth and 8 s time smearing |
| beams | full polarisation, normalised at the phase centre |
| sky | `eor1_negdec.osm`, sources ≥ 10 mJy (`flux_min`): 12,414 of 125,988 sources, 86% of the flux, 99.97% of Σ I² |
| output | MeasurementSet v2 |

```bash
for config in aa2 mwa256t aa2_mwa256t; do
  docker run --rm -v ${PWD}:${PWD} -w ${PWD} -e outdir -e config=$config \
    fdulwich/oskar-python3:2.12.0 demo/23_oskar_sim.sh
done
```

OSKAR's CPU path runs one thread per time step of a block, so a 2-minute
simulation (15 time steps) uses at most 15 cores. To use more, simulate
sub-bands in parallel (`first_channel=0 num_channels=208`,
`first_channel=208 num_channels=208`) and join them with
[`demo/23_oskar_concat.sh`](demo/23_oskar_concat.sh). Set `flux_min=min` for
the whole sky model (about 10x slower).

Because OSKAR computes every baseline on its own, the AA2 × AA2 and
MWA × MWA baselines of case (h) are bit-for-bit identical to the AA2-only and
MWA-only simulations (checked on a 2-time-step, 2-channel run, and on the full
AA2 `TRUE_DATA` of the 2-minute runs), so you can also cut a sub-array out of
case (h) with [`demo/23_oskar_split.py`](demo/23_oskar_split.py). The numbers
below did that for MWA 256T, after the noise and derotation steps that follow,
which saves a 6-hour simulation and gives MWA 256T the same noise as the MWA
half of case (h):

```bash
demo "python demo/23_oskar_split.py ${oskar_dir}/vis/aa2_mwa256t_120s.ms \
  ${oskar_dir}/vis/mwa256t_120s.ms --first 68 --last 323"
```

Then keep the noise-free sky in a `TRUE_DATA` column, add thermal noise to
`DATA`, set `WEIGHT` = 1/σ², and for case (h) flag the AA2 × MWA baselines:

```bash
demo "python demo/24_oskar_noise.py ${oskar_dir}/vis/aa2_120s.ms"
demo "python demo/24_oskar_noise.py ${oskar_dir}/vis/mwa256t_120s.ms"
demo "python demo/24_oskar_noise.py ${oskar_dir}/vis/aa2_mwa256t_120s.ms --flag-cross-array"
```

| array | A_eff/T_sys (150 MHz) | SEFD | σ per visibility (48 kHz, 8 s) |
|---|---|---|---|
| AA2 station | 0.75 m²/K | 3.7 kJy | 4.2 Jy |
| MWA tile | 0.086 m²/K (21.5 m² / 250 K) | 32 kJy | 37 Jy |

### What "case (h), incoherent" means here

The SP-5941 material (the zip) only contains the AA2 MeasurementSet; it does
not define "case (h)". We take it as the arrays sharing a sky, an ionosphere,
a phase centre and a time range but *not a correlator*: AA2 × AA2 and
MWA × MWA baselines exist, AA2 × MWA baselines do not, and the two sets are
combined only when imaging (each weighted by its own noise). OSKAR still
computes the cross-array baselines; `--flag-cross-array` flags them.

### Derotate the AA2 feeds

AA2 stations are rotated, and their dipoles with them. For an unpolarised sky
that scales XX and YY by cos(θᵢ − θⱼ) and moves the rest into XY and YX, by a
different amount on every baseline: 53% of the noise-free AA2 visibility power is in XY
and YX. wsclean forms Stokes I as (XX + YY)/2, so an AA2 image made straight
from OSKAR's visibilities averages cos(θᵢ − θⱼ) over baselines and loses most
of the sky (the brightest source peaks at 14 mJy/beam instead of 0.88 Jy/beam),
and hyperdrive assumes all tiles share one feed orientation.
[`demo/24_oskar_derotate.py`](demo/24_oskar_derotate.py) rotates each
station's feeds back to a common orientation, in place, for `DATA` and
`TRUE_DATA`, and rewrites `FEED/RECEPTOR_ANGLE` and
`PHASED_ARRAY/COORDINATE_AXES` to match, so that EveryBeam (in rapthor) models
the derotated stations too. Afterwards XY and YX hold 0.00% of the power. The
transform is unitary per baseline, so none of the power metrics below depend
on it. It does nothing to MWA tiles, which are not rotated.

```bash
demo "python demo/24_oskar_derotate.py ${oskar_dir}/vis/aa2_120s.ms"
demo "python demo/24_oskar_derotate.py ${oskar_dir}/vis/aa2_mwa256t_120s.ms"
```

## 5. Image

[`demo/26_oskar_img.sh`](demo/26_oskar_img.sh) images with wsclean the way
rapthor facets a sector: a 3600 px × 3″ (3.00°) image cut into 3 × 3 facets of
1200 px (1°), each gridded with 2× padding (2400 px), Briggs robust 0,
5 major cycles and a fixed 10.43″ × 12.79″ restoring beam.

```bash
for config in aa2 mwa256t aa2_mwa256t; do
  demo "config=$config demo/26_oskar_img.sh"                        # data
  demo "config=$config data_column=TRUE_DATA demo/26_oskar_img.sh"  # true sky, no noise
done
```

The restoring beam and the 3″ pixels suit AA2 (λ/B ≈ 6″ at 150 MHz). For the
MWA alone the PSF is about 2′, so its images are oversampled 40× and the
clean components are restored with a beam much smaller than the PSF.

## 6. Peel

### hyperdrive

hyperdrive predicts every tile with one beam (MWA FEE or analytic), which is
neither OSKAR's AA2 station nor its dipole-grid MWA tile. So we peel with
`--no-beam` against an **apparent** sky model made with OSKAR's own beam:
[`demo/25_oskar_apparent.py`](demo/25_oskar_apparent.py) evaluates the
station-averaged Stokes I beam at every source (5 times across the
observation, at 140, 150 and 160 MHz) and writes the 500 apparently brightest
sources with their apparent flux and spectral index.

hyperdrive also has one beam per run, so case (h) is peeled as its two
sub-arrays (its cross-array baselines are flagged anyway), each with its own
apparent model, and the powers are added. When MWA 256T was cut out of case
(h), as here, the MWA half of case (h) is the same data with the same apparent
model, so link its peel instead of running it twice (2.5 hours on 32 cores);
the peel script then only measures it:

```bash
ln -s ../vis/mwa256t_120s.ms ${oskar_dir}/peel/aa2_mwa256t_120s_mwa256t.ms
ln -s mwa256t_120s_mwa256t_hyp_peel.ms ${oskar_dir}/peel/aa2_mwa256t_120s_mwa256t_hyp_peel.ms
```

```bash
for config in aa2 mwa256t aa2_mwa256t; do
  oskar python3 demo/25_oskar_apparent.py --sim-ini ${oskar_dir}/vis/${config}_120s.ini \
    --num-sources 500 --out ${oskar_dir}/sky/${config}_120s_app.skymodel \
    --out-true ${oskar_dir}/sky/${config}_120s_true.skymodel
done
# per sub-array models for case (h)
for part in aa2 mwa256t; do
  oskar python3 demo/25_oskar_apparent.py --sim-ini ${oskar_dir}/vis/aa2_mwa256t_120s.ini \
    --telescope ${oskar_dir}/telescopes/${part}.tm --num-sources 500 \
    --out ${oskar_dir}/sky/aa2_mwa256t_120s_${part}_app.skymodel
done
for config in aa2 mwa256t aa2_mwa256t; do
  demo "config=$config hyperdrive=$hyperdrive demo/27_oskar_peel.sh"
done
```

[`demo/27_oskar_peel.sh`](demo/27_oskar_peel.sh) subtracts the 500 sources and
ionospherically peels the brightest 50 of them (a position shift and gain per
source per 8 s and 1.248 MHz), 2 passes of 4 loops, baselines from 20 λ.

hyperdrive 0.8.1 (`feat/conventions`) writes correctly peeled visibilities for
every channel, but on a MeasurementSet without MWA coarse channels it flags
all channels except the first four in its output.
[`demo/27_oskar_restore_flags.py`](demo/27_oskar_restore_flags.py) (called by
the peel script) puts the input flags and weights back.

### rapthor

[`demo/28_oskar_rapthor.sh`](demo/28_oskar_rapthor.sh) runs one rapthor cycle
with the facet layout of step 5 (3 × 3 facets of 1°, one calibration direction
each): a scalar-phase solve per facet every 8 s and 1.248 MHz against the same
500-source model (true fluxes; DP3 applies OSKAR's station beam through
EveryBeam, which reads the `PHASED_ARRAY` table OSKAR wrote), then a 3600 px,
3″, robust 0 image with 5 major cycles. Its "peel" is DP3 subtracting that
calibration model, corrupted by the facet solutions, from `DATA`.

```bash
for config in aa2 mwa256t aa2_mwa256t; do
  cpus=16; [[ $config == mwa256t ]] && cpus=12; [[ $config == aa2_mwa256t ]] && cpus=8
  docker run --rm --memory 300g --memory-swap 300g -v ${PWD}:${PWD} -w ${PWD} \
    -e outdir -e config=$config -e cpus=$cpus \
    ghcr.io/d3v-null/rapthor-mwa:sha-e27456d-pass demo/28_oskar_rapthor.sh
done
```

Mind the memory. rapthor gives DDECal all `cpus` cores, and DDECal holds
about 14 GB per thread for MWA 256T and 21 GB per thread for case (h) (9
directions × 416 channels × 32,640 or 52,326 baselines). With 32 threads, a
single MWA 256T solve wants more than 300 GB. The `cpus` values above keep each
run at about 170 GB (AA2 needs about 20 GB), and the `--memory` cap makes an
overrun kill the container instead of the host. Run one at a time.
Baseline-dependent averaging is off (`bda_timebase = 0`): every MWA baseline
is shorter than rapthor's 20 km BDA reference, and DP3 refuses the averaging
it asks for.

### How much did each one peel?

[`demo/29_oskar_peel_metrics.py`](demo/29_oskar_peel_metrics.py) compares, on
every unflagged cross-correlation, channel and polarisation, the data D that
went in (sky + noise), the true sky S (`TRUE_DATA`, no noise) and the residual R
that came out. The subtracted model is M = D − R, and

- **true-sky power peeled** = 1 − ‖S − M‖² / ‖S‖²: the fraction of the
  simulated sky's visibility power that the subtraction removed. 1 is perfect;
  it falls for sources not in the model and for errors in their positions,
  fluxes, beam or ionosphere, and is negative if the subtraction adds power.
- **model / true** = ‖M‖² / ‖S‖²
- **data power peeled** = 1 − ‖R‖² / ‖D‖², what you would measure without
  knowing the truth; it is small when noise dominates the data.

```bash
demo "python demo/29_oskar_peel_metrics.py --summary ${oskar_dir}/peel/*_metrics.json ${oskar_dir}/rapthor/*/*_metrics.json"
```

For the 2-minute runs:

| run | true-sky power peeled | model / true | data power peeled | noise share of data |
|---|---|---|---|---|
| AA2, hyperdrive | 0.8740 | 0.8884 | 0.0881 | 0.8992 |
| AA2, rapthor | 0.9738 | 0.9888 | 0.0983 | 0.8992 |
| MWA 256T, hyperdrive | 0.9458 | 0.9283 | 0.2269 | 0.7601 |
| MWA 256T, rapthor | 0.9449 | 0.9291 | 0.2267 | 0.7601 |
| case (h), hyperdrive, AA2 half | 0.8992 | 0.8959 | 0.0907 | 0.8993 |
| case (h), hyperdrive, MWA half | 0.9458 | 0.9283 | 0.2269 | 0.7601 |
| case (h), hyperdrive, combined | 0.9458 | 0.9283 | 0.2268 | 0.7602 |
| case (h), rapthor | 0.9439 | 0.9281 | 0.2264 | 0.7602 |

The combined case (h) numbers are power-weighted, and the MWA half carries
99.97% of the true-sky power (32,640 of its 34,918 unflagged baselines, and
tiles with a much wider beam), so they follow MWA 256T. The AA2 half of case
(h) is the same noise-free sky as AA2 alone (identical `TRUE_DATA`) with a
different noise realisation; that alone moves hyperdrive from 0.874 to 0.899,
which is a fair idea of the scatter in these numbers. rapthor on AA2 gives the
same 0.974 with and without baseline-dependent averaging.

In the image plane (Stokes I, robust rms and extremes of the central 1.2° ×
1.2°; "true" is the noise-free `TRUE_DATA`, cleaned the same way):

| image | rms (mJy/beam) | peak (Jy/beam) | min (Jy/beam) |
|---|---|---|---|
| AA2, true | 1.49 | 0.877 | −0.022 |
| AA2, data | 1.84 | 0.876 | −0.024 |
| AA2, hyperdrive residual | 1.49 | 0.036 | −0.030 |
| AA2, rapthor residual | 1.16 | 0.013 | −0.015 |
| MWA 256T, true | 23.34 | 1.281 | −0.084 |
| MWA 256T, data | 23.46 | 1.285 | −0.084 |
| MWA 256T, hyperdrive residual | 6.45 | 0.317 | −0.089 |
| MWA 256T, rapthor residual | 6.66 | 0.307 | −0.037 |
| case (h), true | 3.52 | 0.903 | −0.031 |
| case (h), data | 3.63 | 0.900 | −0.028 |
| case (h), rapthor residual | 1.54 | 0.156 | −0.015 |

The MWA rms is confusion and sidelobes at 2′ resolution, not noise, which is
why peeling lowers it so much. The case (h) hyperdrive residual is two
MeasurementSets (one per sub-array) and is not imaged here.

### Sizes and runtimes (2 minutes, 32-core CPU host, no GPU)

| | AA2 | MWA 256T | case (h) |
|---|---|---|---|
| stations, baselines | 68, 2,278 | 256, 32,640 | 324, 52,326 (34,918 unflagged) |
| MS as simulated (`DATA` only) | 0.47 GB | about 6.2 GB (cut from case (h)) | 10.0 GB |
| MS with `TRUE_DATA` and `WEIGHT_SPECTRUM` | 0.94 GB | 17 GB | 27 GB |
| OSKAR | 2.9 h, 16 threads | (cut from case (h)) | 5.7 h, 2 sub-bands × 15 threads |
| wsclean, per image | 4 min, 16 threads | 20 min, 8 threads | 27 min, 8 threads |
| hyperdrive peel | 23 min | 2.6 h (6.9 GB RAM) | 12 min (AA2 half) + MWA half reused |
| rapthor (calibrate + image) | 10 min, 16 cores (19 GB) | 73 min, 12 cores (173 GB) | 2.3 h, 8 cores (177 GB) |
| DP3 subtract | 6 min | 15 min | 34 min |

## Scaling to the 2-hour integration

Only `duration_s` changes (900 integrations instead of 15), plus a TEC screen
long enough to cover it:

```bash
oskar python3 demo/22_oskar_tec_screen.py --duration-s 7200 --interval-s 60 \
  --out ${oskar_dir}/screen/tec_7200s.fits
export duration_s=7200
```

Everything here scales linearly with the number of 8 s integrations, so the
2-hour numbers below are the 2-minute ones × 60 (extrapolated, not run):

| | AA2 | MWA 256T | case (h) |
|---|---|---|---|
| rows | 2,050,200 | 29,376,000 | 47,093,400 |
| MS, `DATA` only | 28 GB | ~370 GB | ~600 GB |
| MS with `TRUE_DATA` and `WEIGHT_SPECTRUM` | 56 GB | 1.0 TB | 1.6 TB |
| OSKAR on these 32 CPU cores | ~170 h | (cut from case (h)) | ~340 h |
| hyperdrive peel (CPU) | ~23 h | ~150 h | ~12 h + MWA |
| rapthor + DP3 subtract | ~15 h | ~90 h | ~170 h |
| wsclean, per image | ~4 h | ~20 h | ~27 h |

The SP-5941 product is the AA2 one: 2,050,200 rows (2,278 baselines × 900
integrations) × 416 channels × 4 correlations of complex64 is 27.3 GB
(25.4 GiB), which is the "25 GB MSv2" (the zip is 25.6 GB). For 2 hours,
run OSKAR on a GPU (its CPU path is what makes these simulations take hours)
and use the CUDA build of hyperdrive. rapthor's DDECal memory comes from its
threads and the 8 s solution interval rather than the duration, so it should
stay near the 2-minute peaks (not checked for 2 hours). Check disk
space first: case (h) needs about 2 TB with its intermediates.

## Limitations

- **Beams.** Both station types use OSKAR's default analytic dipole element
  (no element-pattern files): the AA2 station is 256 of them in the SKA-Low
  layout, the MWA tile a 4 × 4 grid with no ground screen or mutual coupling,
  not the MWA FEE beam. Neither is the SKALA4.1 embedded element pattern.
  hyperdrive peels with `--no-beam` against an apparent sky model from that
  same OSKAR beam, so its numbers do not test hyperdrive's own beam models.
  rapthor predicts through EveryBeam, which reads OSKAR's `PHASED_ARRAY`
  table; the known WSClean/EveryBeam MWA primary-beam normalisation issue (a
  factor of about 40 in "true sky" fluxes) means apparent and true fluxes
  should not be compared across tools without care.
- **Sky.** Only sources ≥ 10 mJy are simulated (86% of the flux), the model
  is LoTSS-DR2 mirrored and shifted onto EoR1 rather than the real EoR1 sky,
  every source has spectral index −0.7, and there is no diffuse emission.
  The peel models are the 500 apparently brightest sources, so the unmodelled
  faint sources cap the true-sky power peeled below 1.
- **Ionosphere.** A single frozen-flow 0.01 TECU Kolmogorov layer; no
  multi-layer screens, scintillation or Faraday rotation.
- **Noise.** Thermal noise from nominal A_eff/T_sys at 150 MHz, flat over the
  band; one realisation, which moves the peel metrics by about 0.02.
- **Case (h).** "Incoherent" is our interpretation (no cross-array
  correlations); the SP-5941 material does not define case (h).
- **hyperdrive.** Needs a build from `feat/conventions`
  ([MWATelescope/mwa_hyperdrive#92](https://github.com/MWATelescope/mwa_hyperdrive/pull/92))
  and restores flags afterwards (`27_oskar_restore_flags.py`). It has one
  beam per run, so case (h) is peeled per sub-array.
- **rapthor.** One cycle of scalar-phase facet calibration against the input
  model, not a full self-calibration strategy. The MWA image uses 3″ pixels
  and AA2's restoring beam, as specified, which oversamples MWA's 2′ PSF.
- **Duration.** Only the 2-minute runs were done; the 2-hour numbers are
  linear extrapolations.
