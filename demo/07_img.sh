#!/bin/bash

# ### #
# ENV #
# ### #
# see: 00_env.sh
if [ -n "$ZSH_VERSION" ]; then ME="${0:A}"; else ME=$(realpath ${BASH_SOURCE:0}); fi
export SCRIPT_BASE=${SCRIPT_BASE:-$(dirname $ME)}
source "$SCRIPT_BASE/00_env.sh"

export obsid=${obsid:-1121334536}
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
export briggs=${briggs:-0}
export scale=${scale:-"20asec"}
export mgain=${mgain:-0.85}
export mscale=${mscale:-0.6}
export size=${size:-2048}
export gain=${gain:-0.1}

cores=$(nproc --all)
export cpus=${cpus:-$cores}

export taper=${taper:-}
export multiscale=${multiscale:-}

if [[ -n $multiscale ]]; then
    multiscale="-multiscale -multiscale-scale-bias=${mscale}"
fi

mkdir -p "${outdir}/${obsid}/img"
export imname=${imname:-${obsid}}
export imgname="${outdir}/${obsid}/img/${imname}"

# wsclean needs to know the directory of the beam file
export beam_path="${MWA_BEAM_FILE%/*}"
[[ $beam_path =~ / ]] || export beam_path="${PWD}"

# set idg_mode to "cpu" or "hybrid" based from gpus
export idg_mode="cpu"
if [[ -n "${gpus:-}" ]]; then
    export idg_mode="hybrid"
fi

if [ ! -f "${imgname}-image-pb.fits" ]; then
    wsclean \
        -name "${imgname}" \
        -size ${size} ${size} \
        -j $cpus \
        -scale ${scale} \
        -pol I \
        -nmiter 2 \
        -niter 10000 \
        -mgain ${mgain} \
        -gridder idg -grid-with-beam -idg-mode $idg_mode \
        -weight briggs ${briggs} \
        ${multiscale} ${taper} \
        -gain ${gain} \
        -auto-threshold 1 -auto-mask 3 \
        -make-psf \
        -mwa-path "$beam_path" \
        -temp-dir /tmp \
        $cal_ms
else
    echo "${imgname}-image-pb.fits exists, skipping wsclean"
fi
