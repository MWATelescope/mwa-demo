#!/bin/bash
# common environment variable defaults for the demo

export _ENV_SOURCED=1

# overrides for Setonix
if [[ "$PAWSEY" == "setonix" ]]; then
    # set outdir to $MYSCRATCH if it's not already set.
    if [[ -n $MYSCRATCH ]]; then export outdir=${outdir:-${MYSCRATCH}}; fi
    # TODO: maybe module unuse and module unload first?
    module load hyperdrive-amd-gfx90a/default
    # module load hyperdrive/0.4.1-peel-26pcn5v # for mwaeor users
    module load birli/default giant-squid/default hyperbeam/default wsclean/default mwalib/default singularity/default
    module load py-pip/default py-numpy/default casacore/default
fi

# activate the python virtual environment if it exists (but not in Docker)
if [[ -f .venv/bin/activate && ! -f /.dockerenv ]]; then
    source .venv/bin/activate
fi

# silly hack for macOS Birli
if [[ $(uname -o) == "Darwin" ]]; then
    export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib/
fi

# basically wsclean needs this
export OPENBLAS_NUM_THREADS=1

# base directory for demo data
# - defaults to demo/data in the current working directory (^ unless Setonix)
# - you may want to change this do a directory with more space if extending this demo
export outdir=${outdir:-${PWD}/demo/data/}

# these variables can sometimes be set to a location inaccessible from Docker,
# so we explicitly unset them here.
unset srclist
unset MWA_BEAM_FILE
# export srclist=${srclist:-${outdir}/srclist_pumav3_EoR0LoBES_EoR1pietro_CenA-GP_2023-11-07.yaml}
# hint: here's another sky model you can try.
export srclist=${srclist:-${outdir}/GGSM_updated.fits}
export MWA_BEAM_FILE=${MWA_BEAM_FILE:-${outdir}/mwa_full_embedded_element_pattern.h5}

# ####### #
# SUMMARY #
# ####### #

echo "outdir:        $outdir"
echo "srclist:       $srclist"
echo "MWA_BEAM_FILE: $MWA_BEAM_FILE"
