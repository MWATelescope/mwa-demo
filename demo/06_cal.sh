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

# Cal-specific functions used only in this script
# Function to extract bad antennas from prepqa
get_prep_bad_ants() {
    local prep_uvfits_file="$1"
    local prepqa="${prep_uvfits_file%%.uvfits}_qa.json"

    if [[ -f "$prepqa" ]] && command -v jq >/dev/null 2>&1; then
        export prep_bad_ants=$(jq -r '.BAD_ANTS|join(" ")' "$prepqa")
    else
        export prep_bad_ants=""
        if [[ ! -f "$prepqa" ]]; then
            echo "Warning: prepqa file not found, skipping bad antenna extraction"
        fi
        if ! command -v jq >/dev/null 2>&1; then
            echo "Warning: jq not found, skipping bad antenna extraction"
        fi
    fi
}

# Function to plot calibration solutions
plot_cal_solutions() {
    local soln_file="$1"
    local metafits_file="$2"
    local output_dir="$3"

    if [[ ! -f "${soln_file%%.fits}_phases.png" ]]; then
        # Plot without reference tile
        run_if_available hyperdrive solutions-plot \
            -m "$metafits_file" \
            --no-ref-tile \
            --max-amp 1.5 \
            --output-directory "$output_dir" \
            "$soln_file"

        # Rename files to indicate no reference tile
        [[ -f "${soln_file%%.fits}_phases.png" ]] && mv "${soln_file%%.fits}_phases.png" "${soln_file%%.fits}_phases_noref.png"
        [[ -f "${soln_file%%.fits}_amps.png" ]] && mv "${soln_file%%.fits}_amps.png" "${soln_file%%.fits}_amps_noref.png"

        # Plot with reference tile
        run_if_available hyperdrive solutions-plot \
            -m "$metafits_file" \
            --max-amp 1.5 \
            --ref-tile 0 \
            --output-directory "$output_dir" \
            "$soln_file"
    else
        echo "phases_png ${soln_file%%.fits}_phases.png exists, skipping hyperdrive solutions-plot"
    fi
}

# Function to run calibration QA and extract bad antennas
run_cal_qa() {
    local hyp_soln="$1"
    local metafits="$2"
    local calqa="$3"

    # Run calqa if not exists
    if [[ ! -f "$calqa" ]]; then
        echo "running calqa on solutions $hyp_soln"
        run_if_available run_calqa.py --pol X --out "$calqa" "$hyp_soln" "$metafits"
    else
        echo "calqa $calqa exists, skipping run_calqa.py"
    fi

    # Process QA results if file exists
    if [[ -f "$calqa" ]]; then
        # Plot the cal qa results
        run_if_available plot_calqa.py "$calqa" --save --out "${hyp_soln%%.fits}"

        # Extract convergence percentage and check quality
        if command -v jq >/dev/null 2>&1; then
            cal_pct_nonconvg=$(jq -r '.PERCENT_NONCONVERGED_CHS|tonumber|round' "$calqa" 2>/dev/null) || cal_pct_nonconvg=""
            export cal_pct_nonconvg

            if [[ -n "$cal_pct_nonconvg" && $cal_pct_nonconvg -ge 95 ]]; then
                echo "calibration failed, $cal_pct_nonconvg% of channels did not converge. hint: try a different sky model in demo/00_env.sh"
                return 1 # Signal failure
            fi

            # Extract bad antennas from calqa json
            cal_bad_ants=$(jq -r '.BAD_ANTS|join(" ")' "$calqa" 2>/dev/null) || cal_bad_ants=""
            export cal_bad_ants
        else
            export cal_pct_nonconvg=""
            export cal_bad_ants=""
        fi
    else
        export cal_pct_nonconvg=""
        export cal_bad_ants=""
    fi

    return 0 # Success
}

# ### #
# RAW #
# ### #
# check for raw files
# export raw_pattern=${outdir}/${obsid}/raw/${obsid}_2\*.fits
# check for metafits files
ensure_metafits

# check preprocessed visibility and qa files exist from previous steps
# - birli adds a channel suffix when processing observations with non-contiguous coarse channels.
# - if the files we need are missing, then run 05_prep.sh
set_prep_uvfits_vars

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

create_obsid_dirs "cal"

# ####### #
# SRCLIST #
# ####### #
# DEMO: generate a smaller sourcelist for calibration
export srclist_args="${srclist_args:---source-dist-cutoff=180}" # e.g. --veto-threshold --source-dist-cutoff
setup_srclist

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

    # find prepqa relative to this uvfits file and extract bad antennas
    get_prep_bad_ants "$prep_uvfits"

    # store calibration outputs for the prepqa file in the sibling cal/ folder
    # e.g. for prep_uvfits=a/b/prep/birli_X_chY.uvfits, parent=a/b, obs=X_chY
    set_cal_paths "$prep_uvfits"
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
    plot_cal_solutions "$hyp_soln" "$metafits" "${outdir}/${obsid}/cal"

    # ###### #
    # CAL QA #
    # ###### #
    # DEMO: use mwa_qa to check calibration solutions
    if ! run_cal_qa "$hyp_soln" "$metafits" "$calqa"; then
        continue # Skip to next file if calibration failed
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
