#!/bin/bash

# ### #
# ENV #
# ### #
# see: 00_env.sh
if [ -n "$ZSH_VERSION" ]; then ME="${0:A}"; else ME=$(realpath ${BASH_SOURCE:0}); fi
export SCRIPT_BASE=${SCRIPT_BASE:-$(dirname $ME)}
source $SCRIPT_BASE/00_env.sh

# DEMO: get observation metadata for all obsids in the outdir
ls -1d ${outdir}/1????????? | while read -r obsid; do
    export obsid=${obsid##*/}
    if [ ! -f "${outdir}/${obsid}/meta.json" ]; then
        curl 'http://ws.mwatelescope.org/metadata/obs?extended=1&dict=1&obs_id='${obsid} >${outdir}/${obsid}/meta.json
    fi
    jq -r '[.starttime,.obsname]|@tsv' ${outdir}/${obsid}/meta.json
done | tee $outdir/obsid_obsname.tsv

# DEMO: get a manifest of all raw files
(
    cd $outdir
    ls -1 1?????????/raw/1?????????_2*.fits
) | while read -r raw; do
    export obsid=${raw%%/*}
    echo $obsid$'\t'$raw
done | tee $outdir/obsid_raw.tsv

# DEMO: record all instances of files matching a given pattern
while IFS='|' read -r glob dir; do
    export dir=${dir## }
    cd ${outdir} || exit
    mkdir -p $outdir/$dir
    eval "ls -1 $glob" | while read -r f; do
        ln -F -s $outdir/$f $outdir/$dir/${f##*/}
    done
done <<-'EoF'
??????????/img/*-image*.fits| img
EoF
