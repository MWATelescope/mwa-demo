# syntax=docker/dockerfile:1
# cross-platform, cpu-only dockerfile for demoing MWA software stack
# on amd64, arm64
# ref: https://docs.docker.com/build/building/multi-platform/
# ARG BASE_IMG="ubuntu:20.04"
# HACK: newer python breaks on old ubuntu
FROM mwatelescope/hyperdrive:latest-python3.11-slim-bookworm AS base

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
    g++ \
    jq \
    lcov \
    libatlas3-base \
    libblas-dev \
    libboost-date-time-dev \
    libboost-filesystem-dev \
    libboost-program-options-dev \
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
    libpng-dev \
    libssl-dev \
    libxml2-dev \
    pkg-config \
    procps \
    tzdata \
    unzip \
    wget \
    zip \
    && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    apt-get -y autoremove

RUN cargo install mwa_giant_squid --locked && \
    rm -rf ${CARGO_HOME}/registry /opt/cargo/git/checkouts/

# for example, CMAKE_ARGS="-D CMAKE_CXX_FLAGS='-march=native -mtune=native -O3 -fomit-frame-pointer'"
ARG CMAKE_ARGS="-DPORTABLE=True"

ARG EVERYBEAM_BRANCH=v0.6.1
RUN git clone --depth 1 --branch=${EVERYBEAM_BRANCH} --recurse-submodules https://git.astron.nl/RD/EveryBeam.git /EveryBeam && \
    cd /EveryBeam && \
    git submodule update --init --recursive && \
    mkdir build && \
    cd build && \
    cmake $CMAKE_ARGS .. && \
    make install -j`nproc` && \
    cd / && \
    rm -rf /EveryBeam

ARG IDG_BRANCH=1.2.0
RUN git clone --depth 1 --branch=${IDG_BRANCH} https://git.astron.nl/RD/idg.git /idg && \
    cd /idg && \
    git submodule update --init --recursive && \
    mkdir build && \
    cd build && \
    cmake $CMAKE_ARGS .. && \
    make install -j`nproc` && \
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
    make install -j`nproc` && \
    cd / && \
    rm -rf /wsclean

# install python prerequisites
ARG SSINS_BRANCH=master
ARG MWAQA_BRANCH=dev
RUN python -m pip install --no-cache-dir \
    pyvo==1.5.2 \
    git+https://github.com/mwilensky768/SSINS.git@${SSINS_BRANCH} \
    git+https://github.com/d3v-null/mwa_qa.git@${MWAQA_BRANCH} \
    git+https://github.com/PaulHancock/Aegean.git \
    git+https://github.com/tjgalvin/fits_warp.git \
    ;

# # download latest Leap_Second.dat, IERS finals2000A.all
RUN python -c "from astropy.time import Time; t=Time.now(); from astropy.utils.data import download_file; download_file('http://data.astropy.org/coordinates/sites.json', cache=True); print(t.gps, t.ut1)"

# Copy the demo files
COPY ./demo /demo
ENV PATH="/demo:${PATH}"
WORKDIR /demo

# RUN <<EOF
# #!/usr/bin/env python
# import sys
# from sys import implementation, stdout
# print( f"{implementation=}", file=stdout)
# EOF

# # HACK: the calibration fitting code in mwax_mover deserves its own public repo
FROM d3vnull0/mwax_mover:latest AS mwax_mover
FROM base
# # Copy files from the previous mwax_mover stage into the final image
COPY --from=mwax_mover /app /mwax_mover

RUN cd /mwax_mover && \
    python -m pip install .

# # python /mwax_mover/scripts/cal_analysis.py \
# # --name "${name}" \
# # --metafits "${metafits}" --solns ${soln} \
# # --phase-diff-path=/app/phase_diff.txt \
# # --plot-residual --residual-vmax=0.5

# # export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
# # export raw="$(ls -1 ${outdir}/${obsid}/raw/${obsid}*.fits)"
# # export soln=${outdir}/${obsid}/cal/hyp_soln_${obsid}.fits
# # docker run --rm -it -v ${PWD}:${PWD} -w ${PWD} --entrypoint python mwatelescope/mwa-demo:latest /mwax_mover/scripts/cal_analysis.py --name foo --metafits ${metafits} --solns ${soln} --phase-diff-path=/mwax_mover/phase_diff.txt --plot-residual --residual-vmax=0.5
# # docker run --rm -it -v ${PWD}:${PWD} -w ${PWD} --entrypoint python d3vnull0/mwax_mover:latest /app/scripts/cal_analysis.py --name foo --metafits ${metafits} --solns ${soln} --phase-diff-path=/app/phase_diff.txt --plot-residual --residual-vmax=0.5

ARG TEST_SHIM=""
RUN ${TEST_SHIM}

ENTRYPOINT /bin/bash