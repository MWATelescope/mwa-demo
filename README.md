# MWA Demo

Demonstration pipeline for Murchison Widefield Array (MWA) data

## Flow

```mermaid
flowchart TD;
classDef in fill:#2aa198;
classDef out fill:#d33682;
classDef file fill:#268bd2;
classDef proc fill:#b58900;
classDef decision fill:#cb4b16;

subgraph s01 ["01. TAP"]
  mwaTap([fa:fa-search MWA TAP ]); class mwaTap in;
  obsids[/"fa:fa-table obsids.csv "/]; class obsids file;
  mwaTap --> obsids;
end

subgraph s02 ["02. Download"]
  mwaAsvo([fa:fa-download MWA ASVO]); class mwaAsvo in;
  giant-squid[[fa:fa-download giant-squid ]]; class giant-squid proc;
  raw[/ fa:fa-file raw data /]; class raw file;
  metafits[/ fa:fa-file metafits /]; class metafits file;
  obsids --> giant-squid --> mwaAsvo --> raw & metafits;
end

subgraph s03 ["03. MWALib"]
  mwalib[[fa:fa-wrench MWALib]]; class mwalib proc;
  mwalibOut[/fa:fa-table antennas and channels /]; class mwalibOut file;
  %% channels[/fa:fa-table channels.csv/]; class channels file;
  metafits --> mwalib --> mwalibOut;
end

subgraph s04 ["04. SSINS"]
  ssins[[fa:fa-flag SSINS]]; class ssins proc;
  flags[/fa:fa-file-image flag plots/]; class flags file;
  raw & metafits --> ssins --> flags;
end

s02 -.....->|raw| s05

subgraph s05 ["05. Preprocess"]
  birli[[fa:fa-bolt Birli ]]; class birli proc;
  prepUVFits[/fa:fa-file preprocessed uvfits /]; class prepUVFits file;
  prepQA[[fa:fa-gem prepQA]]; class prepQA proc;
  prepQAJson[/fa:fa-file-code prepQA json /]; class prepQAJson file;
  %% local copy of metafits and raw to simplify graph
  metafits05[/fa:fa-file metafits /]; class metafits05 file;
  raw05[/ fa:fa-file raw data /]; class raw05 file;

  metafits05 & raw05 --> birli --> prepUVFits;
  metafits05 & prepUVFits --> prepQA --> prepQAJson;
end

subgraph s06 ["06. calibrate"]
  hypCalSol[[fa:fa-wrench hyperdrive di-cal]]; class hypCalSol proc
  calSol[/fa:fa-file-excel cal solutions/]; class calSol file
  prepUVFits[/fa:fa-file prep uvfits/]; class prepUVFits file
  calQA[[fa:fa-gem calQA]]; class calQA proc;
  calQAJson[/"fa:fa-file calqa.json "/]; class calQAJson file
  plotSolutions[[fa:fa-gem hyperdrive solutions-plot]]; class plotSolutions proc
  plotSol[/"fa:fa-file-image solution plots "/]; class plotSol file
  hypApply[[fa:fa-times-circle hyperdrive solutions-apply ]]; class hypApply proc
  calMS[/fa:fa-file calibrated CASA Measurement Set /]; class calMS file
  %% local copy of metafits to simplify graph
  metafits06[/fa:fa-file metafits /]; class metafits06 file;

  metafits06 --> hypCalSol
  prepUVFits -----> hypCalSol --> calSol
  metafits06 & calSol --> calQA --> calQAJson
  metafits06 & calSol --> plotSolutions --> plotSol

  calQAJson -.->|bad antennas| hypApply
  calSol & prepUVFits --> hypApply --> calMS
end

subgraph s07 ["07. image"]
  imgDConv[/"fa:fa-file-image wsclean*.fits "/]; class imgDConv file
  wscleanDConv[[fa:fa-image wsclean ]]; class wscleanDConv proc
  %% imgMetricsJson[/fa:fa-file img_metrics.json /]; class imgMetricsJson file
  %% imgQA[[fa:fa-gem imgQA]]; class imgQA proc;
  calMS --> wscleanDConv --> imgDConv
  %% --> imgQA --> imgMetricsJson
end
```

## System Requirements

This demo runs best on a linux amd64 (x86_64) machine with at least:

- 16GB of RAM
- 20GB free disk space

macOS amd64 (Intel) and arm64 (M-Series) will work, but CPU-only.

Windows users will need to use WSL2 or Docker Desktop with Git Bash.

Some Windows users with 8GB of RAM have reported that the demo runs out of memory
running Docker withing WSL. It may be necessary to change

## Setup

Clone this repository to a machine that meets the [system requirements](#system-requirements).

```bash
git clone https://github.com/MWATelescope/mwa-demo.git
cd mwa-demo
```

## Downloads

Download demo data (from Pawsey). You should be in the root of the repository.

```bash
mkdir -p demo/data/1121334536/raw
curl -L -o demo/data/1121334536/raw/1121334536_20150719094841_gpubox20_00.fits 'https://projects.pawsey.org.au/mwa-demo/1121334536_20150719094841_gpubox20_00.fits'
mkdir -p demo/data/1341914000/raw
curl -L -o demo/data/1341914000/raw/1341914000_20220715095302_ch137_000.fits 'https://projects.pawsey.org.au/mwa-demo/1341914000_20220715095302_ch137_000.fits'
```

Alternatively , you can download the same demo data in your browser [here](https://curtin-my.sharepoint.com/:u:/g/personal/285446d_curtin_edu_au/EQF1Dl93KixAimsD7wi7TcYBjAUs7Y6LO08An5rKSB2cmg?e=nMtGhu) and extract it to the `demo/data` directory.

```bash
unzip -n demo2.zip # -n = do not replace pre-existing files
```

## Software dependencies

There are several ways that you can provide the software dependencies to run this demo:

- docker: run the software in a Docker container (best portability)
- bare metal: install everything to your local machine (best performance)
- hybrid: use a mix of Docker and local software (advanced)

The scripts in this demo are designed to be run from a Bash shell, with all
binaries available in `$PATH`.

When your software environment is ready, you can test it by running `demo/00_test.sh`

### Windows

Some dependencies like casacore simply do not work on Windows, so you will need to use Docker or WSL.
The scripts are written for a Bash shell, and won't work in PowerShell or CMD.

The demo has been tested on Windows 11 with Docker Desktop 4.33.1 on a Git Bash shell.

### Bare Metal

For optimal performance, you should compile the following software dependencies directly on your
machine.

Advanced users can provide additional compiler flags during the build process to optimize for their specific CPU micro-architecture. e.g. `-march=native` for C/C++, or `-C target-cpu=native` for Rust.

The steps in the `Dockerfile` may be a useful guide.

- python 3.8+ <https://www.python.org/downloads/>
  - pyvo <https://pyvo.readthedocs.io/en/latest/#installation>
  - mwalib <https://github.com/MWATelescope/mwalib/wiki/Installation%3A-Python-Users>
  - ssins <https://github.com/mwilensky768/SSINS#installation>
  - mwa_qa `git clone https://github.com/d3v-null/mwa_qa.git ; pip install .`
- jq <https://jqlang.github.io/jq/download/>
- AOFlagger <https://aoflagger.readthedocs.io/en/latest/installation.html>
- wsclean <https://wsclean.readthedocs.io/en/latest/installation.html>
  - recommended: EveryBeam <https://everybeam.readthedocs.io/en/latest/build-instructions.html>
  - recommended: IDG <https://idg.readthedocs.io/en/latest/build-instructions.html>
- rust <https://www.rust-lang.org/tools/install>
  - giant-squid <https://github.com/MWATelescope/giant-squid#installation>
  - Birli <https://github.com/MWATelescope/Birli#installation>
  - hyperdrive <https://mwatelescope.github.io/mwa_hyperdrive/installation/intro.html>

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

When [running the demo](#running-the-demo), you should run the commands in an interactive Docker shell.

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

### Hybrid

If you have some software dependencies installed locally, you can use Docker to run the rest. Just comment out the packages you don't need in `demo/00_software.sh` and source it in your shell.

```bash
source demo/00_software.sh
```

## ASVO account

Please register for an ASVO account: [asvo.mwatelescope.org/registration](https://asvo.mwatelescope.org/registration)
Visibility data is made public 18 months after observation. For any support
enquiries, please email <asvo_support@mwatelescope.org>

Once you have your ASVO account, log in to <https://asvo.mwatelescope.org/profile>
to obtain your API key and set it as an environment variable:

```bash
export MWA_ASVO_API_KEY="..."
```

you may want to add this to your `~/.bashrc` to persist it
across sessions, but remember to keep this key secret!

## Customization

You may wish to customize some of the other parameters in `demo/00_env.sh`, e.g.:

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

### Running the demo

Below is a walkthrough of the demo. Ensure that:

- (if using [Docker](#docker)) you are in a Docker shell, not your host system.
- (if [hybrid](#hybrid)), you have sourced `demo/00_software.sh` in your host shell.
- everything is run from the root of the repository
  (don't `cd` into the `demo` directory).
- you don't `source` the scripts, they are `chmod +x` and should be run directly.

```bash
# check that everything is working
demo/00_test.sh # don't source me!
# query the MWA TAP server with ADQL using the pyvo library
clear; demo/01_tap.sh
# display giant-squid commands to download observations
clear; demo/02_download.sh
# mwalib read observation metadata
demo/03_mwalib.sh
# SSINS find RFI
demo/04_ssins.sh
# Birli preprocess raw files, quality analysis, write uvfits
demo/05_prep.sh
# hyperdrive direction independent calibrate, qa, apply solutions, write measurement set
demo/06_cal.sh
# wsclean cal_ms
demo/07_img.sh
# done

for obsid in 1341914000 1121334536; do
  demo/05_prep.sh && demo/06_cal.sh && demo/07_img.sh || break
done

# DEMO: The images look a bit weird, let's enable calqa flags and try again.
# uncomment this line in 00/06_cal.sh to apply bad antennas and see how the image changes!
# export cal_bad_ants=""
rm -rf $outdir/{1341914000,combined}/{cal,img}

# did aoflagger really get all the RFI?
export obsid=1341914000
# export obsid=1121334536
export metafits=${outdir}/${obsid}/raw/${obsid}.metafits
export prep_uvfits="${outdir}/${obsid}/prep/birli_${obsid}.uvfits"
export cal_ms="${outdir}/${obsid}/cal/hyp_cal_${obsid}.ms"
python ${SCRIPT_BASE}/04_ssins.py $prep_uvfits
python ${SCRIPT_BASE}/04_ssins.py $cal_ms

# combine them all into a single image
obsid="combined" cal_ms=$(ls -1d ${outdir}/*/cal/hyp_cal_*.ms ) demo/07_img.sh

carta --top_level_folder . --browser 'open -a Google\ Chrome'

# clean up outdir to start fresh
demo/99_cleanup.sh
```

## Extending the demo

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
md5sum demo/data/*/raw/1*fits | tee demo_data.md5sum
```
