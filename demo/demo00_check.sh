#!/bin/bash

# ##### #
# HOOKS #
# ##### #
# you can overwrite these defaults with environment variables
export outdir=${outdir:-${PWD}/demo/data/}
export srclist=${srclist:-srclist_pumav3_EoR0LoBES_EoR1pietro_CenA-GP_2023-11-07.yaml}
export MWA_BEAM_FILE=${MWA_BEAM_FILE:-mwa_full_embedded_element_pattern.h5}
export hyperdrive=${hyperdrive:-hyperdrive}
export wsclean=${wsclean:-wsclean}
export casa=${casa:-casa}
export python=${python:-python}
export giant_squid=${giant_squid:-giant-squid}
export jq=${jq:-jq}

## ensure outdir exists
[[ ! -d "$outdir" ]] && echo "outdir=$outdir does not exist. try mkdir -p $outdir" && exit 1

# ####### #
# SRCLIST #
# ####### #
## download srclist unless it exists
[[ $srclist =~ srclist_puma && ! -f "$srclist" ]] && wget -O $srclist "https://github.com/JLBLine/srclists/raw/master/${srclist##*/}"
## verify srclist
eval $hyperdrive srclist-verify $srclist

# #### #
# BEAM #
# #### #
## download beam unless it exists
[[ ! -f "$MWA_BEAM_FILE" ]] && wget -O $MWA_BEAM_FILE "http://ws.mwatelescope.org/static/${MWA_BEAM_FILE##*/}"
## verify beam
eval $hyperdrive beam fee --output /dev/null -vv

## verify ASVO API Key
eval $giant_squid list -vv > /dev/null

# #### #
# BINS #
# #### #
set -ue # fail if hook not set or command fails
eval $casa --version || echo "casa not found. https://casa.nrao.edu/casa_obtaining.shtml "
eval $wsclean --version || echo "wsclean not found. https://gitlab.com/aroffringa/wsclean "
eval $hyperdrive --version || echo "hyperdrive not found. https://github.com/MWATelescope/mwa_hyperdrive/releases "
eval $giant_squid --version || echo "giant-squid not found. https://github.com/MWATelescope/giant-squid/releases "
eval $jq --version || echo "jq not found. https://jqlang.github.io/jq/download/ "
eval $python --version || echo "python not found. https://www.python.org/downloads/ "



# ######## #
# OPTIONAL #
# ######## #
eval $wsclean --version | grep -q 'IDG is available' || echo "recommend: wsclean IDG https://gitlab.com/astron-idg/idg "
eval $wsclean --version | grep -q 'EveryBeam is available.' || echo "recommend: wsclean EveryBeam "

## check python version
eval $python <<- EoF
import sys
assert sys.version_info >= (3, 8), "python version >= 3.8 required ( walrus := )"
EoF

## check python packages
eval $python -m pip show pyvo astropy mwalib tabulate matplotlib ssins || echo "python packages not found. pip install ..."

## is asvo up?
eval $python <<- EoF
import pyvo
tap = pyvo.dal.TAPService("http://vo.mwatelescope.org/mwa_asvo/tap")
from pprint import pprint
pprint([(tbl.name) for tbl in tap.tables])
# pprint([(col.name, col.description) for col in tap.tables['mwa.observation'].columns])
EoF
