#!/bin/bash

# ### #
# ENV #
# ### #
# see: 00_env.sh
if [ -n "$ZSH_VERSION" ]; then ME="${0:A}"; else ME=$(realpath ${BASH_SOURCE:0}); fi
export SCRIPT_BASE=${SCRIPT_BASE:-$(dirname $ME)}
source "$SCRIPT_BASE/00_env.sh"

export obsid=${obsid:-1341914000}

# check for calibrated measurement set from previous step
export cal_ms="${cal_ms:-${outdir}/${obsid}/cal/hyp_cal_${obsid}.ms}"

set -e
if (($(ls -ld $cal_ms | wc -l) < 1)); then
    echo "cal_ms=$cal_ms does not exist. trying 06_cal.sh"
    $SCRIPT_BASE/06_cal.sh
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
    wsclean \
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
        -make-psf \
        -circular-beam \
        -mwa-path "$beam_path" \
        -temp-dir /tmp \
        $cal_ms
else
    echo "${imgname}-image.fits exists, skipping wsclean"
fi
