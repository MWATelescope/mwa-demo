#!/bin/bash

# ##### #
# HOOKS #
# ##### #
# you can overwrite these with environment variables
export obsid=${obsid:-1341914000}
export giant_squid=${giant_squid:-giant-squid}
export outdir=${outdir:-${PWD}/demo/data/}
export python=${python:-python}
export SCRIPT_BASE=${SCRIPT_BASE:-${PWD}/demo/}


# ##### #
# SSINS #
# ##### #
# sky-subtracted incoherent noise spectra

# check for raw files
export raw_glob=${outdir}/${obsid}/raw/${obsid}_2\*.fits
[[ -z "$(ls -1 $raw_glob 2>/dev/null)" ]] && echo "raw not present: $raw_glob" && continue
# check for metafits files
export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
[[ ! -f $metafits ]] && echo "metafits not present: $metafits" && continue
# run ssins
eval $python ${SCRIPT_BASE}/demo04_ssins.py $metafits $raw_glob