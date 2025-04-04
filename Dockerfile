# syntax=docker/dockerfile:1
# cross-platform, cpu-only dockerfile for demoing MWA software stack
# on amd64, arm64
# ref: https://docs.docker.com/build/building/multi-platform/
FROM mwatelescope/hyperdrive:birli0.14 AS base

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
    ffmpeg \
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
    python3 \
    python3-pip \
    tzdata \
    unzip \
    vim \
    wget \
    wcslib-dev \
    libboost-python-dev \
    zip \
    && \
    apt-get clean all && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* && \
    apt-get -y autoremove

# if the python command does not exist, use python3 as the default
RUN command -v python || update-alternatives --install /usr/bin/python python /usr/bin/python3 1

# install giant-squid
RUN cargo install mwa_giant_squid --locked && \
    cargo clean && \
    rm -rf ${CARGO_HOME}/registry ${CARGO_HOME}/git

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
RUN python -m pip install --no-cache-dir --force-reinstall \
    'pyvo>=1.5.2' \
    'psutil>=6.0.0' \
    'docstring_parser>=0.15' \
    'astropy>=6.0' \
    'h5py>=3.4' \
    'numpy>=1.23' \
    'pyerfa>=2.0.1.1' \
    'pyyaml>=5.4.1' \
    'scipy>=1.8' \
    'setuptools_scm>=8.1' \
    'pyuvdata[casa]>=3.1.1' \
    'pandas>=2.2.3' \
    'matplotlib==3.9.0' \
    'python-casacore>=3.5.2' \
    git+https://github.com/mwilensky768/SSINS.git \
    git+https://github.com/d3v-null/mwa_qa.git@dev \
    git+https://github.com/PaulHancock/Aegean.git \
    git+https://github.com/tjgalvin/fits_warp.git

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

# # python /mwax_mover/scripts/cal_analysis.py \
# # --name "${name}" \
# # --metafits "${metafits}" --solns ${soln} \
# # --phase-diff-path=/mwax_mover/phase_diff.txt \
# # --plot-residual --residual-vmax=0.5

# # export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
# # export raw="$(ls -1 ${outdir}/${obsid}/raw/${obsid}*.fits)"
# # export soln=${outdir}/${obsid}/cal/hyp_soln_${obsid}.fits
# # docker run --rm -it -v ${PWD}:${PWD} -w ${PWD} --entrypoint python mwatelescope/mwa-demo:latest /mwax_mover/scripts/cal_analysis.py --name foo --metafits ${metafits} --solns ${soln} --phase-diff-path=/mwax_mover/phase_diff.txt --plot-residual --residual-vmax=0.5
# # docker run --rm -it -v ${PWD}:${PWD} -w ${PWD} --entrypoint python d3vnull0/mwax_mover:latest /app/scripts/cal_analysis.py --name foo --metafits ${metafits} --solns ${soln} --phase-diff-path=/app/phase_diff.txt --plot-residual --residual-vmax=0.5

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

ARG TEST_SHIM=""
RUN ${TEST_SHIM}

ENTRYPOINT /bin/bash