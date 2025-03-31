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

# ### #
# RAW #
# ### #
# check for raw files
# export raw_pattern=${outdir}/${obsid}/raw/${obsid}_2\*.fits
# check for metafits files
export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
if [[ ! -f "$metafits" ]]; then
    echo "metafits not present, downloading $metafits"
    mkdir -p $(dirname $metafits)
    curl -L -o "$metafits" $'http://ws.mwatelescope.org/metadata/fits?obs_id='"${obsid}"
fi

# check preprocessed visibility and qa files exist from previous steps
# - birli adds a channel suffix when processing observations with non-contiguous coarse channels.
# - if the files we need are missing, then run 05_prep.sh
export prep_uvfits="${outdir}/${obsid}/prep/birli_${obsid}.uvfits"
[[ -n "${timeres_s:-}" ]] && export prep_uvfits="${prep_uvfits%%.uvfits}_${timeres_s}s.uvfits"
[[ -n "${freqres_khz:-}" ]] && export prep_uvfits="${prep_uvfits%%.uvfits}_${freqres_khz}kHz.uvfits"
[[ -n "${edgewidth_khz:-}" ]] && export prep_uvfits="${prep_uvfits%%.uvfits}_edg${edgewidth_khz}.uvfits"
export prep_uvfits_pattern=${prep_uvfits%%.uvfits}\*.uvfits

for f in $(ls -1d $prep_uvfits_pattern); do
    set -x
    fitsheader $f | grep "ERROR"
    echo $?
    # TODO: detect fitsheader ERROR
done
if ! eval ls -1d $prep_uvfits_pattern >/dev/null; then
    echo "prep_uvfits $prep_uvfits_pattern does not exist. trying 05_prep.sh"
    $SCRIPT_BASE/05_prep.sh
fi
export prep_qa_pattern="${outdir}/${obsid}/prep/birli_${obsid}*_qa.json"
if ! eval ls -1d $prep_qa_pattern >/dev/null; then
    echo "warning: prepqa $prep_qa_pattern does not exist. trying 05_prep.sh"
    $SCRIPT_BASE/05_prep.sh
fi

mkdir -p "${outdir}/${obsid}/cal"

# ####### #
# SRCLIST #
# ####### #
# DEMO: generate a smaller sourcelist for calibration
export srclist_args="${srclist_args:---source-dist-cutoff=180}" # e.g. --veto-threshold --source-dist-cutoff
export num_sources=${num_sources:-500}
if [[ -n "${num_sources:-}" ]]; then
    srclist_args="${srclist_args} -n $num_sources"
fi
export topn_srclist=${srclist##*/}
export topn_srclist=${topn_srclist%.*}
export topn_srclist=$outdir/$obsid/cal/${topn_srclist}_top${num_sources}.yaml
if [[ ! -f "$topn_srclist" ]]; then
    echo "generating top $num_sources sources from $srclist with args $srclist_args"
    hyperdrive srclist-by-beam $srclist_args -m $metafits $srclist -- $topn_srclist
else
    echo "topn_srclist $topn_srclist exists, skipping hyperdrive srclist-by-beam"
fi

# ### #
# CAL #
# ### #
# direction independent calibration with hyperdrive

# DEMO: generate calibration solutions from preprocessed visibilities
# details: https://mwatelescope.github.io/mwa_hyperdrive/user/di_cal/intro.html
# (optional) add --model-filenames $model_ms to write model visibilities
# if using GPU, no need for source count limit
export dical_args="${dical_args:-}" # e.g. --uvw-min 30 --max-iterations 300
export apply_args="${apply_args:-}" # e.g. --time-average 8s --freq-average 80kHz
export dical_suffix=${dical_suffix:-""}
if [[ -n "${gpus:-}" ]]; then
    dical_args=""
fi

set -eu
# loop over all the preprocessed files
eval ls -1d $prep_uvfits_pattern | while read -r prep_uvfits; do
    export prep_uvfits

    # find prepqa relative to this uvfits file
    export prepqa="${prep_uvfits%%.uvfits}_qa.json"
    if [[ -f "$prepqa" ]]; then
        prep_bad_ants=$(jq -r '.BAD_ANTS|join(" ")' "$prepqa")
        export prep_bad_ants
    else
        export prep_bad_ants=""
    fi

    # store calibration outputs for the prepqa file in the sibling cal/ folder
    # e.g. for prep_uvfits=a/b/prep/birli_X_chY.uvfits, parent=a/b, obs=X_chY
    export parent=${prep_uvfits%/*}
    export parent=${parent%/*}
    export dical_name=${prep_uvfits##*/birli_}
    export dical_name="${dical_name%.uvfits}${dical_suffix}"
    export hyp_soln="${parent}/cal/hyp_soln_${dical_name}.fits"
    export cal_vis="${parent}/cal/hyp_cal_${dical_name}.ms"
    # export model_ms="${parent}/cal/hyp_model_${dical_name}.ms"

    if [[ ! -f "$hyp_soln" ]]; then
        echo "calibrating with sourcelist $topn_srclist"
        hyperdrive di-calibrate ${dical_args:-} ${srclist_args:-} \
            --data "$metafits" "$prep_uvfits" \
            --source-list "$topn_srclist" \
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
        mv ${hyp_soln%%.fits}_phases.png ${hyp_soln%%.fits}_phases_noref.png
        mv ${hyp_soln%%.fits}_amps.png ${hyp_soln%%.fits}_amps_noref.png
        hyperdrive solutions-plot \
            -m "$metafits" \
            --max-amp 1.5 \
            --ref-tile 0 \
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
        run_calqa.py --pol X --out "$calqa" "$hyp_soln" "$metafits" || true
    else
        echo "calqa $calqa exists, skipping run_calqa.py"
    fi

    # if the above didn't fail
    if [[ -f "$calqa" ]]; then
        # plot the cal qa results
        plot_calqa.py "$calqa" --save --out "${hyp_soln%%.fits}" || true

        # extract the percentage of channels that converged
        cal_pct_nonconvg=$(jq -r $'.PERCENT_NONCONVERGED_CHS|tonumber|round' "$calqa") || true
        export cal_pct_nonconvg

        if [[ $cal_pct_nonconvg -ge 95 ]]; then
            echo "calibration failed, $cal_pct_nonconvg% of channels did not converge. hint: try a different sky model in demo/00_env.sh"
            continue
        fi

        # extract bad antennas from calqa json with jq
        cal_bad_ants=$(jq -r $'.BAD_ANTS|join(" ")' "$calqa") || true
        export cal_bad_ants
    fi

    # echo "deliberately disabling cal bad ants for the first round :)"
    # export cal_bad_ants=""

    # apply calibration solutions to preprocessed visibilities
    # details: https://mwatelescope.github.io/mwa_hyperdrive/user/solutions_apply/intro.html
    if [[ -n "$cal_vis" && ! -f "$cal_vis" && ! -d "$cal_vis" ]]; then
        hyperdrive apply ${apply_args:-} \
            --data "$metafits" "$prep_uvfits" \
            --solutions "$hyp_soln" \
            --outputs "$cal_vis" \
            $([[ -n "${cal_bad_ants:-}" ]] && echo --tile-flags $cal_bad_ants)
    else
        echo "cal_vis $cal_vis exists, skipping hyperdrive apply"
    fi
done

# TODO phase fits, for now you need to singularity exec -B$PWD -B${outdir:-$PWD} -W$PWD --cleanenv docker://mwatelescope/mwa-demo:latest /bin/bash
cat <<EOF
# this will only work in the contaier :(
python /mwax_mover/scripts/cal_analysis.py \
    --name "${obsid}" \
    --metafits "${metafits}" --solns ${outdir}/${obsid}/cal/hyp_soln_${obsid}*.fits \
    --plot-residual --residual-vmax=0.5
EOF
