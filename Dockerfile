# syntax=docker/dockerfile:1
# lightweight, cross-platform, cpu-only dockerfile for demoing MWA software stack on desktops
# amd64, arm32v7, arm64v8
# ref: https://docs.docker.com/build/building/multi-platform/
ARG UBUNTU_VERSION=20.04

FROM ubuntu:${UBUNTU_VERSION} as base

ENV DEBIAN_FRONTEND="noninteractive"
RUN apt-get update && \
    apt-get install -y \
        build-essential \
        casacore-data \
        casacore-dev \
        clang \
        cmake \
        curl \
        cython3 \
        fontconfig \
        g++ \
        git \
        ipython3 \
        jq \
        lcov \
        libatlas3-base \
        libblas-dev \
        libboost-date-time-dev \
        libboost-filesystem-dev \
        libboost-program-options-dev \
        libboost-system-dev \
        libboost-test-dev \
        libcfitsio-dev \
        liberfa-dev \
        libexpat1-dev \
        libfftw3-dev \
        libfontconfig-dev \
        libfreetype-dev \
        libgsl-dev \
        libgtkmm-3.0-dev \
        libhdf5-dev \
        liblapack-dev \
        liblua5.3-dev \
        libopenmpi-dev \
        libpng-dev \
        libpython3-dev \
        libssl-dev \
        libxml2-dev \
        pkg-config \
        procps \
        python3 \
        python3-dev \
        python3-pip \
        tzdata \
        unzip \
        wget \
        zip \
    && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    apt-get -y autoremove

# use python3 as the default python
RUN update-alternatives --install /usr/bin/python python /usr/bin/python3 1

# install python prerequisites
RUN python -m pip install --upgrade pip && \
    python -m pip install \
        kneed \
        matplotlib \
        maturin[patchelf] \
        numpy>=1.21.0 \
        pandas \
        pip \
        pyuvdata \
        pyvo \
        tabulate \
        seaborn \
    ;

# install ssins
ARG SSINS_VERSION=master
RUN git clone --depth 1 --branch ${SSINS_VERSION} https://github.com/mwilensky768/SSINS.git /ssins && \
    python -m pip install /ssins && \
    rm -rf /ssins

# install mwa_qa
ARG MWAQA_VERSION=dev
RUN git clone --depth 1 --branch ${MWAQA_VERSION} https://github.com/d3v-null/mwa_qa.git /mwa_qa && \
    python -m pip install /mwa_qa && \
    rm -rf /mwa_qa

# Get Rust
ARG RUST_VERSION=1.75
ENV RUSTUP_HOME=/opt/rust CARGO_HOME=/opt/cargo PATH=/opt/cargo/bin:$PATH
RUN mkdir -m755 $RUSTUP_HOME $CARGO_HOME && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
        --profile=minimal \
        --default-toolchain=${RUST_VERSION}-$(uname -m)-unknown-linux-gnu

# TODO: MWALIB_VERSION=1.2.1 after https://github.com/MWATelescope/mwalib/issues/67
ARG MWALIB_VERSION=1.0.1
RUN git clone --depth 1 --branch v${MWALIB_VERSION} https://github.com/MWATelescope/mwalib.git /mwalib && \
    cd /mwalib && \
    maturin build --release --features=python && \
    python -m pip install $(ls -1 target/wheels/*.whl | tail -n 1) && \
    cd / && \
    rm -rf /mwalib ${CARGO_HOME}/registry

# TODO: --recurse-submodules
ARG EVERYBEAM_VERSION=0.5.2
RUN git clone --depth 1 --branch v${EVERYBEAM_VERSION} https://git.astron.nl/RD/EveryBeam.git /EveryBeam && \
    cd /EveryBeam && \
    git submodule update --init --recursive && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make install -j`nproc` && \
    cd / && \
    rm -rf /EveryBeam

ARG IDG_VERSION=1.2.0
RUN git clone --depth 1 --branch ${IDG_VERSION} https://git.astron.nl/RD/idg.git /idg && \
    cd /idg && \
    git submodule update --init --recursive && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make install -j`nproc` && \
    cd / && \
    rm -rf /idg

ARG WSCLEAN_VERSION=3.4
RUN git clone --depth 1 --branch v${WSCLEAN_VERSION} https://gitlab.com/aroffringa/wsclean.git /wsclean && \
    cd /wsclean && \
    git submodule update --init --recursive && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make install -j`nproc` && \
    cd / && \
    rm -rf /wsclean

ARG GIANTSQUID_VERSION=0.8.0
RUN git clone --depth 1 --branch v${GIANTSQUID_VERSION} https://github.com/MWATelescope/giant-squid.git /giant-squid && \
    cd /giant-squid && \
    cargo install --path . --locked && \
    cd / && \
    rm -rf /giant-squid ${CARGO_HOME}/registry

# download latest Leap_Second.dat file
RUN python -c "from astropy.time import Time; print(Time.now().gps)"

# unfortunately because of a casacore issue, we can't put everything in the same dockerfile
# The remaining software stack is in amd64.Dockerfile

# aoflagger
# ARG AOFLAGGER_VERSION=3.1.0
# RUN git clone --depth 1 --branch v${AOFLAGGER_VERSION} --recurse-submodules https://gitlab.com/aroffringa/aoflagger.git /aoflagger && \
#     cd /aoflagger && \
#     mkdir build && \
#     cd build && \
#     cmake .. && \
#     make install -j`nproc` && \
#     cd / && \
#     rm -rf /aoflagger

# ARG BIRLI_VERSION=0.10.0
# RUN git clone --depth 1 --branch v${BIRLI_VERSION} https://github.com/MWATelescope/Birli.git /Birli && \
#     cd /Birli && \
#     cargo install --path . --locked && \
#     cd / && \
#     rm -rf /Birli ${CARGO_HOME}/registry

# ARG HYPERDRIVE_VERSION=0.3.0
# RUN git clone --depth 1 --branch v${HYPERDRIVE_VERSION} https://github.com/MWATelescope/mwa_hyperdrive.git /hyperdrive && \
#     cd /hyperdrive && \
#     cargo install --path . --locked && \
#     cd / && \
#     rm -rf /hyperdrive ${CARGO_HOME}/registry