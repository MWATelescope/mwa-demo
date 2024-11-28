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
# export cal_ms="${cal_ms:-${outdir}/${obsid}/cal/hyp_cal_${obsid}.ms}"
export ms_pattern=${ms_pattern:-${outdir}/${obsid}/\{cal,peel\}/hyp_\*${obsid}\*.ms}
if ! eval ls -1d $ms_pattern >/dev/null; then
    echo "ms_pattern=$ms_pattern does not exist. trying 06_cal.sh"
    $SCRIPT_BASE/06_cal.sh
fi
echo ms_pattern=$ms_pattern

# ### #
# IMG #
# ### #

#   ** GENERAL OPTIONS **
export wsclean_args=${wsclean_args:-}
# -j <threads>
#    Specify number of computing threads to use, i.e., number of cpu cores that will be used.
#    Default: use all cpu cores.
cores=$(nproc --all)
export cpus=${cpus:-$cores}
if [[ -n $cpus ]]; then
    export wsclean_args="${wsclean_args} -j ${cpus}"
fi
# -temp-dir <directory>
#    Set the temporary directory used when reordering files. Default: same directory as input measurement set.
# using /tmp because of the large amount of temporary files created
export temp_dir=${temp_dir:-/tmp}
if [[ -n $temp_dir ]]; then
    export wsclean_args="${wsclean_args} -temp-dir ${temp_dir}"
fi
# -mwa-path <path>
#    Set path where to find the MWA beam file(s).
export beam_path="${MWA_BEAM_FILE%/*}"
[[ $beam_path =~ / ]] || export beam_path="${PWD}"
export wsclean_args="${wsclean_args} -mwa-path $beam_path"

#   ** WEIGHTING OPTIONS **
# -weight <weightmode>
#    Weightmode can be: natural, uniform, briggs. Default: uniform. When using Briggs' weighting,
#    add the robustness parameter, like: "-weight briggs 0.5".
export briggs=${briggs:-0}
if [[ -n $briggs ]]; then
    export wsclean_args="${wsclean_args} -weight briggs ${briggs}"
fi

#   ** INVERSION OPTIONS **
# -size <width> <height>
#    Set the output image size in number of pixels (without padding).
export size=${size:-4096}
if [[ -n $size ]]; then
    export wsclean_args="${wsclean_args} -size ${size} ${size}"
else
    echo "env size not set, required"
    exit 1
fi
# -scale <pixel-scale>
#    Scale of a pixel. Default unit is degrees, but can be specificied, e.g. -scale 20asec. Default: 0.01deg.
export scale=${scale:-20asec}
if [[ -n $scale ]]; then
    export wsclean_args="${wsclean_args} -scale ${scale}"
else
    echo "env scale not set, required"
    exit 1
fi

#   ** DATA SELECTION OPTIONS **
# -pol <list>
#    Default: 'I'. Possible values: XX, XY, YX, YY, I, Q, U, V, RR, RL, LR or LL (case insensitive).
#    It is allowed but not necessary to separate with commas, e.g.: 'xx,xy,yx,yy'.   Two or four polarizations can be joinedly cleaned (see '-joinpolarizations'), but
#    this is not the default. I, Q, U and V polarizations will be directly calculated from
#    the visibilities, which might require correction to get to real IQUV values. The
#    'xy' polarization will output both a real and an imaginary image, which allows calculating
#    true Stokes polarizations for those telescopes.
if [[ -n $pol ]]; then
    export wsclean_args="${wsclean_args} -pol ${pol}"
fi

#   ** DECONVOLUTION OPTIONS **
# -niter <niter>
#    Maximum number of clean iterations to perform. Default: 0 (=no cleaning)
export niter=${niter:-10000}
if [[ -n $niter ]]; then
    export wsclean_args="${wsclean_args} -niter ${niter}"
fi
# -nmiter <nmiter>
#    Maximum number of major clean (inversion/prediction) iterations. Default: 20.   A value of 0 means no limit.
export nmiter=${nmiter:-2}
if [[ -n $nmiter ]]; then
    export wsclean_args="${wsclean_args} -nmiter ${nmiter}"
fi
# -auto-threshold <sigma>
#    Relative clean threshold. Estimate noise level using a robust estimator and stop at sigma x stddev.
export auto_threshold=${auto_threshold:-1}
if [[ -n $auto_threshold ]]; then
    export wsclean_args="${wsclean_args} -auto-threshold ${auto_threshold}"
fi
# -auto-mask <sigma>
#    Relative stopping threshold for the mask generation stage. Construct a mask from found components and when
#    the threshold is reached, continue cleaning with the mask down to the normal threshold.
export auto_mask=${auto_mask:-3}
if [[ -n $auto_mask ]]; then
    export wsclean_args="${wsclean_args} -auto-mask ${auto_mask}"
fi
# -gain <gain>
#    Cleaning gain: Ratio of peak that will be subtracted in each iteration. Default: 0.1
if [[ -n $gain ]]; then
    export wsclean_args="${wsclean_args} -gain ${gain}"
fi
# -mgain <gain>
#    Cleaning gain for major iterations: Ratio of peak that will be subtracted in each major
#    iteration. To use major iterations, 0.85 is a good value. Default: 1.0
export mgain=${mgain:-0.85}
if [[ -n $mgain ]]; then
    export wsclean_args="${wsclean_args} -mgain ${mgain}"
fi
# -multiscale
#    Clean on different scales. This is a new algorithm. Default: off.
#    This parameter invokes the optimized multiscale algorithm published by Offringa & Smirnov (2017).
# -multiscale-scale-bias
#    Parameter to prevent cleaning small scales in the large-scale iterations. A lower
#    bias will give more focus to larger scales. Default: 0.6
export mscale_bias=${mscale_bias:-0.6}
if [[ -n $mscale_bias ]]; then
    export wsclean_args="${wsclean_args} -multiscale -multiscale-scale-bias ${mscale_bias}"
fi

# -gridder <type>
#    Set gridder type: direct-ft, idg, wgridder, tuned-wgridder, or wstacking. Default: wgridder.
# -idg-mode [cpu/gpu/hybrid]
#    Sets the IDG mode. Default: cpu. Hybrid is recommended when a GPU is available.
# -grid-with-beam
#    Apply a-terms to correct for the primary beam. This is only possible when IDG is enabled.
export idg_mode="cpu"
if [[ -n "${gpus:-}" ]]; then
    export idg_mode="hybrid"
fi
export wsclean_args="${wsclean_args} -gridder idg -grid-with-beam -idg-mode ${idg_mode}"

function maybe_wsclean() {
    # first argument is the -name argument, check for existence of images
    local imgname=$1
    local image_files=$(ls ${imgname}-image-pb.fits 2>/dev/null)
    if [ -z $image_files ]; then
        wsclean \
            -make-psf \
            -save-uv \
            $wsclean_args \
            -name $@
        ls ${imgname}*
    else
        echo "found image files $image_files, skipping wsclean"
    fi
}

set -eux

# for joint deconvolution,
# export imgname=${outdir}/whiskers10697/img/whiskers10697_cal ms_list="$(find ${outdir:-.} -type d -name 'hyp_cal*_vv_*.ms')"; demo/07_img.sh
# export imgname=${outdir}/whiskers10697/img/whiskers10697_peel ms_list="$(find ${outdir:-.} -type d -name 'hyp_peel*.ms')"; demo/07_img.sh

if [[ -n "${ms_list:-}" ]]; then
    if [[ -z "$imgname" ]]; then
        echo "imgname not set, required for joint deconvolution"
        exit 1
    fi
    echo "doing joint deconvolution, imgname=$imgname ms_list=$ms_list"
    export parent=${imgname%/*}
    mkdir -p "$parent"
    maybe_wsclean "${imgname}" $ms_list
else
    export ms_list=$(eval ls -1d $ms_pattern)
    echo "imaging each ms separately, ms_list=$ms_list"
    for ms in $ms_list; do
        echo ms=$ms
        export parent=${ms%/*}
        export parent=${parent%/*}
        echo parent=$parent
        mkdir -p "$parent/img"
        export imgname=${ms%.ms}
        export imgname=wsclean_${imgname##*/}
        export imgname="${parent}/img/${imgname##*/}"
        echo imgname=$imgname
        maybe_wsclean "${imgname}" $ms
        ls ${imgname}*
    done
fi
        -mwa-path "$beam_path" \
        -temp-dir /tmp \
        $cal_ms
else
    echo "${imgname}-image-pb.fits exists, skipping wsclean"
fi
