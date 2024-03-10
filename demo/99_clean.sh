#!/bin/bash

export SCRIPT_BASE=${SCRIPT_BASE:-${PWD}/demo/}
source $SCRIPT_BASE/00_env.sh

find $outdir -type f ! -name '*.fits' -delete