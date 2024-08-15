#!/bin/bash

export SCRIPT_BASE=${SCRIPT_BASE:-${PWD}/demo/}
source $SCRIPT_BASE/00_env.sh

find $outdir -type f ! -name '*.fits' -print -delete
find $outdir -type d -name '*.ms' -print -exec rm -rf {} \;
find $outdir -type d -name 'img' -print -exec rm -rf {} \;
find $outdir -type d -name 'cal' -print -exec rm -rf {} \;
find $outdir -type d -name 'prep' -print -exec rm -rf {} \;
