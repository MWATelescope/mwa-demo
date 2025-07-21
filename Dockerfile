# syntax=docker/dockerfile:1
# cross-platform, cpu-only dockerfile for demoing MWA software stack
# on amd64, arm64
# ref: https://docs.docker.com/build/building/multi-platform/
ARG BASE_IMAGE=mwatelescope/hyperdrive:main
FROM $BASE_IMAGE AS base

# Suppress perl locale errors
ENV LC_ALL=C
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    autoconf \
    build-essential \
    ca-certificates \
    casacore-data \
    casacore-dev \
    clang \
    cmake \
    curl \
    ffmpeg \
    g++ \
    gfortran \
    git \
    jq \
    lcov \
    libatlas3-base \
    libblas-dev \
    libboost-date-time-dev \
    libboost-filesystem-dev \
    libboost-program-options-dev \
    libboost-python-dev \
    libboost-system-dev \
    libboost-test-dev \
    liberfa-dev \
    libexpat1-dev \
    libfftw3-dev \
    libfontconfig-dev \
    libfreetype-dev \
    libgsl-dev \
    libhdf5-dev \
    liblapack-dev \
    liblua5.3-dev \
    libopenblas-dev \
    libpng-dev \
    libssl-dev \
    libstarlink-pal-dev \
    libtool \
    libxml2-dev \
    pkg-config \
    procps \
    python3 \
    python3-pip \
    strace \
    time \
    tzdata \
    unzip \
    vim \
    wcslib-dev \
    wget \
    zip \
    zlib1g-dev \
    && \
    apt-get clean all && \
    rm -rf /tmp/* /var/tmp/* && \
    apt-get -y autoremove

# if the python command does not exist, use python3 as the default
RUN command -v python || update-alternatives --install /usr/bin/python python /usr/bin/python3 1

# install giant-squid
RUN --mount=type=cache,target=/app/target/ \
    --mount=type=cache,target=${CARGO_HOME}/git/db \
    --mount=type=cache,target=${CARGO_HOME}/registry/ \
    cargo install mwa_giant_squid --locked && \
    cargo clean

# for example, CMAKE_ARGS="-D CMAKE_CXX_FLAGS='-march=native -mtune=native -O3 -fomit-frame-pointer'"
ARG CMAKE_ARGS="-DPORTABLE=True"

ARG EVERYBEAM_BRANCH=v0.6.1
RUN git clone --depth 1 --branch=${EVERYBEAM_BRANCH} --recurse-submodules https://git.astron.nl/RD/EveryBeam.git /EveryBeam && \
    cd /EveryBeam && \
    git submodule update --init --recursive && \
    mkdir build && \
    cd build && \
    cmake $CMAKE_ARGS .. && \
    make install -j && \
    cd / && \
    rm -rf /EveryBeam

ARG IDG_BRANCH=1.2.0
RUN git clone --depth 1 --branch=${IDG_BRANCH} https://git.astron.nl/RD/idg.git /idg && \
    cd /idg && \
    git submodule update --init --recursive && \
    mkdir build && \
    cd build && \
    cmake $CMAKE_ARGS .. && \
    make install -j && \
    cd / && \
    rm -rf /idg

# can't get wsclean2.X to compile on arm64 :(
# ARG WSCLEAN_BRANCH=wsclean2.9
ARG WSCLEAN_BRANCH=v3.5
RUN git clone --depth 1 --branch=${WSCLEAN_BRANCH} https://gitlab.com/aroffringa/wsclean.git /wsclean && \
    cd /wsclean && \
    git submodule update --init --recursive && \
    mkdir build && \
    cd build && \
    cmake $CMAKE_ARGS .. && \
    make install -j && \
    cd / && \
    rm -rf /wsclean

# install chips
RUN git clone --depth 1 https://github.com/d3v-null/chips2024.git /chips && \
    cd /chips && \
    make install -j PAL_LIBS="-lstarlink_pal" PREFIX=/usr/local && \
    cd / && \
    rm -rf /chips

ARG AOFLAGGER_BRANCH=v3.4.0
RUN if ! command -v aoflagger; then \
        git clone --depth 1 --branch=${AOFLAGGER_BRANCH} --recurse-submodules https://gitlab.com/aroffringa/aoflagger.git /aoflagger && \
        cd /aoflagger && \
        mkdir build && \
        cd build && \
        cmake $CMAKE_ARGS \
        -DENABLE_GUI=OFF \
        -DPORTABLE=True \
        .. && \
        make install -j && \
        ldconfig && \
        cd / && \
        rm -rf /aoflagger; \
    fi

# install birli if it doesn't exist
RUN --mount=type=cache,target=${CARGO_HOME}/git/db \
    --mount=type=cache,target=${CARGO_HOME}/registry/ \
    if ! command -v birli; then \
        apt-get update && \
        DEBIAN_FRONTEND=noninteractive apt-get install -y libaoflagger0 automake libcfitsio-dev && \
        git clone https://github.com/mwatelescope/birli.git --branch=eavil_ssins /birli && \
        cd /birli && \
        wget https://gitlab.com/aroffringa/aoflagger/-/raw/master/interface/aoflagger.h && \
        CXXFLAGS=-I. cargo install --path . --locked --features=aoflagger && \
        cargo clean && \
        cd / && \
        rm -rf /birli && \
        apt-get clean all && \
        rm -rf /tmp/* /var/tmp/* && \
        apt-get -y autoremove; \
    fi

# install python prerequisites
# - install Cython first to fix pyuvdata compilation issues
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip config set global.break-system-packages true && \
    python -m pip install \
    'cython<3.0' \
    'scikit_build_core' \
    'setuptools-scm==8.2.0' \
    'packaging==24.2' \
    && python -m pip install \
    'pyvo>=1.5.2' \
    'psutil>=6.0.0' \
    'docstring_parser>=0.15' \
    'astropy>=6.0,<7' \
    'h5py>=3.4' \
    'numpy>=1.23,<2' \
    'pyerfa>=2.0.1.1' \
    'pyyaml>=5.4.1' \
    'scipy>=1.8,<1.12' \
    'pandas>=2.2.3' \
    'matplotlib==3.9.0' \
    'python-casacore>=3.5.2,<3.7' \
    'aoquality' \
    && python -m pip install --no-build-isolation \
    'pyuvdata[casa]==3.1.3' \
    && python -m pip install \
    git+https://github.com/d3v-null/SSINS.git@eavils-copilot \
    git+https://github.com/d3v-null/mwa_qa.git@dev \
    git+https://github.com/PaulHancock/Aegean.git \
    git+https://github.com/tjgalvin/fits_warp.git \
    git+https://github.com/Chuneeta/mwa_cal.git

# # download latest Leap_Second.dat, IERS finals2000A.all
RUN python -c "from astropy.time import Time; t=Time.now(); from astropy.utils.data import download_file; download_file('http://data.astropy.org/coordinates/sites.json', cache=True); print(t.gps, t.ut1)"

# FROM mwatelescope/giant-squid:latest AS giant_squid
# RUN /opt/cargo/bin/giant-squid --version
# # HACK: the calibration fitting code in mwax_mover deserves its own public repo
FROM d3vnull0/mwax_mover:latest AS mwax_mover
FROM base
# # Copy files from the previous stages into the final image
COPY --from=mwax_mover /app /mwax_mover
# copy giant squid binary from its own image
# COPY --from=giant_squid /opt/cargo/bin/giant-squid /opt/cargo/bin/giant-squid
# RUN /opt/cargo/bin/giant-squid --version

RUN cd /mwax_mover && \
    chmod +x /mwax_mover/scripts/*.py && \
    python -m pip install .
ENV PATH="/mwax_mover/scripts/:${PATH}"

# add chips wrappers
RUN --mount=type=cache,target=/root/.cache/pip \
    python -m pip install  \
    git+https://github.com/d3v-null/CHIPS_wrappers.git@rn-changes

# python /mwax_mover/scripts/cal_analysis.py \
# --name "${name}" \
# --metafits "${metafits}" --solns ${soln} \
# --phase-diff-path=/mwax_mover/phase_diff.txt \
# --plot-residual --residual-vmax=0.5

# export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
# export raw="$(ls -1 ${outdir}/${obsid}/raw/${obsid}*.fits)"
# export soln=${outdir}/${obsid}/cal/hyp_soln_${obsid}.fits
# docker run --rm -it -v ${PWD}:${PWD} -w ${PWD} --entrypoint python mwatelescope/mwa-demo:latest /mwax_mover/scripts/cal_analysis.py --name foo --metafits ${metafits} --solns ${soln} --phase-diff-path=/mwax_mover/phase_diff.txt --plot-residual --residual-vmax=0.5
# docker run --rm -it -v ${PWD}:${PWD} -w ${PWD} --entrypoint python d3vnull0/mwax_mover:latest /app/scripts/cal_analysis.py --name foo --metafits ${metafits} --solns ${soln} --phase-diff-path=/app/phase_diff.txt --plot-residual --residual-vmax=0.5

# Copy the demo files
COPY ./demo /demo
ENV PATH="/demo:${PATH}"
WORKDIR /demo

# Ensure 00_env.sh is sourced in every bash shell unless already sourced
RUN echo 'if [[ -z "$_ENV_SOURCED" ]]; then source /demo/00_env.sh; fi' >> /etc/bash.bashrc

# Create custom entrypoint that sources env unless already sourced
RUN echo '#!/bin/bash' > /entrypoint.sh && \
    echo 'if [[ -z "$_ENV_SOURCED" ]]; then source /demo/00_env.sh; fi' >> /entrypoint.sh && \
    echo 'exec "$@"' >> /entrypoint.sh && \
    chmod +x /entrypoint.sh

ARG TEST_SHIM=""
RUN ${TEST_SHIM}

ENTRYPOINT ["/entrypoint.sh", "/bin/bash"]