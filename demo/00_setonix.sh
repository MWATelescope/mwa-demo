#!/bin/bash
# shellcheck disable=SC2139

export outdir=${outdir:=${MYSCRATCH}/}
module use /software/projects/pawsey1094/setonix/2024.05/modules/zen3/gcc/12.2.0
# module unload ?
module load hyperdrive/default birli/default giant-squid/default hyperbeam/default wsclean/2.9 mwalib/default singularity/default
module load py-pip/default py-numpy/default
pip install --user \
    pyvo==1.5.2 \
    psutil==6.0.0 \
    git+https://github.com/mwilensky768/SSINS.git \
    git+https://github.com/PaulHancock/Aegean.git \
    git+https://github.com/tjgalvin/fits_warp.git \
    git+https://github.com/d3v-null/mwa_qa.git@dev

export singularity_base="singularity exec"
export docker_img=${docker_img:="mwatelescope/mwa-demo:latest"}

export bindir=${PWD}/bin/
export PATH=${PATH}:${bindir}
mkdir -p ${bindir}
rm ${bindir}*
while IFS='|' read -r bin argv; do
    # strip spaces
    bin=$(echo "$bin" | tr -d '[:space:]')
    if command -v "$bin" &>/dev/null; then
        echo "$bin already exists, skipping"
        continue
    else
        echo "$bin not found, creating ${bindir}$bin"
    fi
    echo "#!/bin/bash" >"${bindir}$bin"
    echo "$singularity_base $argv $docker_img $bin \"\$@\"" >>"${bindir}$bin"
    chmod +x "${bindir}$bin"
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
