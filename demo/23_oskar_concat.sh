#!/bin/bash
# join sub-band measurement sets from 23_oskar_sim.sh along frequency with DP3
# runs in the rapthor container (DP3), e.g.
#   docker run --rm --user $(id -u):$(id -g) -v $PWD:$PWD -w $PWD \
#     ghcr.io/d3v-null/rapthor-mwa:sha-e27456d-pass demo/23_oskar_concat.sh out.ms in_ch0+208.ms in_ch208+208.ms

set -euo pipefail
if [[ $# -lt 3 ]]; then
    echo "usage: $0 out.ms in1.ms in2.ms [...] (inputs in frequency order)"
    exit 1
fi
out=$1
shift
inputs=$(IFS=,; echo "$*")
export OPENBLAS_NUM_THREADS=1
rm -rf "$out"
# keep OSKAR's UVWs as they are (DP3's default UvwStMan re-derives them), and
# plain ANTENNA1/2 and FLAG columns (older casacore, e.g. in mwa-demo, cannot
# read DP3 6.6's AntennaPairStMan or StokesIStMan)
DP3 msin="[$inputs]" msout="$out" msout.uvwcompression=false msout.antennacompression=false msout.scalarflags=false steps=[]
du -sh "$out"
