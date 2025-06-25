#!/bin/bash
# use Birli to preprocess raw files
# details: https://github.com/MWATelescope/Birli/

# ### #
# ENV #
# ### #
# see: 00_env.sh
if [ -n "$ZSH_VERSION" ]; then ME="${0:A}"; else ME=$(realpath ${BASH_SOURCE:0}); fi
export SCRIPT_BASE=${SCRIPT_BASE:-$(dirname $ME)}
source "$SCRIPT_BASE/00_env.sh"

export obsid=${obsid:-1341914000}

# ### #
# RAW #
# ### #
# pattern to check for raw files
export raw_pattern=${outdir}/${obsid}/raw/${obsid}_2\*.fits
# check for metafits files
# use _fixed if available
export metafits=${outdir}/${obsid}/raw/${obsid}_fixed.metafits
if [[ ! -f "$metafits" ]]; then
    # otherwise use the original
    export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
fi
if [[ ! -f "$metafits" ]]; then
    # otherwise download it
    echo "metafits not present, downloading $metafits"
    curl -L -o "$metafits" $'http://ws.mwatelescope.org/metadata/fits?obs_id='${obsid}
fi

# #### #
# PREP #
# #### #
# DEMO: preprocess raw files with birli
# Cotter only works on legacy correlator files and has been discontinued.

# optional preprocessing settings for 00_env.sh
# export freqres_khz=10   # frequency resolution to average to in kHz
# export birli_args=""    # extra birli args if any
# export timeres_s=4      # time resolution to average to in seconds
export edgewidth_khz=${edgewidth_khz:-80} # edge width to flag on each coarse channel in kHz

mkdir -p "${outdir}/${obsid}/prep"

# prep_vis is where we tell birli to write our preprocessed visibility files to.
# However, If the channels in the observation are non-contiguous, birli will output
# multiple files add a channel suffix to the output file names.
# So to test if the uvfits files exist, we need to look for a pattern.
export prep_vis_fmt=${prep_vis_fmt:-uvfits}
export prep_vis="${outdir}/${obsid}/prep/birli_${obsid}"
[[ -n "${timeres_s:-}" ]] && export prep_vis="${prep_vis}_${timeres_s}s"
[[ -n "${freqres_khz:-}" ]] && export prep_vis="${prep_vis}_${freqres_khz}kHz"
[[ -n "${edgewidth_khz:-}" ]] && export prep_vis="${prep_vis}_edg${edgewidth_khz}"
export prep_vis_pattern=${prep_vis}\*.${prep_vis_fmt}
export prep_vis=${prep_vis}.${prep_vis_fmt}
echo prep_vis=$prep_vis prep_vis_pattern=$prep_vis_pattern

# since we don't expect the uvfits files to exist the first time around,
# >/dev/null silences the warning
if ! eval ls -1 $prep_vis_pattern >/dev/null; then
    if ! eval ls -1 $raw_pattern >/dev/null; then
        echo "raw not present: $raw_pattern , try ${SCRIPT_BASE}/02_download.sh"
        exit 1
    fi
    echo "running birli on $raw_pattern" \
        $([[ -n "${edgewidth_khz:-}" ]] && echo " edge width ${edgewidth_khz}kHz") \
        $([[ -n "${freqres_khz:-}" ]] && echo " freq res ${freqres_khz}kHz") \
        $([[ -n "${timeres_s:-}" ]] && echo " time res ${timeres_s}s") \
        ;
    birli ${birli_args:-} \
        -m "${metafits}" \
        $([[ -n "${edgewidth_khz:-}" ]] && echo "--flag-edge-width ${edgewidth_khz}") \
        $([[ -n "${freqres_khz:-}" ]] && echo "--avg-freq-res ${freqres_khz}") \
        $([[ -n "${timeres_s:-}" ]] && echo "--avg-time-res ${timeres_s}") \
        $([[ "${prep_vis_fmt}" == "ms" ]] && echo "-M ${prep_vis}" || echo "-u ${prep_vis}") \
        $raw_pattern \
        $@
    export birli_return=$?
    echo return code $birli_return
else
    echo "prep_vis $prep_vis_pattern exists, skipping birli"
fi

# ####### #
# PREP QA #
# ####### #
# DEMO: use mwa_qa for quality analysis of preprocessed uvfits
# details: https://github.com/d3v-null/mwa_qa (my fork of  https://github.com/Chuneeta/mwa_qa/ )

# this only works for uvfits files
if [[ "$prep_vis_fmt" == "uvfits" ]]; then

    # loop over all the preprocessed visibility files birli produced
    eval ls -1 $prep_vis_pattern | while read -r prep_vis; do
        # the current uvfits file we're looking at
        export prep_vis
        # obsid plus any channel suffix that birli might add.
        export obs_ch=${prep_vis##*/birli_}
        export obs_ch=${obs_ch%%.${prep_vis_fmt}}

        # store prepqa relative to this uvfits
        export prepqa="${prep_vis%%.${prep_vis_fmt}}_qa.json"
        if [[ ! -f "$prepqa" ]]; then
            echo "running run_prepvisqa on $prep_vis -> $prepqa"
            run_prepvisqa.py --split $prep_vis $metafits --out $prepqa
        else
            echo "prepqa $prepqa exists, skipping run_prepvisqa"
        fi

        # DEMO: extract bad antennas from prepqa json with jq
        prep_bad_ants=$(jq -r $'.BAD_ANTS|join(" ")' $prepqa)

        # DEMO: plot the prep qa results
        # - RMS plot: RMS of all autocorrelation values for each antenna
        plot_prepvisqa.py $prepqa --save --out ${prep_vis%%.uvfits}

        echo $obs_ch $prep_bad_ants
    done
fi
