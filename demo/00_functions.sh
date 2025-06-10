#!/bin/bash
# Common functions used across multiple demo scripts

# Function to set metafits path
set_metafits_path() {
    export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
}

# Function to set prep_uvfits and prep_uvfits_pattern variables
# Based on obsid, outdir, and optional processing parameters
set_prep_uvfits_vars() {
    # Build base path
    export prep_uvfits="${outdir}/${obsid}/prep/birli_${obsid}.uvfits"

    # Add processing parameter suffixes if they exist
    [[ -n "${timeres_s:-}" ]] && export prep_uvfits="${prep_uvfits%%.uvfits}_${timeres_s}s.uvfits"
    [[ -n "${freqres_khz:-}" ]] && export prep_uvfits="${prep_uvfits%%.uvfits}_${freqres_khz}kHz.uvfits"
    [[ -n "${edgewidth_khz:-}" ]] && export prep_uvfits="${prep_uvfits%%.uvfits}_edg${edgewidth_khz}.uvfits"

    # Create pattern for matching multiple files (when birli outputs channel suffixes)
    export prep_uvfits_pattern=${prep_uvfits%%.uvfits}\*.uvfits

    echo prep_uvfits=$prep_uvfits prep_uvfits_pattern=$prep_uvfits_pattern
}

# Function to set topn_srclist path
set_topn_srclist_path() {
    export topn_srclist=${srclist##*/}
    export topn_srclist=${topn_srclist%.*}
    export topn_srclist=$outdir/$obsid/cal/${topn_srclist}_top${num_sources}.yaml
}

# Function to set raw file pattern (consolidated to just raw_glob)
set_raw_glob() {
    export raw_glob=${outdir}/${obsid}/raw/${obsid}_2\*.fits
}

# Function to ensure metafits exists (download if not present)
ensure_metafits() {
    set_metafits_path
    if [[ ! -f "$metafits" ]]; then
        echo "metafits not present, downloading $metafits"
        mkdir -p $(dirname $metafits)
        curl -L -o "$metafits" $'http://ws.mwatelescope.org/metadata/fits?obs_id='"${obsid}"
    fi
}

# Function to check raw files are present
check_raw_files() {
    local exit_on_missing="${1:-true}"
    set_raw_glob
    if ! eval ls -1 $raw_glob >/dev/null 2>&1; then
        echo "raw not present: $raw_glob , try ${SCRIPT_BASE}/02_download.sh"
        if [[ "$exit_on_missing" == "true" ]]; then
            exit 1
        fi
    fi
}

# Function to create standard obsid directories
create_obsid_dirs() {
    local dirs="$1"
    for dir in $dirs; do
        mkdir -p "${outdir}/${obsid}/${dir}"
    done
}

# Function to safely run optional commands (skip if not found)
run_if_available() {
    local cmd="$1"
    shift
    if command -v "$cmd" >/dev/null 2>&1; then
        "$cmd" "$@"
    else
        echo "Warning: $cmd not found, skipping"
        return 1
    fi
}

# Function to set calibration file paths from prep_uvfits
set_cal_paths() {
    local prep_uvfits_file="$1"

    # Extract parent directory (remove /prep/filename, get obsid directory)
    export parent=${prep_uvfits_file%/*}
    export parent=${parent%/*}

    # Extract observation name from filename (remove birli_ prefix and .uvfits suffix)
    export dical_name=${prep_uvfits_file##*/birli_}
    export dical_name="${dical_name%.uvfits}${dical_suffix:-}"

    # Set standard calibration file paths
    export hyp_soln="${parent}/cal/hyp_soln_${dical_name}.fits"
    export cal_vis="${parent}/cal/hyp_cal_${dical_name}.ms"
    export calqa="${hyp_soln%%.fits}_qa.json"
}

# Function to setup srclist args and ensure top-N sourcelist exists
setup_srclist() {
    # Set default values if not already set
    export num_sources=${num_sources:-500}

    # Add num_sources to srclist_args if specified
    if [[ -n "${num_sources:-}" ]]; then
        srclist_args="${srclist_args} -n $num_sources"
    fi

    # Ensure the sourcelist exists
    set_topn_srclist_path
    if [[ ! -f "$topn_srclist" ]]; then
        echo "generating top $num_sources sources from $srclist with args $srclist_args"
        run_if_available hyperdrive srclist-by-beam $srclist_args -m $metafits $srclist -- $topn_srclist
    else
        echo "topn_srclist $topn_srclist exists, skipping hyperdrive srclist-by-beam"
    fi
}
