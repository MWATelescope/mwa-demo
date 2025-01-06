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
# check for raw files
export raw_pattern=${outdir}/${obsid}/raw/${obsid}_2\*.fits
if ! eval ls -1 $raw_pattern >/dev/null; then
    echo "raw not present: $raw_pattern , try ${SCRIPT_BASE}/02_download.sh"
    exit 1
fi
# check for metafits files
export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
if [[ ! -f "$metafits" ]]; then
    echo "metafits not present, downloading $metafits"
    curl -L -o "$metafits" $'http://ws.mwatelescope.org/metadata/fits?obs_id='${obsid}
fi

# #### #
# PREP #
# #### #
# DEMO: preprocess raw files with birli
# Cotter only works on legacy correlator files and has been discontinued.

# uncomment to modify preprocessing settings
# export freqres_khz=10     # frequency resolution to average to in kHz
# export birli_args=""      # extra birli args if any
# export timeres_s=4      # time resolution to average to in seconds
export edgewidth_khz=80 # edge width to flag on each coarse channel in kHz

mkdir -p "${outdir}/${obsid}/prep"

# Prep_uvfits is where we tell birli to write our preprocessed visibility files to.
# However, If the channels in the observation are non-contiguous, birli will output
# multiple files add a channel suffix to the output file names.
# So to test if the uvfits files exist, we need to look for a pattern.
export prep_uvfits="${outdir}/${obsid}/prep/birli_${obsid}.uvfits"
export prep_uvfits_pattern=${outdir}/${obsid}/prep/birli_${obsid}\*.uvfits

# since we don't expect the uvfits files to exist the first time around, 2>/dev/null silences the warning
if ! eval ls -1 $prep_uvfits_pattern 2>/dev/null; then
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
        -u "${prep_uvfits}" \
        $raw_pattern \
        $@
    # -M "${prep_uvfits%%.uvfits}.ms" \
else
    echo "prep_uvfits $prep_uvfits_pattern exists, skipping birli"
fi

# ####### #
# PREP QA #
# ####### #
# DEMO: use mwa_qa for quality analysis of preprocessed uvfits
# details: https://github.com/d3v-null/mwa_qa (my fork of  https://github.com/Chuneeta/mwa_qa/ )

# loop over all the preprocessed visibility files birli produced
eval ls -1 $prep_uvfits_pattern | while read -r prep_uvfits; do
    export prep_uvfits
    # obsid plus any channel suffix that birli might add.
    export obs_ch=${prep_uvfits##*/birli_}
    export obs_ch=${obs_ch%%.uvfits}

    # store prepqa relative to this uvfits
    export prepqa="${prep_uvfits%%.uvfits}_qa.json"
    if [[ ! -f "$prepqa" ]]; then
        echo "running run_prepvisqa on $prep_uvfits -> $prepqa"
        run_prepvisqa.py $prep_uvfits $metafits --out $prepqa
    else
        echo "prepqa $prepqa exists, skipping run_prepvisqa"
    fi

    # DEMO: extract bad antennas from prepqa json with jq
    prep_bad_ants=$(jq -r $'.BAD_ANTS|join(" ")' $prepqa)

    # DEMO: plot the prep qa results
    # - RMS plot: RMS of all autocorrelation values for each antenna
    plot_prepvisqa.py $prepqa --save --out ${prep_uvfits%%.uvfits}

    echo $obs_ch $prep_bad_ants
done
