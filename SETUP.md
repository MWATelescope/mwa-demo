# Setup instructions

## Setonix

If you are attending Radio School 2024 in person, you should have received an invite to create a
[Pawsey account](https://docs.google.com/document/d/1oEcX8glqemYe73wuqpHCyfGUCSO3PFmYOgecsUzces8/edit#heading=h.lgs4oa3svljd). Otherwise, the rest of this document will guide you through how to set up this workshop on another machine.

It is recommended that you register for an [MWA ASVO account](#asvo-account).

The workshop software has been installed for all members of the Radio School group (`pawsey1094`). You should check that you are a member of this group by logging in to Setonix and checking the `groups` command.

Setonix users will not need to download any data, however you will need to:

- [clone this repository](#clone)
- run [`demo/00_setonix.sh`](demo/00_setonix.sh) to set everything up
- run [`demo/00_test.sh`](demo/00_test.sh) to check everything is working

## Overview

- You will need access to install software on a system meeting the [system requirements](#system-requirements)
- [clone this repository](#clone)

## System Requirements

This demo runs best on a linux x86 machine with at least:

- 16GB of RAM
- 20GB free disk space

macOS x86 and arm (newer M-Series) will work, but CPU-only.

Windows users will need to use WSL2 or Docker Desktop with Git Bash.

## Clone

Clone this repository to a machine that meets the [system requirements](#system-requirements).

Setonix note: a good place for this is `$MYSOFTWARE` or `/software/projects/pawsey1094/${USER}/`

```bash
git clone https://github.com/MWATelescope/mwa-demo.git
cd mwa-demo
```

If you originally cloned this repository days before the workshop, it's a good idea
to check for updates right before the workshop starts with a `git pull`.

## Downloads

Each workshop in the demo uses different data sets. You can refer to the start of the [workshop instructions](README.md#workshops) for how to download that data, or download it yourself with [demo/01_download.sh](demo/01_download.sh) if you have an ASVO account.

## Software dependencies

There are several ways that you can provide the software dependencies to run this demo:

- *docker*: run the software in a Docker container (**recommended for new users!**)
- *bare metal*: install everything to your local machine (best for performance)
- *hybrid*: use a mix of Docker and local software (good balance)
- *singularity*: similar to Docker, but for shared HPC environments

The scripts in this demo are designed to be run from a Bash shell, with all
binaries available in `$PATH`.

When your software environment is ready, you can test it by running [`demo/00_test.sh`](demo/00_test.sh)

### Windows

Some dependencies like casacore simply do not work on Windows, so you will need to use Docker or WSL.
The scripts are written for a Bash shell, and won't work in PowerShell or CMD.

The demo has been tested on Windows 11 with Docker Desktop 4.33.1 on a Git Bash shell.

Some Windows users with 8GB of RAM have reported that the demo runs out of memory
running Docker withing WSL. It may be necessary to change

### Docker

A cross-platform, cpu-only [`Dockerfile`](Dockerfile) is provided which encapsulates all software
dependencies.

For maximum portability, generic Docker images have been built for the `linux/amd64` and
`linux/arm64` platforms, however neither take full advantage of the hardware acceleration
available on your machine. For maximum performance, you should follow the [bare metal](#bare-metal)
instructions.

[Windows](https://docs.docker.com/desktop/install/windows-install/) and
[macOS](https://docs.docker.com/desktop/install/mac-install/) users should install Docker Desktop.

Linux users should Carefully follow these [instructions](https://docs.docker.com/engine/install/)
to install Docker Engine. Debian and Ubuntu users may be tempted to install `docker` via snap, but
this is not recommended. I personally use the unofficial `docker.io` package available on apt.

Linux users should also ensure they have permissions to run docker without root:
`sudo usermod -aG docker $USER`

quick start: pull the images from dockerhub.

```bash
docker pull mwatelescope/mwa-demo:latest
```

When running the demo, you should run the commands in an interactive Docker shell.

```bash
docker run -it --rm -v ${PWD}:${PWD} -w ${PWD} -e MWA_ASVO_API_KEY=$MWA_ASVO_API_KEY mwatelescope/mwa-demo:latest
```

#### Docker Troubleshooting

macOS users: if you see this error: `WARNING: The requested image's platform (linux/amd64) does not match the detected host platform (linux/arm64/v8) and no specific platform was requested`, you should pull the image for the correct platform.

```bash
docker pull --platform linux/arm64 mwatelescope/mwa-demo:latest
```

If you have any issues, you should delete all traces of the image that was pulled and build the image locally. (this may take a while)

```bash
# first remove the image that was pulled from dockerhub
docker rmi mwatelescope/mwa-demo:latest
docker builder prune --all
docker buildx prune --all
docker build -t mwatelescope/mwa-demo:latest -f Dockerfile .
```

### Bare Metal

<!-- markdownlint-disable MD033 -->
<details>
  <summary>For advanced users</summary>

For optimal performance, you should compile the following software dependencies directly on your
machine.

Advanced users can provide additional compiler flags during the build process to optimize for their specific CPU micro-architecture. e.g. `-march=native` for C/C++, or `-C target-cpu=native` for Rust.

The steps in the [Dockerfile](Dockerfile) may be a useful guide.

- python 3.11+ <https://www.python.org/downloads/>
  - pyvo <https://pyvo.readthedocs.io/en/latest/#installation>
  - mwalib `pip install mwalib` <https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/348127236/mwalib>
  - ssins `pip install git+https://github.com/mwilensky768/SSINS.git` <https://github.com/mwilensky768/SSINS#installation>
  - mwa_qa `pip install git+https://github.com/d3v-null/mwa_qa.git@dev`
  - AegeanTools `pip install git+https://github.com/PaulHancock/Aegean.git` <https://aegeantools.rtfd.io/>
  - fits_warp `pip install psutil git+https://github.com/tjgalvin/fits_warp.git`
- jq <https://jqlang.github.io/jq/download/>
- AOFlagger <https://aoflagger.readthedocs.io/en/latest/installation.html>
- wsclean <https://wsclean.readthedocs.io/en/latest/installation.html>
  - recommended: EveryBeam <https://everybeam.readthedocs.io/en/latest/build-instructions.html>
  - recommended: IDG <https://idg.readthedocs.io/en/latest/build-instructions.html>
- rust <https://www.rust-lang.org/tools/install>
  - giant-squid <https://github.com/MWATelescope/giant-squid#installation>
  - Birli <https://github.com/MWATelescope/Birli#installation>
  - hyperdrive <https://mwatelescope.github.io/mwa_hyperdrive/installation/intro.html>

</details>

### Hybrid

<details>
  <summary>For advanced users</summary>

If you have some software dependencies installed locally, you can use Docker to run the rest.

This will create fake binaries in the `./bin` directory that just call Docker for any missing commands.

```bash
demo/00_hybrid.sh
export PATH=${PATH}:./bin/
```

This is probably bad practice for a production pipeline!

</details>

### Singularity

<details>
  <summary>For advanced users</summary>

Most HPC environments don't allow you to run Docker (for security reasons).
You can however run Docker images in Singularity.

```bash
singularity exec -B$PWD -B${outdir:-$PWD} -W$PWD --cleanenv docker://mwatelescope/mwa-demo:latest /bin/bash
```

</details>

## ASVO account

Please register for an ASVO account: [asvo.mwatelescope.org/registration](https://asvo.mwatelescope.org/registration)
Visibility data is made public 18 months after observation. For any support
enquiries, please email <asvo_support@mwatelescope.org>

Once you have your ASVO account, log in to <https://asvo.mwatelescope.org/profile>
to obtain your API key and set it as an environment variable:

```bash
export MWA_ASVO_API_KEY="..."
```

Detailed instructions here: <https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/24972779/MWA+ASVO+Command+Line+Clients#Finding-your-API-key>

you may want to add this to your `~/.bashrc` to persist it
across sessions, but remember to keep this key secret!

## Pre-workshop tests

The last step before the workshop is to check that everything is working.

```bash
demo/00_test.sh
```

Please ensure that:

- scripts are run from the root of the repository (don't `cd` into the `demo` directory).
- scripts are not sourced, and are run directly.
- (if [Docker](#docker)) you are in a Docker shell, not your host system.
- (if [hybrid](#hybrid)), you have run [`demo/00_hybrid.sh`](demo/00_hybrid.sh) and `export PATH=${PATH}:${PWD}/bin/`
- (if [singularity](#singularity)), you are in a Singularity shell, `singularity exec -B$PWD -W$PWD --cleanenv docker://mwatelescope/mwa-demo:latest /bin/bash`

## Customization

<details>
  <summary>For advanced users</summary>

You may wish to customize some of the other parameters in [`demo/00_env.sh`](demo/00_env.sh), e.g.:

- `$outdir` the output directory, where files are written. If you're extending
  this demo with more observations, you may want to put the files in a directory
  with more space.
- `$srclist` the
  [calibration sourcelist](https://mwatelescope.github.io/mwa_hyperdrive/defs/source_lists.html).
  Fits catalogue support (not fully tested) is available in
  [this branch](https://github.com/MWATelescope/mwa_hyperdrive/tree/issue-27)
- `$MWA_BEAM_FILE` the
  [beam model](https://mwatelescope.github.io/mwa_hyperdrive/defs/beam.html)

See also: [Extending The Demo](#extending-the-demo) for additional instructions for customizing the
docker images.

</details>

### Extending the demo

<details>
  <summary>For advanced users</summary>

If you extend the `Dockerfile`, you may want to publish your modified image for
multiple platforms using `docker buildx`.

```bash
# quick start: pull the images from dockerhub.
docker pull mwatelescope/mwa-demo:latest # on macos or linux arm64 (Apple M series), add --platform linux/arm64

# if you have any issues, you can override the image with a fresh build on your local machine
# docker rmi mwatelescope/mwa-demo:latest
docker build -t mwatelescope/mwa-demo:latest -f Dockerfile .

# If you still encounter issues on macOS arm64 (Apple Silicon, M series),
# the same image is also available via Docker x86_64 emulation. Make sure to update
# your Docker Desktop to the latest version, as this features is relatively new.
docker pull --platform linux/amd64 mwatelescope/mwa-demo:latest
```

Here's how to customize and build the image for multiple platforms and push to dockerhub

```bash
# (optional) get your docker username
docker login
export DOCKER_USER=$(docker info | sed '/Username:/!d;s/.* //');
if [ -z $DOCKER_USER ]; then
  export DOCKER_CREDSTORE=docker-credential-$(jq -r .credsStore ~/.docker/config.json);
  export DOCKER_USER=$( $DOCKER_CREDSTORE list | jq -r ' . | to_entries[] | select( .key | contains("docker.io") ) | last(.value)' )
fi

# create a new builder instance if not already created
docker buildx create --driver=docker-container --name=multi --use

# build the image for multiple platforms.
# - (optional) use build args to specify software versions.
# - use --push instead to push to dockerhub
# - or use --load to load the image into the local docker daemon
export EVERYBEAM_BRANCH="v0.5.2"
export IDG_BRANCH="v1.2.0"
export WSCLEAN_BRANCH="v3.4"
export tag=${DOCKER_USER}/mwa-demo:everybeam${EVERYBEAM_BRANCH}-idg${IDG_BRANCH}-wsclean${WSCLEAN_BRANCH}
docker buildx build \
  -f Dockerfile \
  --platform linux/amd64,linux/arm64 \
  --build-arg="EVERYBEAM_BRANCH=${EVERYBEAM_BRANCH}" \
  --build-arg="IDG_BRANCH=${IDG_BRANCH}" \
  --build-arg="WSCLEAN_BRANCH=${WSCLEAN_BRANCH}" \
  -t $tag \
  --push \
  .

# DEV: docker buildx build --platform linux/amd64,linux/arm64 -t mwatelescope/mwa-demo:latest -f Dockerfile --push .
```

If you add extra raw files, you can add their checksums with

```bash
md5sum demo/data/*/raw/1*_2*fits | tee demo_data.md5sum
```

</details>
