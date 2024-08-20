#!/bin/bash
# test the software dependencies via environment variables

# is this script being sourced? https://stackoverflow.com/a/28776166/565019
if (
    [[ -n $ZSH_VERSION && $ZSH_EVAL_CONTEXT =~ :file$ ]] ||
        [[ -n $BASH_VERSION ]] && (return 0 2>/dev/null)
); then
    echo "this script is not intended for sourcing, run it with 'bash demo/00_test.sh'"
    return 1
fi

# ### #
# ENV #
# ### #
# see: 00_env.sh
if [ -n "$ZSH_VERSION" ]; then ME="${0:A}"; else ME=$(realpath ${BASH_SOURCE:0}); fi
export SCRIPT_BASE=${SCRIPT_BASE:-$(dirname $ME)}
source $SCRIPT_BASE/00_env.sh

# (for debugging) configure bash to:
# - (-e) exit on error
# - (-u) raise an error if a variable is used before being set
# - (-x) trace the execution of the script
# we do this after the giant-squid check to avoid showing the api key in the logs
set -eu

# #### #
# DATA #
# #### #
# DEMO: check raw files are present
if command -v md5sum &>/dev/null; then
    echo "validating raw files with md5sum"
    md5sum -c demo_data.md5sum
else
    echo "md5sum or md5 not found. couldn't validate raw files."
    exit 1
fi

# #### #
# BINS #
# #### #
# DEMO: check software is installed
if ! giant-squid --version; then
    echo "giant-squid not found. https://github.com/MWATelescope/giant-squid?tab=readme-ov-file#installation "
    exit 1
fi
if ! wsclean --version; then
    echo "wsclean not found. https://wsclean.readthedocs.io/en/latest/installation.html "
    exit 1
fi
if ! hyperdrive --version; then
    echo "hyperdrive not found. https://mwatelescope.github.io/mwa_hyperdrive/installation/intro.html "
    exit 1
fi
if ! jq --version; then
    echo "jq not found. https://jqlang.github.io/jq/download/ "
    exit 1
fi
if ! python --version; then
    echo "python not found. https://www.python.org/downloads/ "
    exit 1
fi

## ensure outdir exists
if [[ ! -d "$outdir" ]]; then
    echo "outdir=$outdir does not exist. try mkdir -p $outdir"
    exit 1
fi

# ####### #
# SRCLIST #
# ####### #
# DEMO: download srclist unless it exists
if [[ $srclist =~ srclist_puma && ! -f "$srclist" ]]; then
    echo "downloading srclist ${srclist} from github"
    curl -L -o $srclist "https://github.com/JLBLine/srclists/raw/master/${srclist##*/}"
fi
# DEMO: verify srclist
hyperdrive srclist-verify $srclist

# #### #
# BEAM #
# #### #
# DEMO: download beam unless it exists
if [[ ! -f "$MWA_BEAM_FILE" ]]; then
    echo "downloading beam ${MWA_BEAM_FILE} from mwatelescope.org"
    curl -L -o $MWA_BEAM_FILE "http://ws.mwatelescope.org/static/${MWA_BEAM_FILE##*/}"
fi
# DEMO: verify beam
hyperdrive beam fee --output /dev/null

# ######## #
# OPTIONAL #
# ######## #
echo "recommended software, not on the critical path:"
set +eux

## verify ASVO API Key
giant-squid list >/dev/null

# DEMO: check wsclean features
wsclean --version | tee .wsclean_version
while IFS='|' read -r feature details; do
    if ! grep -q "${feature} is available" .wsclean_version; then
        echo "warning: wsclean $feature not found. recompile wsclean after installing $feature"
        echo details: $details
    fi
done <<'EoF'
IDG|       https://gitlab.com/astron-idg/idg
EveryBeam| https://everybeam.readthedocs.io/en/latest/build-instructions.html
EoF
rm .wsclean_version

# DEMO: check python version
if ! python -c $'"assert __import__(\'sys\').version_info>=(3,8)"' >/dev/null; then
    echo "warning: python version 3.8+ not found https://www.python.org/downloads/ "
    python --version
fi

# DEMO: check python packages
while IFS='|' read -r package details; do
    if ! eval "$python -m pip show $package >/dev/null"; then
        echo "recommended: python package $package not found."
        echo details: $details
    fi
done <<'EoF'
pyvo|    https://pyvo.readthedocs.io/en/latest/#installation
mwalib|  https://github.com/MWATelescope/mwalib/wiki/Installation%3A-Python-Users
ssins|   https://github.com/mwilensky768/SSINS?tab=readme-ov-file#installation
mwa_qa|  git clone https://github.com/d3v-null/mwa_qa.git ; pip install mwa_qa
EoF

# DEMO: is the MWA TAP server accessible?
if ! python -c $'"assert len(__import__(\'pyvo\').dal.TAPService(\'http://vo.mwatelescope.org/mwa_asvo/tap\').tables)"'; then
    echo "warning: MWA TAP inaccessible. https://wiki.mwatelescope.org/display/MP/MWA+TAP+Service "
fi

echo "all required software dependencies are working, scroll up for recommendations"
