# MWA Demo

## Data

download the demo data to the root of this repository from [here](https://curtin-my.sharepoint.com/:u:/g/personal/285446d_curtin_edu_au/EQF1Dl93KixAimsD7wi7TcYBjAUs7Y6LO08An5rKSB2cmg?e=nMtGhu)

`unzip -n demo2.zip` (`-n` = do not replace pre-existing files)

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
export giant_squid="docker run ... mwatelescope/giant-squid"
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
  - mwa_qa `git clone https://github.com/d3v-null/mwa_qa.git ; pip install mwa_qa`
- jq <https://jqlang.github.io/jq/download/>
- hyperdrive <https://mwatelescope.github.io/mwa_hyperdrive/installation/intro.html>
- giant-squid <https://github.com/MWATelescope/giant-squid?tab=readme-ov-file#installation>
- wsclean <https://wsclean.readthedocs.io/en/latest/installation.html>
  - recommended: EveryBeam <https://everybeam.readthedocs.io/en/latest/build-instructions.html>
  - recommended: IDG <https://idg.readthedocs.io/en/latest/build-instructions.html>

note: there is currently an issue binding to casacore on macOS arm64 (Apple Silicon, M series),
so hyperdrive and birli will only work via Docker x86_64 emulation

### Docker

A lightweight, cross-platform, cpu-only `Dockerfile` is provided which encapsulates
most of the software dependencies.

Some of the software requires emulation on arm64, for this you will likely need
to use a newer version of Docker. This
may require a newer version of macos.

You can build this for your local platform with `docker build`, or for multiple
platforms using `docker buildx`. See Dockerfile for details.

```bash
# quick start: pull the images from dockerhub
docker pull d3vnull0/mwa-demo:latest d3vnull0/mwa-demo-amd64:latest

# if you have any issues, you can override the image with a fresh build for your local platform
docker build -t d3vnull0/mwa-demo:latest -f Dockerfile .

# advanced: build the image for multiple platforms and push to dockerhub

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
export EVERYBEAM_VERSION=0.5.2
export IDG_VERSION=1.2.0
export WSCLEAN_VERSION=3.4
export tag=${DOCKER_USER}/mwa-demo:everybeam${EVERYBEAM_VERSION}-idg${IDG_VERSION}-wsclean${WSCLEAN_VERSION}
docker buildx build \
  -f Dockerfile \
  --platform linux/amd64,linux/arm64 \
  --build-arg="EVERYBEAM_VERSION=${EVERYBEAM_VERSION}" \
  --build-arg="IDG_VERSION=${IDG_VERSION}" \
  --build-arg="WSCLEAN_VERSION=${WSCLEAN_VERSION}" \
  -t $tag \
  --push \
  .

docker buildx build --platform linux/amd64,linux/arm64 -t d3vnull0/mwa-demo:latest -f Dockerfile .
docker build --platform linux/amd64 -t d3vnull0/mwa-demo-amd64:latest -f amd64.Dockerfile .
```

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
# set up the software environment
source demo/00_software.sh
# check that everything is working (and pull docker images)
demo/00_test.sh
# query the MWA TAP server with ADQL using the pyvo library
clear; demo/01_tap.sh
# display giant-squid commands to download observations
clear; demo/02_download.sh
# mwalib read observation metadata
demo/03_mwalib.sh
# SSINS find RFI
demo/04_ssins.sh
# Birli preprocess raw files, quality analysis
demo/05_prep.sh
# hyperdrive direciton independent calibrate, qa and apply solutions
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