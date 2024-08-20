#!/bin/bash
# display the commands you can use to download the observation data with giant-squid
# details https://github.com/mwaTelescope/giant-squid

# ### #
# ENV #
# ### #
# see: 00_env.sh
if [ -n "$ZSH_VERSION" ]; then ME="${0:A}"; else ME=$(realpath ${BASH_SOURCE:0}); fi
export SCRIPT_BASE=${SCRIPT_BASE:-$(dirname $ME)}
source $SCRIPT_BASE/00_env.sh

export obsids_csv=${obsids_csv:-"${outdir}/obsids.csv"}

# ##### #
# CHECK #
# ##### #

if [ ! -f "$obsids_csv" ]; then
    echo "obsids_csv=$obsids_csv does not exist. try: ${SCRIPT_BASE}/01_tap.sh" && exit 1
fi

if [ -z $MWA_ASVO_API_KEY ]; then
    echo "don't forget to set MWA_ASVO_API_KEY"
    exit 1
fi

# ##### #
# SQUID #
# ##### #

echo "you should run one of the following commands manually:"
echo " -> request raw visibilities"
echo "giant_squid submit-vis $obsids_csv"
echo " -> (or) submit preprocessed visibility conversion jobs (uvfits or ms)"
echo "giant_squid submit-conv $obsids_csv -p output=uvfits,avg_freq_res=40,avg_time_res=2,flag_edge_width=80"

echo " -> get human-readable list of jobs that are queued or processing"
echo "giant_squid list $obsids_csv"

echo " -> (advanced) get a machine readable list of jobs that are queued or processing"
echo "giant_squid list $obsids_csv --states queued,processing --json >$outdir/jobs.json"
echo "jq -r '[.[]|.jobId]|join(" ")' $outdir/jobs.json"

echo " -> wait until a job is ready"
echo "giant_squid wait $obsids_csv"

echo " -> download a job"
echo "giant_squid download jobid"
