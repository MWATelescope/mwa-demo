#!/bin/bash
# calibrate and image an OSKAR simulation with rapthor (one direction-dependent
# cycle, 3 x 3 facets that match 26_oskar_img.sh), then subtract rapthor's
# calibration model, corrupted by its direction-dependent solutions, with DP3 and
# measure how much sky that removed.
# usage guide: https://gist.github.com/d3v-null/63eb2255d8823783866da9e77debfce0
# runs in the rapthor container, as your own user, e.g.
#   docker run --rm --user $(id -u):$(id -g) -v $PWD:$PWD -w $PWD \
#     ghcr.io/d3v-null/rapthor-mwa:sha-e27456d-pass demo/28_oskar_rapthor.sh

export outdir=${outdir:-${PWD}/demo/data/}
export oskar_dir=${oskar_dir:-${outdir}/oskar}
export config=${config:-aa2}
export duration_s=${duration_s:-120}
export sim_name=${sim_name:-${config}_${duration_s}s}
export ms=${ms:-${oskar_dir}/vis/${sim_name}.ms}
export work=${work:-${oskar_dir}/rapthor/${sim_name}}
# true- and apparent-flux models of the same sources (25_oskar_apparent.py)
export true_skymodel=${true_skymodel:-${oskar_dir}/sky/${sim_name}_true.skymodel}
export app_skymodel=${app_skymodel:-${oskar_dir}/sky/${sim_name}_app.skymodel}
# facet layout written by 26_oskar_img.sh (3 x 3 facets of 1200 px at 3")
export facets=${facets:-${oskar_dir}/img/facets_3600px_1200px.reg}
export cpus=${cpus:-$(nproc)}
export mem_gb=${mem_gb:-200}
# rapthor runs DDECal with $cpus threads, and its memory grows with them: about
# 13 GB per thread for MWA 256T and 21 GB for case (h) (9 directions, 416
# channels), so lower cpus to fit your RAM (cpus=12 and 8 here, for 300 GB)
# DP3 threads for the final subtract
export numthreads=${numthreads:-$cpus}

set -euxo pipefail
export OPENBLAS_NUM_THREADS=1 TOIL_HISTORY=False TOIL_JOB_HISTORY=False
export HOME=${work}/.home XDG_CACHE_HOME=${work}/.home/.cache
mkdir -p "$HOME"

read -r ra dec < <(python3 -c "
import numpy as np
from casacore.tables import table
ra, dec = np.degrees(table('${ms}/FIELD', ack=False).getcol('PHASE_DIR')[0, 0])
print(ra % 360, dec)")

cat >"${work}/rapthor.parset" <<EOF
[global]
dir_working = ${work}/rapthor
input_ms = ${ms}
data_colname = DATA
generate_initial_skymodel = False
download_initial_skymodel = False
input_skymodel = ${true_skymodel}
apparent_skymodel = ${app_skymodel}
regroup_input_skymodel = True
facet_layout = ${facets}
strategy = ${work}/strategy.py
selfcal_data_fraction = 1.0
final_data_fraction = 1.0
dde_mode = faceting

[calibration]
use_included_skymodels = False
use_image_based_predict = False
llssolver = qr
maxiter = 150
propagatesolutions = True
solveralgorithm = directioniterative
onebeamperpatch = False
stepsize = 0.02
tolerance = 5e-3
fast_freqstep_hz = 1.248e6
fast_smoothnessconstraint = 5e6
fast_datause = single
medium_freqstep_hz = 1.248e6
medium_smoothnessconstraint = 5e6
slow_freqstep_hz = 4.992e6
slow_smoothnessconstraint = 1e7
correct_time_frequency_smearing = False
# no baseline-dependent averaging: with all MWA baselines shorter than the
# 20 km default, DP3 refuses the frequency averaging it asks for
bda_timebase = 0
bda_frequencybase = 0

[imaging]
cellsize_arcsec = 3.0
robust = 0.0
min_uv_lambda = 20
max_uv_lambda = 1e7
mgain = 0.8
do_multiscale_clean = False
dde_method = full
filter_skymodel = True
source_finder = bdsf
save_visibilities = False
compress_selfcal_images = False
compress_final_images = False
mem_gb = ${mem_gb}
apply_diagonal_solutions = True
grid_width_ra_deg = 3.0
grid_width_dec_deg = 3.0
grid_center_ra = ${ra}
grid_center_dec = ${dec}
grid_nsectors_ra = 0
skip_final_major_iteration = False
average_visibilities = False

[cluster]
batch_system = single_machine
max_nodes = 1
cpus_per_task = 0
max_cores = ${cpus}
max_threads = ${cpus}
deconvolution_threads = 16
mem_per_node_gb = ${mem_gb}
cwl_runner = toil
debug_workflow = False
keep_temporary_files = False
EOF

# one cycle: fast (8 s) scalar phase per facet against the input model,
# then image the 3 deg sector with 5 major cycles
cat >"${work}/strategy.py" <<'EOF'
strategy_steps = [
    {
        "do_calibrate": True,
        "do_slowgain_solve": False,
        "do_fulljones_solve": False,
        "peel_outliers": False,
        "peel_bright_sources": False,
        "max_normalization_delta": 0.3,
        "scale_normalization_delta": True,
        "solve_min_uv_lambda": 20,
        "fast_timestep_sec": 8.0,
        "medium_timestep_sec": 8.0,
        "slow_timestep_sec": 120.0,
        "fulljones_timestep_sec": 120.0,
        "do_normalize": False,
        "do_image": True,
        "auto_mask": 5.0,
        "auto_mask_nmiter": 2,
        "max_nmiter": 5,
        "channel_width_hz": 4.992e6,
        "threshisl": 4.0,
        "threshpix": 5.0,
        "regroup_model": False,
        # ignored: the facet layout fixes the directions
        "target_flux": 1.0,
        "max_directions": 9,
        "max_distance": None,
        "do_check": False,
    }
]
EOF

find "${work}/rapthor/pipelines" -maxdepth 2 -name jobstore -type d -exec rm -rf {} + 2>/dev/null || true
SECONDS=0
rapthor "${work}/rapthor.parset"
echo "rapthor took ${SECONDS} s" | tee "${work}/rapthor.time"

# subtract the calibration model, corrupted by the facet solutions, from DATA
h5parms=("${work}"/rapthor/solutions/calibrate_*/field-solutions.h5)
skymodels=("${work}"/rapthor/skymodels/calibrate_*/calibration_skymodel.txt)
h5parm=${h5parms[-1]}
skymodel=${skymodels[-1]}
residual="${work}/${sim_name}_rapthor_sub.ms"
rm -rf "$residual"
SECONDS=0
DP3 msin="$ms" msin.datacolumn=DATA msout="$residual" msout.uvwcompression=false msout.antennacompression=false msout.scalarflags=false \
    numthreads="$numthreads" \
    steps=[sub] \
    sub.type=h5parmpredict \
    sub.sourcedb="$skymodel" \
    sub.applycal.parmdb="$h5parm" \
    sub.applycal.correction=phase000 \
    sub.applycal.missingantennabehavior=flag \
    sub.operation=subtract \
    sub.usebeammodel=true \
    sub.beammode=full \
    sub.usefastpredict=false
echo "DP3 subtract took ${SECONDS} s" | tee "${work}/dp3_sub.time"
python3 "$(dirname "$0")/29_oskar_peel_metrics.py" \
    --input "$ms" --residual "$residual" \
    --label "${sim_name} rapthor" --json "${work}/${sim_name}_rapthor_metrics.json"
