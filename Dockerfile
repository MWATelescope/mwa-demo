# syntax=docker/dockerfile:1
# cross-platform, cpu-only dockerfile for demoing MWA software stack
# on amd64, arm64
# ref: https://docs.docker.com/build/building/multi-platform/
# ARG BASE_IMG="ubuntu:20.04"
# HACK: newer python breaks on old ubuntu
ARG BASE_IMG="python:3.11-bookworm"
FROM ${BASE_IMG} as base

# Suppress perl locale errors
ENV LC_ALL=C
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
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
    python3-wheel \
    python3-importlib-metadata \
    tzdata \
    unzip \
    wget \
    zip \
    && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    apt-get -y autoremove

# Get Rust
ARG RUST_VERSION=stable
ENV RUSTUP_HOME=/opt/rust CARGO_HOME=/opt/cargo PATH="/opt/cargo/bin:${PATH}"
RUN mkdir -m755 $RUSTUP_HOME $CARGO_HOME && ( \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | env RUSTUP_HOME=$RUSTUP_HOME CARGO_HOME=$CARGO_HOME sh -s -- -y \
    --profile=minimal \
    --default-toolchain=${RUST_VERSION} \
    )

# install python prerequisites
# - newer pip needed for mwalib maturin install
# - other versions pinned to avoid issues with numpy==2
ARG SSINS_BRANCH=master
ARG MWAQA_BRANCH=dev
RUN python -m pip install --no-cache-dir \
    importlib_metadata==8.2.0 \
    kneed==0.8.5 \
    matplotlib==3.7.5 \
    maturin[patchelf]==1.7.0 \
    numpy==1.24.4 \
    pandas==2.0.3 \
    pip==24.2 \
    pyuvdata==2.4.5 \
    pyvo==1.5.2 \
    seaborn==0.13.2 \
    tabulate==0.9.0 \
    psutil==6.0.0 \
    ;

# python packages
RUN python -m pip install --no-cache-dir \
    git+https://github.com/mwilensky768/SSINS.git@${SSINS_BRANCH} \
    git+https://github.com/d3v-null/mwa_qa.git@${MWAQA_BRANCH} \
    git+https://github.com/PaulHancock/Aegean.git \
    git+https://github.com/tjgalvin/fits_warp.git \
    ;

# ARG MWALIB_BRANCH=v1.5.0
# RUN git clone --depth 1 --branch=${MWALIB_BRANCH} https://github.com/MWATelescope/mwalib.git /mwalib && \
#     cd /mwalib && \
#     maturin build --release --features=python && \
#     python -m pip install $(ls -1 target/wheels/*.whl | tail -n 1) && \
#     cd / && \
#     rm -rf /mwalib ${CARGO_HOME}/registry

# # for example, CMAKE_ARGS="-D CMAKE_CXX_FLAGS='-march=native -mtune=native -O3 -fomit-frame-pointer'"
# ARG CMAKE_ARGS="-D PORTABLE=ON"

# ARG EVERYBEAM_BRANCH=v0.5.2
# RUN git clone --depth 1 --branch=${EVERYBEAM_BRANCH} --recurse-submodules https://git.astron.nl/RD/EveryBeam.git /EveryBeam && \
#     cd /EveryBeam && \
#     git submodule update --init --recursive && \
#     mkdir build && \
#     cd build && \
#     cmake $CMAKE_ARGS .. && \
#     make install -j`nproc` && \
#     cd / && \
#     rm -rf /EveryBeam

# ARG IDG_BRANCH=1.2.0
# RUN git clone --depth 1 --branch=${IDG_BRANCH} https://git.astron.nl/RD/idg.git /idg && \
#     cd /idg && \
#     git submodule update --init --recursive && \
#     mkdir build && \
#     cd build && \
#     cmake $CMAKE_ARGS .. && \
#     make install -j`nproc` && \
#     cd / && \
#     rm -rf /idg

# ARG WSCLEAN_BRANCH=v3.4
# RUN git clone --depth 1 --branch=${WSCLEAN_BRANCH} https://gitlab.com/aroffringa/wsclean.git /wsclean && \
#     cd /wsclean && \
#     git submodule update --init --recursive && \
#     mkdir build && \
#     cd build && \
#     cmake $CMAKE_ARGS .. && \
#     make install -j`nproc` && \
#     cd / && \
#     rm -rf /wsclean

# ARG GIANTSQUID_BRANCH=v1.0.3
# RUN git clone --depth 1 --branch=${GIANTSQUID_BRANCH} https://github.com/MWATelescope/giant-squid.git /giant-squid && \
#     cd /giant-squid && \
#     cargo install --path . --locked && \
#     cd / && \
#     rm -rf /giant-squid ${CARGO_HOME}/registry

# ARG AOFLAGGER_BRANCH=v3.4.0
# RUN git clone --depth 1 --branch=${AOFLAGGER_BRANCH} --recurse-submodules https://gitlab.com/aroffringa/aoflagger.git /aoflagger && \
#     cd /aoflagger && \
#     mkdir build && \
#     cd build && \
#     cmake $CMAKE_ARGS \
#     -DENABLE_GUI=OFF \
#     .. && \
#     make install -j`nproc` && \
#     ldconfig && \
#     cd / && \
#     rm -rf /aoflagger
# # set up aoflagger python library
# ENV PYTHONPATH="/usr/local/lib/:$PYTHONPATH"

# ARG BIRLI_GIT=https://github.com/MWATelescope/Birli.git
# ARG BIRLI_BRANCH=main
# RUN cargo install birli --locked --git=${BIRLI_GIT} --branch=${BIRLI_BRANCH} && \
#     rm -rf ${CARGO_HOME}/registry /opt/cargo/git/checkouts/

# ARG HYPERBEAM_GIT=https://github.com/MWATelescope/mwa_hyperbeam.git
# ARG HYPERBEAM_BRANCH=marlu0.14
# ARG HYPERBEAM_FEATURES=python
# # This won't install the python library:
# # RUN cargo install mwa_hyperbeam --locked --git=${HYPERBEAM_GIT} --branch=${HYPERBEAM_BRANCH} --features=${HYPERBEAM_FEATURES} && \
# #     rm -rf ${CARGO_HOME}/registry /opt/cargo/git/checkouts/
# RUN git clone --depth 1 --branch=${HYPERBEAM_BRANCH} ${HYPERBEAM_GIT} /hyperbeam && \
#     cd /hyperbeam && \
#     maturin build --locked --release --features=${HYPERBEAM_FEATURES} && \
#     python -m pip install $(ls -1 target/wheels/*.whl | tail -n 1) && \
#     rm -rf /hyperbeam ${CARGO_HOME}/registry

# ARG HYPERDRIVE_GIT=https://github.com/MWATelescope/mwa_hyperdrive.git
# # # HACK: birli0.14 needs newer ndarray
# # ARG HYPERDRIVE_BRANCH=main
# ARG HYPERDRIVE_BRANCH=birli0.14
# # TODO: ARG HYPERDRIVE_FEATURES=  ... --features=${HYPERDRIVE_FEATURES}
# RUN cargo install mwa_hyperdrive --locked --git=${HYPERDRIVE_GIT} --branch=${HYPERDRIVE_BRANCH} && \
#     rm -rf ${CARGO_HOME}/registry /opt/cargo/git/checkouts/

# # # HACK: beam_fits deserves its own feature branch
# # ARG HYPERDRIVE_BRANCH=marlu0.13
# # RUN git clone --depth 1 --branch=${HYPERDRIVE_BRANCH} https://github.com/MWATelescope/mwa_hyperdrive.git /hyperdrive && \
# #     cd /hyperdrive && \
# #     # mkdir -p src/hacks && \
# #     # wget -Osrc/hacks/beam_fits.rs https://raw.githubusercontent.com/MWATelescope/mwa_hyperdrive/refs/heads/SDC3/src/hacks/beam_fits.rs && \
# #     # wget -Osrc/hacks/mod.rs https://raw.githubusercontent.com/MWATelescope/mwa_hyperdrive/refs/heads/SDC3/src/hacks/mod.rs && \
# #     # sed -i '/mod cli;/a pub mod hacks;' src/lib.rs && \
# #     # cat src/lib.rs && \
# #     # wget -Osrc/cli/mod.rs https://raw.githubusercontent.com/MWATelescope/mwa_hyperdrive/refs/heads/SDC3/src/cli/mod.rs && \
# #     cargo install --path . --locked && \
# #     cd / && \
# #     rm -rf /hyperdrive ${CARGO_HOME}/registry

# # # download latest Leap_Second.dat, IERS finals2000A.all
# RUN python -c "from astropy.time import Time; t=Time.now(); from astropy.utils.data import download_file; download_file('http://data.astropy.org/coordinates/sites.json', cache=True); print(t.gps, t.ut1)"

# # # finufft
# # # RUN git clone https://github.com/flatironinstitute/finufft.git /finufft && \
# # #     cd /finufft && \
# # #     mkdir build && \
# # #     cd build && \
# # #     cmake $CMAKE_ARGS \
# # #     -DENABLE_GUI=OFF \
# # #     .. && \
# # #     make install -j`nproc`

# # Copy the demo files
# COPY ./demo /demo
# ENV PATH="/demo:${PATH}"
# WORKDIR /demo

# # HACK: the calibration fitting code in mwax_mover deserves its own public repo
# FROM d3vnull0/mwax_mover:latest as mwax_mover
# FROM base
# # Copy files from the previous mwax_mover stage into the final image
# COPY --from=mwax_mover /app /mwax_mover

# RUN cd /mwax_mover && \
#     python -m pip install .

# # # python /mwax_mover/scripts/cal_analysis.py \
# # # --name "${name}" \
# # # --metafits "${metafits}" --solns ${soln} \
# # # --phase-diff-path=/app/phase_diff.txt \
# # # --plot-residual --residual-vmax=0.5

# # # export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
# # # export raw="$(ls -1 ${outdir}/${obsid}/raw/${obsid}*.fits)"
# # # export soln=${outdir}/${obsid}/cal/hyp_soln_${obsid}.fits
# # # docker run --rm -it -v ${PWD}:${PWD} -w ${PWD} --entrypoint python mwatelescope/mwa-demo:latest /mwax_mover/scripts/cal_analysis.py --name foo --metafits ${metafits} --solns ${soln} --phase-diff-path=/mwax_mover/phase_diff.txt --plot-residual --residual-vmax=0.5
# # # docker run --rm -it -v ${PWD}:${PWD} -w ${PWD} --entrypoint python d3vnull0/mwax_mover:latest /app/scripts/cal_analysis.py --name foo --metafits ${metafits} --solns ${soln} --phase-diff-path=/app/phase_diff.txt --plot-residual --residual-vmax=0.5