#!/bin/bash
# shellcheck disable=SC2139

export docker_base="docker run --rm -it"
export docker_img=${docker_img:="mwatelescope/mwa-demo:latest"}

# silly hacks for Windows / Git Bash
if [[ -n "$OS" && "$OS" == "Windows_NT" ]]; then
    export docker_base="$docker_base -v /\${PWD}:\${PWD} -w /\${PWD}"
    export outdir='./demo/data'
    export SCRIPT_BASE='./demo'
else
    export docker_base="$docker_base -v \${PWD}:\${PWD} -v \${outdir}:\${outdir} -w \${PWD}"
fi

alias birli="$docker_base --entrypoint=birli '${docker_img}'"
alias giant_squid="$docker_base --entrypoint=giant-squid -e MWA_ASVO_API_KEY=\$MWA_ASVO_API_KEY '${docker_img}'"
alias hyperdrive="$docker_base --entrypoint=hyperdrive -e MWA_BEAM_FILE=\$MWA_BEAM_FILE '${docker_img}'"
alias jq="$docker_base --entrypoint=jq '${docker_img}'"
alias wsclean="$docker_base --entrypoint=wsclean '${docker_img}'"
alias python="$docker_base --entrypoint=python '${docker_img}'"
alias plot_calqa="$docker_base --entrypoint=plot_calqa.py '${docker_img}'"
alias plot_prepqa="$docker_base --entrypoint=plot_prepvisqa.py '${docker_img}'"
alias run_calqa="$docker_base --entrypoint=run_calqa.py '${docker_img}'"
alias run_prepqa="$docker_base --entrypoint=run_prepvisqa.py '${docker_img}'"
