# Workshop Part 5: Power spectrum

This workshop will demonstrate how to use CHIPS for power spectrum estimation.

We will skip the preprocessing and calibration steps, and download data with and without ionospheric correction.

We'll start with a known good observation, and then move on to a more challenging observation.

## Downloads / Setup

run the these before the workshop:

```bash
export obsid=1069761080
export outdir=${outdir:-${PWD}/demo/data/}
mkdir -p ${outdir}/${obsid}/{cal,peel}
# ssins flagging and calibration, no ionospheric subtraction
wget -O ${outdir}/1069761080/cal/hyp_1069761080_ssins_30l_src8k_300it_8s_80kHz.uvfits https://projects.pawsey.org.au/high0.uvfits/hyp_1069761080_ssins_30l_src8k_300it_8s_80kHz.uvfits
# ssins flagging, calibration ionospheric subtraction
wget -O ${outdir}/1069761080/peel/hyp_1069761080_ionosub_ssins_30l_src8k_300it_8s_80kHz_i1000.uvfits https://projects.pawsey.org.au/high0.uvfits/hyp_1069761080_ionosub_ssins_30l_src8k_300it_8s_80kHz_i1000.uvfits
# pull the latest mwa-demo image
docker pull mwatelescope/mwa-demo:latest
```

See [SETUP.md](SETUP.md) for setup options, but for a quick start, the following commands should be run in a shell from  the docker image (via Singularity if you're on HPC).

```bash
# quickstart
docker run -it --rm -v ${PWD}:${PWD} -w ${PWD} mwatelescope/mwa-demo:main
```

Note: the baremetal instructions won't work for running CHIPS on macOS yet, so your best bet is to use the docker image (via Singularity if you're on HPC).

note: CHIPS grids take up a lot of disk space.
Each 2GB input file will produce 100GB of grids.

## Known good observation

run the following:

```bash
export obsid=1069761080
export uvf_pattern=${outdir}/${obsid}/cal/hyp_${obsid}_ssins_30l_src8k_300it_8s_80kHz.uvfits
demo/12_chips.sh
export uvf_pattern=${outdir}/${obsid}/peel/hyp_${obsid}_ionosub_ssins_30l_src8k_300it_8s_80kHz_i1000.uvfits
demo/12_chips.sh
```
