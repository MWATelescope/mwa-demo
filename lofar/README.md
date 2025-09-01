# LOFAR Scripts

These files are adapted from <https://github.com/kariukic/lofar-eor-demo/>

e.g.

```bash
docker run --rm -v ${PWD}:${PWD} -w ${PWD} -v ${outdir}:${outdir} mwa-demo
pip install click aoquality
export ms=${outdir}/1341914000/cal/hyp_cal_1341914000.ms
export name=${ms%.ms}
lofar/plot_flags.py plot_occ <(echo ${ms}) --filename ${name}
aoquality collect -d DATA $ms
lofar/plot_aoqstats.py plot_aoq ${ms} --name ${name}
```

```bash
export obsids_csv=${outdir:-demo/data/}obsids.csv
cat <<EOF > $obsids_csv
1060550888
1087596040
1088806248
1089238040
1090871744
1341914000
EOF
demo/02_download.sh
giant-squid submit-conv $obsids_csv -w \
  -p output=ms,avg_freq_res=80,avg_time_res=8
while read obsid; do
  export prep_vis=${outdir:-demo/data/}${obsid}/prep/${obsid}.ms
  if [[ ! -d "$prep_vis" && ! -f "$prep_vis" ]]; then
    echo "No MS found for $obsid, downloading preprocessed data"
    mkdir -p ${outdir:-demo/data/}${obsid}/prep
    giant-squid download -d $_ $obsid
  fi

  export name=${prep_vis%.ms}
  docker run --rm -v ${PWD}:${PWD} -w ${PWD} -v ${outdir}:${outdir} mwa-demo -lc "
    pip install click aoquality
    lofar/plot_flags.py plot_occ <(echo ${prep_vis}) --filename ${name}
    aoquality collect -d DATA $prep_vis
    lofar/plot_aoqstats.py plot_aoq ${prep_vis} --name ${name}
    "

  export name_export=${name}_export.ms
  docker run -it --rm -v ${PWD}:${PWD} -w ${PWD} -v${outdir}:${outdir} mwa-demo -lc "
    pip install click aoquality
    demo/04_ssins.py ${prep_vis} --no-diff --crosses --flags
    demo/04_ssins.py ${prep_vis} --diff --crosses --spectrum --export-ms
    demo/04_ssins.py ${prep_vis} --diff --crosses --sigchain

    aoflagger ${name_export}
    lofar/plot_flags.py plot_occ <(echo ${name_export}) --filename ${name_export}
    aoquality collect -d DATA ${name_export}
    lofar/plot_aoqstats.py plot_aoq ${name_export} --name ${name_export}
    demo/04_ssins.py ${name_export} --no-diff --crosses --spectrum
    demo/04_ssins.py ${name_export} --no-diff --crosses --flags
    demo/04_ssins.py ${name_export} --diff --crosses --spectrum"

done < $obsids_csv
```