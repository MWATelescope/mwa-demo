#!/bin/bash
# use mwalib to read observation metadata
# details: https://github.com/mwaTelescope/mwalib

# ### #
# ENV #
# ### #
# see: 00_env.sh
export SCRIPT_BASE=${SCRIPT_BASE:-${PWD}/demo/}
source $SCRIPT_BASE/00_env.sh

export obsid=${obsid:-1341914000} # mwax
# export obsid=1121334536 # legacy

# ###### #
# MWALIB #
# ###### #

# DEMO: raw visibility file names are different between legacy and MWAX correlator:
# - legacy: 1121334536_20150719094841_gpubox20_00.fits
# - MWAX:   1341914000_20220715095302_ch137_000.fits
# so for legacy files, it's hard to determine the sky channel from the filename.
# MWALib to the rescue!

mkdir -p ${outdir}/${obsid}/raw
export raw_glob=${raw_glob:-${outdir}/${obsid}/raw/${obsid}_2\*.fits}
if ! eval ls -1 $raw_glob; then
    echo "raw not present: $raw_glob , try ${SCRIPT_BASE}/02_download.sh"
fi

# DEMO: check for metafits, download unless present
export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
if [[ ! -f "$metafits" ]]; then
    echo "metafits not present, downloading $metafits"
    wget -O "$metafits" $'http://ws.mwatelescope.org/metadata/fits?obs_id='${obsid}
fi

# get channel and antenna info
eval $python ${SCRIPT_BASE}/03_mwalib.py $metafits

# DEMO: antenna info

# DEMO: mwalib can also be used to read raw visibility data!