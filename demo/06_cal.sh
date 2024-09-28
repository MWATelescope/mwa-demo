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
    echo "prep_uvfits=$prep_uvfits does not exist. trying 05_prep.sh"
    $SCRIPT_BASE/05_prep.sh
fi
export prepqa="${prep_uvfits%%.uvfits}_qa.json"
if [[ ! -f "$prepqa" ]]; then
    echo "warning: prepqa=$prepqa does not exist. trying 05_prep.sh"
    $SCRIPT_BASE/05_prep.sh
fi
if [[ -f "$prepqa" ]]; then
    prep_bad_ants=$(jq -r '.BAD_ANTS|join(" ")' "$prepqa")
    export prep_bad_ants
else
    export prep_bad_ants=""
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
    echo "calibrating with sourcelist $srclist"
    hyperdrive di-calibrate ${dical_args:-} \
        --data "$metafits" "$prep_uvfits" \
        --source-list "$srclist" \
        --outputs "$hyp_soln" \
        $([[ -n "${prep_bad_ants:-}" ]] && echo --tile-flags $prep_bad_ants)
else
    echo "hyp_soln $hyp_soln exists, skipping hyperdrive di-calibrate"
fi

# plot solutions file
if [[ ! -f "${hyp_soln%%.fits}_phases.png" ]]; then
    hyperdrive solutions-plot \
        -m "$metafits" \
        --no-ref-tile \
        --max-amp 1.5 \
        --output-directory "${outdir}/${obsid}/cal" \
        "$hyp_soln"
else
    echo "phases_png ${hyp_soln%%.fits}_phases.png exists, skipping hyperdrive solutions-plot"
fi

# ###### #
# CAL QA #
# ###### #
# DEMO: use mwa_qa to check calibration solutions

export calqa="${hyp_soln%%.fits}_qa.json"

if [[ ! -f "$calqa" ]]; then
    echo "running calqa on solutions $hyp_soln"
    run_calqa.py --pol X --out "$calqa" "$hyp_soln" "$metafits"
else
    echo "calqa $calqa exists, skipping run_calqa.py"
fi

# plot the cal qa results
plot_calqa.py "$calqa" --save --out "${hyp_soln%%.fits}"

# extract the percentage of channels that converged
cal_pct_nonconvg=$(jq -r $'.PERCENT_NONCONVERGED_CHS|tonumber|round' "$calqa")
export cal_pct_nonconvg

if [[ $cal_pct_nonconvg -ge 95 ]]; then
    echo "calibration failed, $cal_pct_nonconvg% of channels did not converge. hint: try a different sky model in demo/00_env.sh"
    exit 1
fi

# extract bad antennas from calqa json with jq
cal_bad_ants=$(jq -r $'.BAD_ANTS|join(" ")' "$calqa")
export cal_bad_ants

echo "deliberately disabling cal bad ants for the first round :)"
export cal_bad_ants=""

# apply calibration solutions to preprocessed visibilities
# details: https://mwatelescope.github.io/mwa_hyperdrive/user/solutions_apply/intro.html
if [[ ! -d "$cal_ms" ]]; then
    hyperdrive apply ${apply_args:-} \
        --data "$metafits" "$prep_uvfits" \
        --solutions "$hyp_soln" \
        --outputs "$cal_ms" \
        $([[ -n "${cal_bad_ants:-}" ]] && echo --tile-flags $cal_bad_ants)
else
    echo "cal_ms $cal_ms exists, skipping hyperdrive apply"
fi
