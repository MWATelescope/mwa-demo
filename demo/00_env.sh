#!/bin/bash
# common environment variable defaults for the demo

# overrides for Setonix
if [[ "$PAWSEY" == "setonix" ]]; then
    # set outdir to $MYSCRATCH if it's not already set.
    if [[ -n $MYSCRATCH ]]; then export outdir=${outdir:-${MYSCRATCH}}; fi
    # TODO: maybe module unuse and module unload first?
    module load hyperdrive-amd-gfx90a/default
    # module load hyperdrive/0.4.1-peel-26pcn5v # for mwaeor users
    module load birli/default giant-squid/default hyperbeam/default wsclean/default mwalib/default singularity/default
    module load py-pip/default py-numpy/default casacore/default
fi

# activate the python virtual environment if it exists
if [[ -f .venv/bin/activate ]]; then
    source .venv/bin/activate
fi

# silly hack for macOS Birli
if [[ $(uname -o) == "Darwin" ]]; then
    export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib/
fi

# basically wsclean needs this
export OPENBLAS_NUM_THREADS=1

# base directory for demo data
# - defaults to demo/data in the current working directory (^ unless Setonix)
# - you may want to change this do a directory with more space if extending this demo
export outdir=${outdir:-${PWD}/demo/data/}

# these variables can sometimes be set to a location inaccessible from Docker,
# so we explicitly unset them here.
unset srclist
unset MWA_BEAM_FILE
# export srclist=${srclist:-${outdir}/srclist_pumav3_EoR0LoBES_EoR1pietro_CenA-GP_2023-11-07.yaml}
# hint: here's another sky model you can try.
export srclist=${srclist:-${outdir}/GGSM_updated.fits}
export MWA_BEAM_FILE=${MWA_BEAM_FILE:-${outdir}/mwa_full_embedded_element_pattern.h5}

export obsid=1121334536
# PREP
export timeres_s=2
export freqres_khz=40
export edgewidth_khz=80
# export tile_flags=""
# export birli_args="--sel-time 10 13"
# export birli_args="--no-sel-flagged-ants"
# CAL
export num_sources=500
export dical_args="--uvw-min 75l --uvw-max 1667l --max-iterations 300 --stop-thresh 1e-20" # max baseline of phase1
export apply_args="--time-average 8s --freq-average 80kHz"
# export dical_suffix="_GGSM"
# PEEL
export iono_sources=50
# export num_passes=2
# export num_loops=1
# export iono_freq_average=1280kHz
# export iono_time_average=8s
# export uvw_min=50lambda
# export uvw_max=300lambda
# export short_baseline_sigma=40
# export convergence=0.9

# ######### #
# FUNCTIONS #
# ######### #

# Source common functions used across multiple scripts
# Function definitions will be available after sourcing 00_functions.sh when SCRIPT_BASE is set
# (SCRIPT_BASE is set by individual scripts, not by this environment file)
if [[ -n "${SCRIPT_BASE:-}" ]]; then
    source "$SCRIPT_BASE/00_functions.sh"
fi

# ####### #
# SUMMARY #
# ####### #

echo "outdir:        $outdir"
echo "srclist:       $srclist"
echo "MWA_BEAM_FILE: $MWA_BEAM_FILE"
