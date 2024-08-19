# MWA Demo

## System Requirements

This demo runs best on a linux x86_64 machine with at least 16GB of RAM, and
20GB free disk space. macOS arm64 should work too. Windows users may need to
use WSL or Docker Desktop.

Some Windows users with 8GB of RAM have reported that the demo runs out of memory.
It may be necessary to close other programs you have open.

## Clone the repository

```bash
git clone https://github.com/MWATelescope/mwa-demo.git
cd mwa-demo
```

## Downloads

Download demo data (from Pawsey)

```bash
cd mwa-demo # or wherever the root of this repository is.
mkdir -p demo/data/1121334536/raw
curl -L -o demo/data/1121334536/raw/1121334536_20150719094841_gpubox20_00.fits 'https://projects.pawsey.org.au/mwa-demo/1121334536_20150719094841_gpubox20_00.fits?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=3bbbe461c87641ec9f4233718a7ca461%2F20240819%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20240819T040154Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=82b63ade9dcdf988a0eb46c6929d8ca6a328492545d1954150208e322f6bb757'
mkdir -p demo/data/1341914000/raw
curl -L -o demo/data/1341914000/raw/1341914000_20220715095302_ch137_000.fits 'https://projects.pawsey.org.au/mwa-demo/1341914000_20220715095302_ch137_000.fits?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=3bbbe461c87641ec9f4233718a7ca461%2F20240819%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20240819T040441Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Signature=8d2a1bc404878a1a7a777c942bd130072f40edc6d4234db39309a09e70d32d53'
```

Alternatively , you can download the same demo data from AWS:

```bash
curl -L -o mwa_demo2.zip 'https://mwa-project-meeting-2024.s3.ap-southeast-2.amazonaws.com/data/mwa_demo2.zip?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=ASIAUM6XOPSVEE5U3DUE%2F20240819%2Fap-southeast-2%2Fs3%2Faws4_request&X-Amz-Date=20240819T040249Z&X-Amz-Expires=604800&X-Amz-SignedHeaders=host&X-Amz-Security-Token=IQoJb3JpZ2luX2VjEDQaDmFwLXNvdXRoZWFzdC0yIkYwRAIgaQM6JEdCpgFn8jeSFLfg%2F92Ffybx5DR71TB%2B0DmadGwCICnFl1fPG3HYRQyANtudq2Y8avAg2PnuEYbVtphMc%2BZmKoAECD0QBRoMMzAyNzEwMTYwNTU0IgxqDGhQ2S2xpUkpyW0q3QMhvsdgqa9X%2FyxaTZS5wGWxe1intMHq2z%2FhZznPnizGBD%2BCEsA%2BR0JepBQ8zRu3AdLgtiljYLN8vknuBaYIyylriHMDTmIrjVsKuXNqfUfY6uuHkXQI6vJho9wwaMOANNu55y9F6Ph66xe7%2BOgdWwNtQsUVTDwYVejR%2FhZre0AZwzGhPmXlvi9HeBGqihy8VtgaQGBSQ0ROJaSdNrQ%2Btn64TOCMNN1xjLRMHVaFbGv1n7w57umm8Y1g%2B430OifvI3sMfub7rj7VVoKErDCwQCYZftvnwhpxwb0su2feva%2Buc4h1bvkgp%2F9qQi9ZNJCeAzr8DRb7MKy65WgB9s%2FWEcAC%2B06V9Le12J0VmSILMvbrNDMRLChlZmQoLQgQXMOQ0cfyRTrl3zUbLz9yK2gHiQ2nnMne0gHgT8rL4wC%2FMKaZvnK1bHyYwNkXSo5EbQ7DyDOXobhkFQXmnmo1c0c%2BUGJphejIhX6eDKdZB6M66TNC1oIe8VUBhzpMAnCksDlWo9M7qicHCPoyVC1sT1Cvmi1ZO03ZuFIh9nEOY5vSw873fThbNp0UWOVrj0pf94aaTauwdQVoBwldtqbl6rHla1%2BlXUvNraARU3Dv%2Bj%2B46i9%2FsyqMBdWzd2ISzXXxXq4wqvqKtgY6lQIFOAJtlr8pXfOPNOxzzYXRUmLgoZfz1OFr7tSpsNAzI%2FFtU5IVXctjKUJZu6xzuwTCVTbJ9c44Ts2yizpfwhD%2BJfQcAX%2BaM7E1kN07TJqyZ7oypmrLKJtAUBVyrX4SSsNUcau2tcHelMRgr7fW%2FYUKA4NTufdhooubebloPXegqW4fbU6r43rbOnfowSdUHYrpy8gnXGS0p0hKUU%2FRjGUG%2BXG7L2s0haaHp66dma1G9H6fk82D7UGJ5tDiGqGaUzGSscdFHZ9yNexFd4g0Zdw5aY1jv9vt70xmhg1UCppIdY0V11OIi86ZqxMgz3a6eoNIDnpd%2FROcvBHD9R43TPN22Oc7QcnSPCAyHR%2Bbaaq8IQlyTxzm&X-Amz-Signature=408b5e905a6355fe6ad393f8fe7e8ca0f6e071d0b24e0a0a3f8f45187c8f140f'

unzip -n demo2.zip # `-n` = do not replace pre-existing files
```

Third backup download [link](https://curtin-my.sharepoint.com/:u:/g/personal/285446d_curtin_edu_au/EQF1Dl93KixAimsD7wi7TcYBjAUs7Y6LO08An5rKSB2cmg?e=nMtGhu)

You may want to start downloading the docker images too.

```bash
# ... on macos arm64 (Apple Silicon, M series)
docker pull d3vnull0/mwa-demo:latest-arm64
# ... on linux amd64 (x86_64)
docker pull d3vnull0/mwa-demo:latest-amd64
```

## Software dependencies

There are several ways that you can provide the software dependencies to run this demo:

- bare metal: install everything to your local machine
- docker: run the software in Docker containers
- singularity: (todo!)

The scripts in this demo are designed for maximum flexibility. They evaluate environment variables
to dictate how to run each software package on your system, so you can use a mixture of
the methods above. For example:

```bash
# you can use the docker image
export giant_squid="docker run <arguments> mwatelescope/giant-squid"
# or the giant-squid binary if that is available on your system
export giant_squid="giant-squid"
# the script can handle either case
eval $giant_squid list
```

You can customize the Docker images in `demo/00_software.sh`, then source the file
in your shell before running the demo.

When your software environment is ready, you can test it by running `demo/00_test.sh`

### Bare Metal

you will need to install the following software.
For best results, use an x86 Linux machine.

- python 3.8 <https://www.python.org/downloads/>
  - pyvo <https://pyvo.readthedocs.io/en/latest/#installation>
  - mwalib <https://github.com/MWATelescope/mwalib/wiki/Installation%3A-Python-Users>
  - ssins <https://github.com/mwilensky768/SSINS?tab=readme-ov-file#installation>
  - mwa_qa `git clone https://github.com/d3v-null/mwa_qa.git ; pip install .`
- jq <https://jqlang.github.io/jq/download/>
- hyperdrive <https://mwatelescope.github.io/mwa_hyperdrive/installation/intro.html>
- giant-squid <https://github.com/MWATelescope/giant-squid?tab=readme-ov-file#installation>
- wsclean <https://wsclean.readthedocs.io/en/latest/installation.html>
  - recommended: EveryBeam <https://everybeam.readthedocs.io/en/latest/build-instructions.html>
  - recommended: IDG <https://idg.readthedocs.io/en/latest/build-instructions.html>

### Docker

A lightweight, cross-platform, cpu-only `Dockerfile` is provided which encapsulates
most of the software dependencies.

You can build this for your local platform with `docker build`, or for multiple
platforms using `docker buildx`. See Dockerfile for details.

```bash
# quick start: pull the images from dockerhub.
docker pull d3vnull0/mwa-demo:latest # on macos or linux arm64 (Apple M series), add --platform linux/arm64

# if you have any issues, you can override the image with a fresh build on your local machine
# docker rmi d3vnull0/mwa-demo:latest
docker build -t d3vnull0/mwa-demo:latest -f Dockerfile .

# If you still encounter issues on macOS arm64 (Apple Silicon, M series),
# the same image is also available via Docker x86_64 emulation. Make sure to update
# your Docker Desktop to the latest version, as this features is relatively new.
docker pull --platform linux/amd64 d3vnull0/mwa-demo:latest
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

# DEV: docker buildx build --platform linux/amd64,linux/arm64 -t d3vnull0/mwa-demo:latest -f Dockerfile --push .
```

### Windows

Some dependencies like casacore simply do not work on Windows, so you will need to use Docker or WSL.
The demo scripts are written for a Bash shell, and won't work in PowerShell or CMD.

This demo has been tested on Windows 11 with:

- Docker Desktop 4.33.1 on a Git Bash shell.

### ASVO account

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

### Customization

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

### Running the demo

Here is a walkthrough of the demo:

```bash
# DEMO: open a bash shell
# DEMO: change directory into the root of this repository.
# set up the software environment to use Docker for any binaries not on your system
source demo/00_software.sh
# check that everything is working (and pull Docker images)
demo/00_test.sh
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
eval $python ${SCRIPT_BASE}/04_ssins.py $prep_uvfits
eval $python ${SCRIPT_BASE}/04_ssins.py $cal_ms

# combine them all into a single image
obsid="combined" cal_ms=$(ls -1d ${outdir}/*/cal/hyp_cal_*.ms ) demo/07_img.sh

carta --top_level_folder . --browser 'open -a Google\ Chrome'

# clean up outdir to start fresh
demo/99_cleanup.sh
```
