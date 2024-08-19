#!/bin/bash

if [ -n "$ZSH_VERSION" ]; then ME="${0:A}"; else ME=$(realpath ${BASH_SOURCE:0}); fi
export SCRIPT_BASE=${SCRIPT_BASE:-$(dirname $ME)}
source $SCRIPT_BASE/00_env.sh

find $outdir -type f ! -name '*.fits' -print -delete
find $outdir -type d -name '*.ms' -print -exec rm -rf {} \;
find $outdir -type d -name 'img' -print -exec rm -rf {} \;
find $outdir -type d -name 'cal' -print -exec rm -rf {} \;
find $outdir -type d -name 'prep' -print -exec rm -rf {} \;
