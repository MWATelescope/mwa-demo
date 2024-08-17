#!/bin/bash

export docker_base="docker run --rm -it"

# silly hacks for Windows / Git Bash
if [[ -n "$OS" && "$OS" == "Windows_NT" ]]; then
    export docker_base="$docker_base -v /\${PWD}:\${PWD} -w /\${PWD}"
    export outdir='./demo/data'
    export SCRIPT_BASE='./demo'
    export force_docker=true
else
    export docker_base="$docker_base -v \${PWD}:\${PWD} -v \${outdir}:\${outdir} -w \${PWD}"
fi

export docker_img=${docker_img:="d3vnull0/mwa-demo:latest"}
export force_docker=${force_docker:="false"}
# if $force_docker is set, or the command is not found provide software with docker
# if a command is not set, it will be set to the default value in 00_env.sh
if [[ "$force_docker" != "false" ]] || ! command -v birli >/dev/null 2>&1; then export birli="$docker_base --entrypoint=birli '${docker_img}'"; fi
if [[ "$force_docker" != "false" ]] || ! command -v giant-squid >/dev/null 2>&1; then export giant_squid="$docker_base --entrypoint=giant-squid -e MWA_ASVO_API_KEY=\$MWA_ASVO_API_KEY '${docker_img}'"; fi
if [[ "$force_docker" != "false" ]] || ! command -v hyperdrive >/dev/null 2>&1; then export hyperdrive="$docker_base --entrypoint=hyperdrive -e MWA_BEAM_FILE=\$MWA_BEAM_FILE '${docker_img}'"; fi
if [[ "$force_docker" != "false" ]] || ! command -v jq >/dev/null 2>&1; then export jq="$docker_base --entrypoint=jq '${docker_img}'"; fi
if [[ "$force_docker" != "false" ]] || ! command -v wsclean >/dev/null 2>&1; then export wsclean="$docker_base --entrypoint=wsclean '${docker_img}'"; fi
# python
if [[ "$force_docker" != "false" ]] || ! command -v python >/dev/null 2>&1; then export python="$docker_base --entrypoint=python '${docker_img}'"; fi
if [[ "$force_docker" != "false" ]] || ! command -v plot_calqa.py >/dev/null 2>&1; then export plot_calqa="$docker_base --entrypoint=plot_calqa.py '${docker_img}'"; fi
if [[ "$force_docker" != "false" ]] || ! command -v plot_prepvisqa.py >/dev/null 2>&1; then export plot_prepqa="$docker_base --entrypoint=plot_prepvisqa.py '${docker_img}'"; fi
if [[ "$force_docker" != "false" ]] || ! command -v run_calqa.py >/dev/null 2>&1; then export run_calqa="$docker_base --entrypoint=run_calqa.py '${docker_img}'"; fi
if [[ "$force_docker" != "false" ]] || ! command -v run_prepvisqa.py >/dev/null 2>&1; then export run_prepqa="$docker_base --entrypoint=run_prepvisqa.py '${docker_img}'"; fi
