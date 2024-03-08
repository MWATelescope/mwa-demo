#!/bin/bash

# ##### #
# HOOKS #
# ##### #
export obsid=${obsid:-1341914000}
export outdir=${outdir:-${PWD}/demo/data/}
export srclist=${srclist:-srclist_pumav3_EoR0LoBES_EoR1pietro_CenA-GP_2023-11-07.yaml}
export MWA_BEAM_FILE=${MWA_BEAM_FILE:-mwa_full_embedded_element_pattern.h5}
export hyperdrive=${hyperdrive:-hyperdrive}
export wsclean=${wsclean:-wsclean}
export birli=${birli:-birli}
export run_prepqa=${run_prepqa:-run_prepvisqa.py}
export run_calqa=${run_calqa:-run_calqa.py}
export SCRIPT_BASE=${SCRIPT_BASE:-${PWD}/demo/}


## Preprocessing settings
# export timeres_s=1      # (optional) time resolution to average to in seconds
# export freqres_khz=10   # (optional) frequency resolution to average to in kHz
export edgewidth_khz=80   # edge width to flag on each coarse channel in kHz
export birli_args=""      # extra birli args if any
export prep_name="_${timeres_s}s_${freqres_khz}kHz"
set -e

# ##### #
# CHECK #
# ##### #

export raw_glob=${outdir}/${obsid}/raw/${obsid}_2\*.fits
[[ -z "$(ls -1 $raw_glob 2>/dev/null)" ]] && echo "raw not present: $raw_glob" && continue
# check for metafits files
export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
[[ ! -f $metafits ]] && echo "metafits not present: $metafits" && continue

# #### #
# PREP #
# #### #
# preprocess raw files with birli
mkdir -p ${outdir}/${obsid}/prep
export prep_uvfits="${outdir}/${obsid}/prep/birli_${obsid}.uvfits"
export prepqa="${prep_uvfits%%.uvfits}_qa.json"

[ -f $prep_uvfits ] || eval $birli \
    -m "${metafits}" \
    --flag-edge-width ${edgewidth_khz} \
    $( [[ -n "${freqres_khz:-}" ]] && echo "--avg-freq-res ${freqres_khz}" ) \
    $( [[ -n "${timeres_s:-}" ]] && echo "--avg-time-res ${timeres_s}" ) \
    -u "${prep_uvfits}" \
    $raw_glob

[ -f "$prepqa" ] \
    || eval $run_prepqa $prep_uvfits $metafits --out $prepqa

export bad_ants=$(jq -r '.BAD_ANTS|join(" ")' $prepqa)

echo $obsid $bad_ants


# ### #
# CAL #
# ### #
mkdir -p ${outdir}/${obsid}/cal
export hyp_soln="${outdir}/${obsid}/cal/hyp_soln_${obsid}.fits"
export cal_ms="${outdir}/${obsid}/cal/hyp_cal_${obsid}.ms"
export model_ms="${outdir}/${obsid}/cal/hyp_model_${obsid}.ms"

[ -f "$hyp_soln" ] || eval $hyperdrive di-calibrate \
    --data $metafits $prep_uvfits \
    --source-list $srclist \
    --outputs $hyp_soln \
    $( [[ -n "$bad_ants" ]] && echo --tile-flags $bad_ants )

[ -f "${hyp_soln%%.fits}_phases.png" ] || eval $hyperdrive solutions-plot \
    -m $metafits \
    --no-ref-tile \
    --output-directory ${outdir}/${obsid}/cal \
    $hyp_soln

[ -d "$cal_ms" ] || eval $hyperdrive apply \
    --data $metafits $raw_glob \
    --solutions $hyp_soln \
    --outputs $cal_ms

# ### #
# IMG #
# ### #
mkdir -p ${outdir}/${obsid}/img

# wsclean needs to know the directory of the beam file
export beam_path="${MWA_BEAM_FILE%/*}"
[[ $beam_path =~ / ]] || export beam_path="${PWD}"

eval $wsclean \
    -name ${outdir}/${obsid}/img/wsclean_hyp_${obsid} \
    -size 2048 2048 \
    -scale 20asec \
    -pol i \
    -niter 100 \
    -gridder idg -grid-with-beam -idg-mode hybrid \
    -multiscale \
    -weight briggs 0 \
    -mgain 0.85 -gain 0.1 \
    -auto-threshold 1 -auto-mask 3 \
    -no-update-model-required \
    -make-psf \
    -small-inversion \
    -mwa-path $beam_path \
    $cal_ms
