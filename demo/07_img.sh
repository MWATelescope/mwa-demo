#!/bin/bash

# ### #
# ENV #
# ### #
# see: 00_env.sh
export SCRIPT_BASE=${SCRIPT_BASE:-${PWD}/demo/}
source "$SCRIPT_BASE/00_env.sh"

export obsid=${obsid:-1341914000}

# check for calibrated measurement set from previous step
export cal_ms="${cal_ms:-${outdir}/${obsid}/cal/hyp_cal_${obsid}.ms}"

set -e
if (($(ls -ld $cal_ms | wc -l) < 1)); then
    echo "cal_ms=$cal_ms does not exist. try running 06_cal.sh"
    exit 1
fi

# ### #
# IMG #
# ### #
mkdir -p "${outdir}/${obsid}/img"

# wsclean needs to know the directory of the beam file
export beam_path="${MWA_BEAM_FILE%/*}"
[[ $beam_path =~ / ]] || export beam_path="${PWD}"

# set idg_mode to "cpu" or "hybrid" based from gpus
export idg_mode="cpu"
if [[ -n "${gpus:-}" ]]; then
    export idg_mode="hybrid"
fi

export imgname="${outdir}/${obsid}/img/wsclean_hyp_${obsid}"
if [ ! -f "${imgname}-image.fits" ]; then
    eval $wsclean \
        -name "${imgname}" \
        -size 2048 2048 \
        -scale 20asec \
        -pol i \
        -niter 100 \
        -gridder idg -grid-with-beam -idg-mode $idg_mode \
        -multiscale \
        -weight briggs 0 \
        -mgain 0.85 -gain 0.1 \
        -auto-threshold 1 -auto-mask 3 \
        -no-update-model-required \
        -make-psf \
        -small-inversion \
        -mwa-path "$beam_path" \
        $cal_ms
fi
