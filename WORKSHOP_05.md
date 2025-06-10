# Workshop Part 5: Power spectrum

This workshop will demonstrate how to use CHIPS for power spectrum estimation.

We will skip the preprocessing and calibration steps, and download data with and without ionospheric correction.

We'll start with a known good observation, and then move on to a more challenging observation.

## Downloads

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

## Known good observation

TODO

add the following to `demo/00_env.sh`:

```bash
# TODO
```

and run the following:

```bash
export obsid=1069761080
demo/12_chips.sh
```
