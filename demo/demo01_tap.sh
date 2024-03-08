#!/bin/bash

# ##### #
# HOOKS #
# ##### #
# you can overwrite these with environment variables
export python=${python:-python}
export SCRIPT_BASE=${SCRIPT_BASE:-${PWD}/demo/}

# ### #
# TAP #
# ### #
# query the MWA TAP server with ADQL using the pyvo library
# details: https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/24970532/MWA+ASVO+VO+Services
eval $python $SCRIPT_BASE/demo01_tap.py
