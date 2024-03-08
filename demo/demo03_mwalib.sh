#!/bin/bash

# ##### #
# HOOKS #
# ##### #
# you can overwrite these with environment variables
export obsid=${obsid:-1341914000}
export python=${python:-python}
export outdir=${outdir:-${PWD}/demo/data/}
export SCRIPT_BASE=${SCRIPT_BASE:-${PWD}/demo/}

# ###### #
# MWALIB #
# ###### #

mkdir -p ${outdir}/${obsid}/raw
# check for metafits, download unless present
export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
[ -f "$metafits" ] || wget -O "$metafits" $'http://ws.mwatelescope.org/metadata/fits?obs_id='${obsid}

# get channel and antenna info
eval $python ${SCRIPT_BASE}/demo03_mwalib.py $metafits
