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

# generate k_edges.txt

[ ! -f $outdir/k_edges.txt ] && cat >$outdir/k_edges.txt <<EOF
0.0
0.123863
0.159253
0.194642
0.230032
0.265421
0.300811
0.336201
0.371590
0.406980
0.442369
0.477759
0.513148
0.548538
0.583927
0.619317
0.654706
0.690096
0.725485
0.760875
0.796264
0.831654
0.867043
0.902433
0.937823
0.973212
1.00860
1.04399
1.07938
1.11477
1.15016
1.18555
1.22094
1.25633
1.29172
1.32711
1.36250
1.39789
1.43328
1.46867
1.50406
1.53944
1.57483
1.61022
1.64561
1.68100
1.71639
1.75178
1.78717
1.82256
EOF

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
        set -x
        gridvisdiff $uvf $obsid $ext $eorband -f $eorfield
        echo "gridvisdiff exit code: $?"
        set +x
    fi
    # this produces {vis_tot,vis_diff,noise_tot,noise_diff,weights}_${pol}_${ext}.dat in $OUTPUTDIR
    for pol in $pols; do
        if [ -f "$parent_parent/ps/noise_tot_${pol}.${ext}.dat" ]; then
            echo "noise_tot_${pol}.${ext}.dat exists in $parent_parent/ps, skipping prepare_diff"
        else
            set -x
            prepare_diff $ext $nchan 0 $pol $ext $eorband -p $period -c $chanwidth -n $lowfreq -u $maxu
            echo "prepare_diff exit code: $?"
            set +x
        fi
    done
done

# TODO: combine if more than one uvf, this just does the last one in the list

for pol in $pols; do
    export DATADIR="$parent_parent/ps/" INPUTDIR="$parent_parent/ps/" OUTPUTDIR="$parent_parent/ps/" OBSDIR="$parent_parent/ps/"
    if [ -f "$parent_parent/ps/crosspower_${pol}_${bias_mode}.iter.${ext}.dat" ]; then
        echo "crosspower_${pol}_${bias_mode}.iter.${ext}.dat exists in $parent_parent/ps, skipping lssa_fg_simple"
    else
        set -x
        lssa_fg_simple $ext $nchan $nbins $pol $maxu $ext $bias_mode $eorband -p $period -c $chanwidth
        export lssa_fg_simple_exit_code=$?
        set +x
        if [ $lssa_fg_simple_exit_code -ne 0 ]; then
            cat $parent_parent/ps/syslog_lssa.txt
            echo "lssa_fg_simple failed, exiting"
            exit 1
        fi
    fi

    set -eux
    chips1D_tsv.py \
        --basedir $parent_parent/ps/ \
        --chips_tag $ext \
        --outputdir $parent_parent/ps/ \
        --polarisation $pol \
        --N_kperp $nbins \
        --N_chan_orig $nchan \
        --lowerfreq_orig $lowfreq \
        --chan_width $chanwidth \
        --umax $maxu \
        --bias_mode $bias_mode \
        --density_correction 2.15 \
        --ktot_bin_edges $outdir/k_edges.txt \
        --kperp_max 0.06 \
        --kperp_min 0.02 \
        --kparra_min 0.11 \
        --kparra_max 100
    set +eux

done
