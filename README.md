# mwa-nextflow-starter
Nextflow template for MWA processing. Simplified version of <https://github.com/MWATelescope/MWAEoR-Pipeline>

## Demo

### Data

download the demo data to the root of this repository from <https://curtin-my.sharepoint.com/:u:/g/personal/285446d_curtin_edu_au/EQF1Dl93KixAimsD7wi7TcYBjAUs7Y6LO08An5rKSB2cmg?e=nMtGhu>

`unzip demo2.zip` and do not replace `demo/demo00_check.sh` if prompted

```
Archive:  demo2.zip
  inflating: demo/data/1121334536/raw/1121334536_20150719094841_gpubox20_00.fits
  inflating: demo/data/1341914000/raw/1341914000_20220715095302_ch137_000.fits
  inflating: demo/data/1121334536/raw/1121334536.metafits
  inflating: demo/data/1341914000/raw/1341914000.metafits
replace demo/demo00_check.sh? [y]es, [n]o, [A]ll, [N]one, [r]ename: n
```

There are several ways that you can run these demo scripts:
- bare metal: install everything to your local machine
- docker
- singularity
