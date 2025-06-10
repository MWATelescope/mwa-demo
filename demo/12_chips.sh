#!/bin/bash

# ### #
# ENV #
# ### #
# see: 00_env.sh
if [ -n "$ZSH_VERSION" ]; then ME="${0:A}"; else ME=$(realpath ${BASH_SOURCE:0}); fi
export SCRIPT_BASE=${SCRIPT_BASE:-$(dirname $ME)}
source "$SCRIPT_BASE/00_env.sh"

export obsid=${obsid:-1069761080}

# ### #
# CAL #
# ### #

export dical_suffix=${dical_suffix:-""}
# check for calibrated measurement set from previous step
export uvf_pattern=${uvf_pattern:-${outdir}/${obsid}/\{cal,peel\}/hyp_\*${obsid}\*${dical_suffix}\*.uvfits}
if ! eval ls -1d $uvf_pattern >/dev/null; then
    echo "uvf_pattern=$uvf_pattern does not exist. try 06_cal.sh"
fi
echo uvf_pattern=$uvf_pattern

# ##### #
# CHIPS #
# ##### #
# details: https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/24972433/Running+CHIPS
# there are 4 binaries:
# - gridvisdiff - grid MWA visibilities
# - prepare_diff - combine data over frequency
# - combine_data - combine data over multiple gridded sets
# - lssa_fg_simple - compute the LS spectral power (no kriging)

export eorband=0         # EOR band = 0 (low, 139-170MHz), 1 (high, 167-198MHz)
export eorfield=1        # EOR field = 0, 1, 2, 3
export nchan=384         # number of channels in the file
export period=8.0        # integration time in seconds
export nbins=80          # number of k bins
export maxu=300          # maximum u value
export chanwidth=80000   # channel width in Hz
export lowfreq=167035000 # first frequency in the data in Hz
export bias_mode=0       # bias mode = 0/10/11/12 e.g. 0
export pols="xx yy"      # list of polarizations to process

OMP_NUM_THREADS=$(nproc)
export OMP_NUM_THREADS

if [ $bias_mode -eq 0 ]; then
    export nchan_out=$nchan start_chan=0
elif [ $bias_mode -eq 10 ]; then
    export nchan_out=$(($nchan / 2)) start_chan=$(($nchan / 2))
elif [ $bias_mode -eq 12 ]; then
    export nchan_out=$(($nchan / 2)) start_chan=$(($nchan / 4))
elif [ $bias_mode -eq 13 ]; then
    export nchan_out=$(($nchan / 2)) start_chan=$(($nchan / 8))
else
    echo "unknown bias_mode ${bias_mode}"
fi

uvf_list=$(eval ls -1d $uvf_pattern)
echo "gridding each uvf separately, uvf_list=$uvf_list"
for uvf in $uvf_list; do
    echo uvf=$uvf
    export parent=${uvf%/*}
    export parent_parent=${parent%/*}
    echo parent_parent=$parent_parent
    mkdir -p "$parent_parent/ps"
    # ext is the basename of the uvf file without the extension
    export ext=${uvf%.uvfits}
    export ext=${ext##*/}

    # redundant, but CHIPS needs these
    # this produces {noisec,bv,noisecdiff,bvdiff,weightsc}_{xx,yy}.${ext}.dat in $OUTPUTDIR
    export DATADIR="$parent/" INPUTDIR="$parent/" OUTPUTDIR="$parent_parent/ps/" OBSDIR="$parent/"
    echo ext=$ext
    if [ -f "$parent_parent/ps/weightsc_yy.${ext}.dat" ]; then
        echo "weightsc_yy.${ext}.dat exists in $parent_parent/ps, skipping gridvisdiff"
    else
        echo "weightsc_yy.${ext}.dat does not exist in $parent_parent/ps, running gridvisdiff"
        gridvisdiff $uvf $obsid $ext $eorband -f $eorfield
    fi
    # this produces {vis_tot,vis_diff,noise_tot,noise_diff,weights}_${pol}_${ext}.dat in $OUTPUTDIR
    for pol in $pols; do
        if [ -f "$parent_parent/ps/crosspower_${pol}_${bias_mode}.iter.${ext}.dat" ]; then
            echo "crosspower_${pol}_${bias_mode}.iter.${ext}.dat exists in $parent_parent/ps, skipping prepare_diff"
        else
            set -x
            prepare_diff $ext $nchan 0 $pol $ext $eorband -p $period -c $chanwidth -n $lowfreq -u $maxu
            set +x
        fi
    done
done

# TODO: combine if more than one uvf

for pol in $pols; do
    lssa_fg_simple $ext $nchan $nbins $pol $maxu $ext $bias_mode $eorband -p $period -c $chanwidth
done
