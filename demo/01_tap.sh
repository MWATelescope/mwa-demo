#!/bin/bash
# query the MWA TAP server with ADQL using the pyvo library

# ### #
# ENV #
# ### #
# see: 00_env.sh
if [ -n "$ZSH_VERSION" ]; then ME="${0:A}"; else ME=$(realpath ${BASH_SOURCE:0}); fi
export SCRIPT_BASE=${SCRIPT_BASE:-$(dirname $ME)}
source $SCRIPT_BASE/00_env.sh

export obsids_csv=${obsids_csv:-"${outdir}/obsids.csv"}
export details_csv=${details_csv:-"${outdir}/details.csv"}

# ### #
# TAP #
# ### #
# query the MWA TAP server with ADQL using the pyvo library
# details: https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/24970532/MWA+ASVO+VO+Services
eval $python $SCRIPT_BASE/01_tap.py $obsids_csv $details_csv
