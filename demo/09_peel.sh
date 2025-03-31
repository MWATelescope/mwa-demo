#!/bin/bash
# peel (specifically ionospherically subtract)
# details: https://mwatelescope.github.io/mwa_hyperdrive/user/peel/intro.html

# ### #
# ENV #
# ### #
# see: 00_env.sh
if [ -n "$ZSH_VERSION" ]; then ME="${0:A}"; else ME=$(realpath ${BASH_SOURCE:0}); fi
export SCRIPT_BASE=${SCRIPT_BASE:-$(dirname $ME)}
source "$SCRIPT_BASE/00_env.sh"

export obsid=${obsid:-UNSET}

# #### #
# PREP #
# #### #
# check for metafits files
export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
if [[ ! -f "$metafits" ]]; then
    echo "metafits not present, downloading $metafits"
    mkdir -p $(dirname $metafits)
    curl -L -o "$metafits" $'http://ws.mwatelescope.org/metadata/fits?obs_id='"${obsid}"
fi

# ####### #
# SRCLIST #
# ####### #
# DEMO: generate a smaller sourcelist for calibration
export srclist_args="${srclist_args:-}" # e.g. --veto-threshold --source-dist-cutoff
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
export dical_suffix=${dical_suffix:-""}

# check preprocessed visibility and qa files exist from previous steps
# - birli adds a channel suffix when processing observations with non-contiguous coarse channels.
# - if the files we need are missing, then run 05_prep.
# export prep_uvfits_pattern=${outdir}/${obsid}/prep/birli_${obsid}\*.uvfits
export prep_uvfits_pattern=${outdir}/${obsid}/prep/birli_${obsid}.uvfits
if ! eval ls -1 $prep_uvfits_pattern >/dev/null; then
    echo "prep_uvfits $prep_uvfits_pattern does not exist. trying 05_prep.sh"
    $SCRIPT_BASE/05_prep.sh
fi

for prep_uvfits in $prep_uvfits_pattern; do
    fitsheader $prep_uvfits | grep -i COMMENT

    export parent=${prep_uvfits%/*}
    export parent=${parent%/*}
    export dical_name=${prep_uvfits##*/birli_}
    export dical_name="${dical_name%.uvfits}${dical_suffix}"

    # ### #
    # CAL #
    # ### #

    export hyp_soln="${parent}/cal/hyp_soln_${dical_name}.fits"
    export cal_vis="${parent}/cal/hyp_cal_${dical_name}.ms"
    if ! eval ls -1 $cal_vis >/dev/null; then
        echo "warning: cal_vis $cal_vis does not exist. trying" 06_cal.sh
        $SCRIPT_BASE/06_cal.sh
    fi

    # #### #
    # PEEL #
    # #### #

    # - this is a computationally expensive step
    # - it is recommended to run this on a GPU
    # - the number of sources to use is a trade-off between accuracy and computational cost
    # - the time-average parameter is the time window over which to average the data

    export num_sources=${num_sources:-500}
    export iono_sources=${iono_sources:-50}
    export num_passes=${num_passes:-2}
    export num_loops=${num_loops:-1}
    export freq_average=${freq_average:-80kHz}
    export time_average=${time_average:-8s}
    export iono_freq_average=${iono_freq_average:-1280kHz}
    export iono_time_average=${iono_time_average:-8s}
    export short_baseline_sigma=${short_baseline_sigma:-40}
    export convergence=${convergence:-0.9}
    # recommended settings for GGSM (phase1)
    export uvw_min=${uvw_min:-75lambda}
    export uvw_max=${uvw_max:-1667lambda}

    mkdir -p "${outdir}/${obsid}/cal"
    export peel_prefix="${peel_prefix:-peel_}"
    export peel_vis="${parent}/peel/hyp_${peel_prefix}${dical_name}.ms"
    export iono_json="${parent}/peel/hyp_${peel_prefix}${dical_name}_iono.json"

    if [[ ! -f "$peel_vis" && ! -d "$peel_vis" ]]; then
        echo "ionospherically subtracting $iono_sources (total $num_sources) from sourcelist $topn_srclist"
        hyperdrive peel ${peel_args:-} \
            --data "$metafits" "$cal_vis" \
            --outputs "$peel_vis" "$iono_json" \
            --iono-sub $iono_sources \
            --num-passes $num_passes \
            --num-loops $num_loops \
            --iono-time-average $iono_time_average \
            --iono-freq-average $iono_freq_average \
            --uvw-min $uvw_min \
            --uvw-max $uvw_max \
            --short-baseline-sigma $short_baseline_sigma \
            --convergence $convergence \
            --source-list "$topn_srclist" \
            $@
    else
        echo "peel_vis $peel_vis exists, skipping hyperdrive peel"
    fi
done
