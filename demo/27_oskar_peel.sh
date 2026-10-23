#!/bin/bash
# peel an OSKAR simulation with hyperdrive, then measure how much sky it removed
# details: https://mwatelescope.github.io/mwa_hyperdrive/user/peel/intro.html
# expects the MS to be derotated already (24_oskar_derotate.py): hyperdrive
# assumes every tile has the same feed orientation, AA2 stations are rotated.
# needs a hyperdrive with the DP3 sky-model reader and OSKAR conventions
# (mwa_hyperdrive >= 0.8, branch feat/conventions); see WORKSHOP_06.md.
# runs inside the mwa-demo container.

# ### #
# ENV #
# ### #
# see: 00_env.sh
if [ -n "$ZSH_VERSION" ]; then ME="${0:A}"; else ME=$(realpath "${BASH_SOURCE:0}"); fi
export SCRIPT_BASE=${SCRIPT_BASE:-$(dirname "$ME")}
source "$SCRIPT_BASE/00_env.sh"

export oskar_dir=${oskar_dir:-${outdir}/oskar}
export config=${config:-aa2}
export duration_s=${duration_s:-120}
export sim_name=${sim_name:-${config}_${duration_s}s}
export ms=${ms:-${oskar_dir}/vis/${sim_name}.ms}
export hyperdrive=${hyperdrive:-hyperdrive}
export peel_dir=${peel_dir:-${oskar_dir}/peel}
# subtract the sources of the apparent model (25_oskar_apparent.py keeps the
# 500 apparently brightest; set num_sources to use fewer), ionospherically peel
# the brightest iono_sources of those (solving a position shift and gain each)
export num_sources=${num_sources:-}
export iono_sources=${iono_sources:-50}
export num_passes=${num_passes:-2}
export num_loops=${num_loops:-4}
export iono_time_average=${iono_time_average:-8s}
export iono_freq_average=${iono_freq_average:-1248kHz}
export uvw_min=${uvw_min:-20lambda}
export uvw_max=${uvw_max:-100000lambda}
export short_baseline_sigma=${short_baseline_sigma:-40}
export convergence=${convergence:-0.9}

set -eux
mkdir -p "$peel_dir"

# hyperdrive models every tile with the same beam, so case (h) is peeled as
# its two sub-arrays (their cross-baselines are flagged, so nothing is lost):
# part name, first and last station
case $config in
    aa2) default_parts="aa2:0:67" ;;
    mwa256t) default_parts="mwa256t:0:255" ;;
    aa2_mwa256t) default_parts="aa2:0:67 mwa256t:68:323" ;;
    *) echo "unknown config $config"; exit 1 ;;
esac
# set parts to peel only some of them, e.g. parts=aa2:0:67
export parts=${parts:-$default_parts}

for part in $parts; do
    IFS=: read -r name first last <<<"$part"
    base="${peel_dir}/${sim_name}_${name}"
    part_ms="$ms"
    if [[ "$config" == "aa2_mwa256t" ]]; then
        part_ms="${base}.ms"
        [[ -d "$part_ms" ]] || python "$SCRIPT_BASE/23_oskar_split.py" "$ms" "$part_ms" --first "$first" --last "$last"
    fi
    # apparent sky model from OSKAR's own station beam (25_oskar_apparent.py,
    # in the OSKAR container); case (h) needs one per sub-array
    app="${oskar_dir}/sky/${sim_name}_app.skymodel"
    [[ "$config" == "aa2_mwa256t" ]] && app="${oskar_dir}/sky/${sim_name}_${name}_app.skymodel"
    if [[ ! -f "$app" ]]; then
        echo "apparent sky model $app missing, run 25_oskar_apparent.py"
        exit 1
    fi
    peeled="${base}_hyp_peel.ms"
    if [[ ! -d "$peeled" ]]; then
        SECONDS=0
        # shellcheck disable=SC2086 # peel_args is a word list
        $hyperdrive peel ${peel_args:-} \
            --data "$part_ms" \
            --source-list "$app" \
            --source-list-type dp3 \
            --no-beam \
            ${num_sources:+--num-sources "$num_sources"} \
            --iono-sub "$iono_sources" \
            --num-passes "$num_passes" \
            --num-loops "$num_loops" \
            --iono-time-average "$iono_time_average" \
            --iono-freq-average "$iono_freq_average" \
            --uvw-min "$uvw_min" \
            --uvw-max "$uvw_max" \
            --short-baseline-sigma "$short_baseline_sigma" \
            --convergence "$convergence" \
            --outputs "$peeled" "${base}_hyp_iono.json"
        echo "hyperdrive peel took ${SECONDS} s" | tee "${base}_hyp_peel.time"
        # hyperdrive 0.8.1 flags all but 4 channels of its output here
        python "$SCRIPT_BASE/27_oskar_restore_flags.py" "$part_ms" "$peeled"
    fi
    python "$SCRIPT_BASE/29_oskar_peel_metrics.py" \
        --input "$part_ms" --residual "$peeled" \
        --label "${sim_name} hyperdrive [${name}]" --json "${base}_hyp_metrics.json"
done
