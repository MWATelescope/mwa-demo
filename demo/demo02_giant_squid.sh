#!/bin/bash

# ##### #
# HOOKS #
# ##### #
# you can overwrite these with environment variables
export obsid=${obsid:-1341914000}
export giant_squid=${giant_squid:-giant-squid}
export jq=${jq:-jq}
export outdir=${outdir:-${PWD}/demo/data/}
export SCRIPT_BASE=${SCRIPT_BASE:-${PWD}/demo/}

# ##### #
# SQUID #
# ##### #

echo "quitting before submitting jobs"
exit 0

# submit raw visibility download jobs
[ -z $MWA_ASVO_API_KEY ] && echo "don't forget to set MWA_ASVO_API_KEY" && exit 1
eval $giant_squid submit-vis obsids-cena.csv

# wait until a job is ready
eval $giant_squid wait $( eval $giant_squid list obsids-cena.csv --states queued,processing --json | jq -r '[.[]|.jobId]|join(" ")' )

# download a job
# eval $giant_squid download jobid