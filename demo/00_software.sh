#!/bin/bash

export docker_base="docker run --rm -t -v \${PWD}:\${PWD} -v \${outdir}:\${outdir} -w \${PWD}"
# uncomment me to enable docker gpu support ()
# export gpus="all"
if [[ -n "${gpus:-}" ]]; then
    export docker_base="$docker_base --gpus=$gpus"
fi

# I was hoping to get the whole demo working from a single multi-platform docker image, but it's
# not quite there yet, so some amd64-only images will need to be emulated on arm64 for now.

# multiplatform
export docker_tag=${docker_tag:="latest"}
export python="$docker_base --entrypoint=python 'd3vnull0/mwa-demo:${docker_tag}' "
export giant_squid="$docker_base -e MWA_ASVO_API_KEY=\$MWA_ASVO_API_KEY --entrypoint giant-squid 'd3vnull0/mwa-demo:${docker_tag}' "
export run_prepqa="$docker_base --entrypoint=python 'd3vnull0/mwa-demo:${docker_tag}' /usr/local/bin/run_prepvisqa.py"
export plot_prepqa="$docker_base --entrypoint=python 'd3vnull0/mwa-demo:${docker_tag}' /usr/local/bin/plot_prepvisqa.py "
export run_calqa="$docker_base --entrypoint=python 'd3vnull0/mwa-demo:${docker_tag}' /usr/local/bin/run_calqa.py "
export plot_calqa="$docker_base --entrypoint=python 'd3vnull0/mwa-demo:${docker_tag}' /usr/local/bin/plot_calqa.py "
export wsclean="$docker_base --entrypoint=wsclean 'd3vnull0/mwa-demo:${docker_tag}'"
export birli="$docker_base --entrypoint=birli d3vnull0/mwa-demo:${docker_tag}"
export hyperdrive="$docker_base --entrypoint=hyperdrive -e MWA_BEAM_FILE=\$MWA_BEAM_FILE d3vnull0/mwa-demo:${docker_tag}"

# amd64-only
# export giant_squid="$docker_base mwatelescope/giant-squid:latest giant-squid"
# export birli="$docker_base --platform linux/amd64 --entrypoint birli d3vnull0/mwa-demo-amd64:latest"
# export birli="$docker_base --platform linux/amd64 --entrypoint birli mwatelescope/birli:latest"
# export hyperdrive="$docker_base --platform linux/amd64 --entrypoint hyperdrive -e MWA_BEAM_FILE=\$MWA_BEAM_FILE d3vnull0/mwa_hyperdrive:fits"
# if [[ -n "${gpus:-}" ]]; then
#   export wsclean="$docker_base --platform linux/amd64 --entrypoint wsclean d3vnull0/wsclean_idg:nvidia12.2.2-idg1.2.0-wsclean3.4"
# fi
