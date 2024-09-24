#!/bin/bash
# common environment variable defaults for the demo
# - will not overwrite most environment variables

# silly hack for macOS Birli
if [[ $(uname -o) == "Darwin" ]]; then
    export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib/
fi

# base directory for demo data
# - you may want to change this do a directory with more space if extending this demo
export outdir=${outdir:-${PWD}/demo/data/}

# these variables can sometimes be set to a location inaccessible from Docker,
# so we explicitly unset them here.
unset srclist
unset MWA_BEAM_FILE
export srclist=${srclist:-${outdir}/srclist_pumav3_EoR0LoBES_EoR1pietro_CenA-GP_2023-11-07.yaml}
export MWA_BEAM_FILE=${MWA_BEAM_FILE:-${outdir}/mwa_full_embedded_element_pattern.h5}

# #### #
# BINS #
# #### #
# default values for binaries if not already set
export hyperdrive=${hyperdrive:-hyperdrive}
export wsclean=${wsclean:-wsclean}
# export casa=${casa:-casa}
export python=${python:-python}
export giant_squid=${giant_squid:-giant-squid}
export jq=${jq:-jq}
export birli=${birli:-birli}
export run_prepqa=${run_prepqa:-run_prepvisqa.py}
export plot_prepqa=${plot_prepqa:-plot_prepvisqa.py}
export run_calqa=${run_calqa:-run_calqa.py}
export plot_calqa=${plot_calqa:-plot_calqa.py}
