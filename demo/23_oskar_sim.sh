#!/bin/bash
# simulate one telescope configuration with OSKAR, write a MeasurementSet (MSv2)
# details: https://ska-telescope.gitlab.io/sim/oskar/
# runs inside the OSKAR container, e.g.
#   docker run --rm -v $PWD:$PWD -w $PWD fdulwich/oskar-python3:2.12.0 demo/23_oskar_sim.sh

# ### #
# ENV #
# ### #
# not sourcing 00_env.sh: the OSKAR image has no MWA tools
export outdir=${outdir:-${PWD}/demo/data/}
export oskar_dir=${oskar_dir:-${outdir}/oskar}
# configuration: aa2, mwa256t or aa2_mwa256t (case h)
export config=${config:-aa2}
export telescope=${telescope:-${oskar_dir}/telescopes/${config}.tm}
export sky=${sky:-${oskar_dir}/sky/eor1_negdec.osm}
# phase centre: EoR1
export ra_deg=${ra_deg:-60.0}
export dec_deg=${dec_deg:--27.0}
# observation: 2 minutes of 8 s, centred on transit on 2000-01-01 (SP-5941's date)
export duration_s=${duration_s:-120}
export dt_s=${dt_s:-8}
export obs_date=${obs_date:-2000-01-01}
# transit is computed at the SKA-Low (AA2) reference longitude for every
# configuration, so that all three simulations share the same time stamps
export transit_lon_deg=${transit_lon_deg:-116.7644482}
# 140-160 MHz in 48 kHz channels (SP-5941: 416 channels from 140.000 MHz)
export freq_start_hz=${freq_start_hz:-140e6}
export freq_inc_hz=${freq_inc_hz:-48e3}
export num_channels=${num_channels:-416}
# to spread one simulation over more cores, run several sub-bands at once
# (first_channel=0 num_channels=208, first_channel=208 num_channels=208, ...)
# then join them with 23_oskar_concat.sh
export first_channel=${first_channel:-0}
# ionosphere: TEC screen from 22_oskar_tec_screen.py, "none" to disable
export tec_screen=${tec_screen:-${oskar_dir}/screen/tec_${duration_s}s.fits}
export screen_height_km=${screen_height_km:-300}
# only simulate sources brighter than this (Jy at 144 MHz), "min" for all.
# 10 mJy keeps 12,414 of 125,988 sources: 86% of the flux, 99.97% of sum(I^2)
export flux_min=${flux_min:-0.01}
# bandwidth and time-average smearing
export smearing=${smearing:-true}
# OSKAR's CPU "devices" are threads, each simulating one time sample of a
# block, so at most one thread per time step is busy. OpenMP inside each
# device only oversubscribes the CPU: keep it at 1.
export num_threads=${num_threads:-$(nproc)}
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-1}
# SP-5941 recorded a 38 m dish diameter; MWA tiles are ~4.4 m across
case $config in
    mwa256t) export dish_diameter=${dish_diameter:-4.4} ;;
    *) export dish_diameter=${dish_diameter:-38} ;;
esac
export sim_name=${sim_name:-${config}_${duration_s}s}
if [[ $first_channel != 0 || $num_channels != 416 ]]; then
    export sim_name="${sim_name}_ch${first_channel}+${num_channels}"
fi
export ms=${ms:-${oskar_dir}/vis/${sim_name}.ms}

set -euo pipefail
if [[ "$tec_screen" != "none" && ! -f "$tec_screen" ]]; then
    echo "tec_screen=$tec_screen not found, run 22_oskar_tec_screen.py"
    exit 1
fi

num_times=$((duration_s / dt_s))
# start time: transit of the phase centre minus half the duration
start_utc=${start_utc:-$(python3 - <<EOF
import numpy as np
from astropy import units as u
from astropy.coordinates import EarthLocation
from astropy.time import Time
loc = EarthLocation.from_geodetic(${transit_lon_deg} * u.deg, -26.8 * u.deg)
t0 = Time("${obs_date}T00:00:00", scale="utc", location=loc)
lst0 = t0.sidereal_time("apparent").deg
dt_sid = ((${ra_deg} - lst0) % 360) / 360.0 * 86164.0905
start = t0 + (dt_sid - ${duration_s} / 2) * u.s
print(start.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3])
EOF
)}

mkdir -p "$(dirname "$ms")"
ini="${ms%.ms}.ini"
rm -f "$ini"
touch "$ini"
set_key() { oskar_sim_interferometer -q --set "$ini" "$1" "$2"; }
set_key simulator/use_gpus false
set_key simulator/num_devices "$num_threads"
set_key simulator/double_precision "${double_precision:-true}"
set_key sky/oskar_sky_model/file "$sky"
set_key sky/oskar_sky_model/filter/flux_min "$flux_min"
set_key observation/phase_centre_ra_deg "$ra_deg"
set_key observation/phase_centre_dec_deg "$dec_deg"
set_key observation/start_frequency_hz "$(python3 -c "print(${freq_start_hz} + ${first_channel} * ${freq_inc_hz})")"
set_key observation/num_channels "$num_channels"
set_key observation/frequency_inc_hz "$freq_inc_hz"
set_key observation/start_time_utc "$start_utc"
set_key observation/length "$duration_s"
set_key observation/num_time_steps "$num_times"
set_key telescope/input_directory "$telescope"
set_key telescope/normalise_beams_at_phase_centre true
set_key telescope/pol_mode Full
if [[ "$tec_screen" != "none" ]]; then
    set_key telescope/ionosphere_screen_type External
    set_key telescope/external_tec_screen/input_fits_file "$tec_screen"
    set_key telescope/external_tec_screen/screen_height_km "$screen_height_km"
fi
if [[ "$smearing" == "true" ]]; then
    set_key interferometer/channel_bandwidth_hz "$freq_inc_hz"
    set_key interferometer/time_average_sec "$dt_s"
fi
set_key interferometer/correlation_type Cross-correlations
set_key interferometer/max_time_samples_per_block "$(( num_times < num_threads ? num_times : num_threads ))"
set_key interferometer/ms_dish_diameter "$dish_diameter"
set_key interferometer/ms_filename "$ms"
cat "$ini"

rm -rf "$ms"
SECONDS=0
oskar_sim_interferometer "$ini" 2>&1 | tee "${ms%.ms}.log"
echo "oskar_sim_interferometer took ${SECONDS} s with ${num_threads} threads" | tee -a "${ms%.ms}.log"
du -sh "$ms" | tee -a "${ms%.ms}.log"
