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

# this creates a fake binary for each tool in the bin/ directory.
# delete any binaries that already exist on your system.

mkdir -p bin/
rm bin/*
while IFS='|' read -r bin argv; do
    # strip spaces
    bin=$(echo "$bin" | tr -d '[:space:]')
    if command -v "$bin" &>/dev/null; then
        echo "$bin already exists, skipping"
        continue
    else
        echo "$bin not found, creating bin/$bin"
    fi
    echo "#!/bin/bash" >"bin/$bin"
    echo "$docker_base --entrypoint=$bin $argv $docker_img \"\$@\"" >>"bin/$bin"
    chmod +x "bin/$bin"
done <<-EoF
birli
giant-squid | -e MWA_ASVO_API_KEY=\$MWA_ASVO_API_KEY
hyperdrive  | -e MWA_BEAM_FILE=\$MWA_BEAM_FILE
jq
wsclean
python
plot_calqa.py
plot_prepvisqa.py
run_calqa.py
run_prepvisqa.py
EoF
