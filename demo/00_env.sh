#!/bin/bash
# common environment variable defaults for the demo

# overrides for Setonix
if [[ "$PAWSEY" == "setonix" ]]; then
    # set outdir to $MYSCRATCH if it's not already set.
    if [[ -n $MYSCRATCH ]]; then export outdir=${outdir:-${MYSCRATCH}}; fi
    # load the radio school modules
    export modulepath="/software/projects/pawsey1094/setonix/2024.05/modules/zen3/gcc/12.2.0"
    if [[ ! -d $modulepath ]]; then
        echo "modulepath $modulepath does not exist"
        exit 1;
    fi
    # TODO: maybe module unuse and module unload first?
    module use $modulepath
    module load hyperdrive/default birli/default giant-squid/default hyperbeam/default wsclean/2.9 mwalib/default singularity/default
    module load py-pip/default py-numpy/default
fi

# silly hack for macOS Birli
if [[ $(uname -o) == "Darwin" ]]; then
    export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib/
fi

# base directory for demo data
# - defaults to demo/data in the current working directory (^ unless Setonix)
# - you may want to change this do a directory with more space if extending this demo
export outdir=${outdir:-${PWD}/demo/data/}

# these variables can sometimes be set to a location inaccessible from Docker,
# so we explicitly unset them here.
unset srclist
unset MWA_BEAM_FILE
export srclist=${srclist:-${outdir}/srclist_pumav3_EoR0LoBES_EoR1pietro_CenA-GP_2023-11-07.yaml}
# hint: here's another sky model you can try.
# export srclist=${srclist:-${outdir}/GGSM_updated.fits}
export MWA_BEAM_FILE=${MWA_BEAM_FILE:-${outdir}/mwa_full_embedded_element_pattern.h5}


# ####### #
# SUMMARY #
# ####### #

echo "outdir:        $outdir"
echo "srclist:       $srclist"
echo "MWA_BEAM_FILE: $MWA_BEAM_FILE"