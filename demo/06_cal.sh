#!/bin/bash
# direciton independent calibrate, qa and apply solutions
# details: https://mwatelescope.github.io/mwa_hyperdrive/user/di_cal/intro.html

# ### #
# ENV #
# ### #
# see: 00_env.sh
if [ -n "$ZSH_VERSION" ]; then ME="${0:A}"; else ME=$(realpath ${BASH_SOURCE:0}); fi
export SCRIPT_BASE=${SCRIPT_BASE:-$(dirname $ME)}
source "$SCRIPT_BASE/00_env.sh"

export obsid=${obsid:-1341914000}

# #### #
# PREP #
# #### #
# check for metafits files
export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
if [[ ! -f "$metafits" ]]; then
    echo "metafits not present, downloading $metafits"
    curl -L -o "$metafits" $'http://ws.mwatelescope.org/metadata/fits?obs_id='"${obsid}"
fi

# check preprocessed visibility and qa files exist from previous steps
export prep_uvfits="${outdir}/${obsid}/prep/birli_${obsid}.uvfits"
if [ ! -f "$prep_uvfits" ]; then
    echo "prep_uvfits=$prep_uvfits does not exist. try running 05_prep.sh"
    exit 1
fi
export prepqa="${prep_uvfits%%.uvfits}_qa.json"
if [[ ! -f "$prepqa" ]]; then
    echo "warning: prepqa=$prepqa does not exist. try running 05_prep.sh"
    export prep_bad_ants=""
else
    prep_bad_ants=$(jq -r '.BAD_ANTS|join(" ")' "$prepqa")
    export prep_bad_ants
fi

# ### #
# CAL #
# ### #
# direction independent calibration with hyperdrive
mkdir -p "${outdir}/${obsid}/cal"
export hyp_soln="${outdir}/${obsid}/cal/hyp_soln_${obsid}.fits"
export cal_ms="${outdir}/${obsid}/cal/hyp_cal_${obsid}.ms"
export model_ms="${outdir}/${obsid}/cal/hyp_model_${obsid}.ms"

# DEMO: generate calibration solutions from preprocessed visibilities
# details: https://mwatelescope.github.io/mwa_hyperdrive/user/di_cal/intro.html
# (optional) add --model-filenames $model_ms to write model visibilities
# if using GPU, no need for source count limit
export dical_args="--num-sources 500 --time-average 8s"
export apply_args="--time-average 8s --freq-average 80kHz"
if [[ -n "${gpus:-}" ]]; then
    dical_args=""
fi

set -eu

if [[ ! -f "$hyp_soln" ]]; then
    eval $hyperdrive di-calibrate ${dical_args:-} \
        --data "$metafits" "$prep_uvfits" \
        --source-list "$srclist" \
        --outputs "$hyp_soln" \
        $([[ -n "${prep_bad_ants:-}" ]] && echo --tile-flags $prep_bad_ants)
fi

# plot solutions file
if [[ ! -f "${hyp_soln%%.fits}_phases.png" ]]; then
    eval $hyperdrive solutions-plot \
        -m "$metafits" \
        --no-ref-tile \
        --max-amp 1.5 \
        --output-directory "${outdir}/${obsid}/cal" \
        "$hyp_soln"
fi

# ###### #
# CAL QA #
# ###### #
# DEMO: use mwa_qa to check calibration solutions

export calqa="${hyp_soln%%.fits}_qa.json"

if [[ ! -f "$calqa" ]]; then
    eval $run_calqa --pol X --out "$calqa" "$hyp_soln" "$metafits"
fi

# plot the cal qa results
eval $plot_calqa "$calqa" --save --out "${hyp_soln%%.fits}"

# extract bad antennas from calqa json with jq
cal_bad_ants=$(eval $jq -r $'\'.BAD_ANTS|join(" ")\'' "$calqa")
export cal_bad_ants

echo "deliberately disabling cal bad ants for the first round :)"
export cal_bad_ants=""

# apply calibration solutions to preprocessed visibilities
# details: https://mwatelescope.github.io/mwa_hyperdrive/user/solutions_apply/intro.html
if [[ ! -d "$cal_ms" ]]; then
    eval $hyperdrive apply ${apply_args:-} \
        --data "$metafits" "$prep_uvfits" \
        --solutions "$hyp_soln" \
        --outputs "$cal_ms" \
        $([[ -n "${cal_bad_ants:-}" ]] && echo --tile-flags $cal_bad_ants)
fi
