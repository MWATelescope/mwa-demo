# syntax=docker/dockerfile:1
# lightweight, cpu-only dockerfile for demoing MWA software stack on desktops
# amd64 only, until https://github.com/pkgw/rubbl/issues/345
ARG UBUNTU_VERSION=20.04

FROM ubuntu:${UBUNTU_VERSION} as base

ENV DEBIAN_FRONTEND="noninteractive"
RUN apt-get update && \
    apt-get install -y \
        build-essential \
        casacore-data \
        casacore-data casacore-dev \
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

# Get Rust
ARG RUST_VERSION=1.75
ENV RUSTUP_HOME=/opt/rust CARGO_HOME=/opt/cargo PATH=/opt/cargo/bin:$PATH
RUN mkdir -m755 $RUSTUP_HOME $CARGO_HOME && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
        --profile=minimal \
        --default-toolchain=${RUST_VERSION}-$(uname -m)-unknown-linux-gnu

# aoflagger
ARG AOFLAGGER_VERSION=3.4.0
RUN git clone --depth 1 --branch v${AOFLAGGER_VERSION} --recurse-submodules https://gitlab.com/aroffringa/aoflagger.git /aoflagger && \
    cd /aoflagger && \
    mkdir build && \
    cd build && \
    cmake .. && \
    make install -j`nproc` && \
    ldconfig && \
    cd / && \
    rm -rf /aoflagger

# birli
ARG BIRLI_VERSION=0.10.0
RUN git clone --depth 1 --branch v${BIRLI_VERSION} https://github.com/MWATelescope/Birli.git /Birli && \
    cd /Birli && \
    cargo install --path . --locked && \
    cd / && \
    rm -rf /Birli ${CARGO_HOME}/registry && \
    birli --version

# hyperdrive-cpu with fits catalogue support, optimization disabled
RUN git clone --depth 1 --branch issue-27 https://github.com/MWATelescope/mwa_hyperdrive.git /hyperdrive && \
    cd /hyperdrive && \
    rm -rf .cargo/config.toml && \
    RUSTFLAGS='-C target-cpu=x86-64' cargo install --path . --locked && \
    cd / && \
    rm -rf /hyperdrive ${CARGO_HOME}/registry && \
    hyperdrive --version