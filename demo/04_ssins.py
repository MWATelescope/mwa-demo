#!/usr/bin/env python
from SSINS import SS, INS, MF
import os, sys
import matplotlib as mpl
from matplotlib import pyplot as plt
import numpy as np
from astropy.time import Time

data_files = sys.argv[1:]
if len(data_files) > 1 and data_files[-1].endswith('.fits'):
    metafits = data_files[0]
    # output name is basename of metafits, or uvfits if provided
    base,_ = os.path.splitext(metafits)
elif len(data_files) == 1:
    vis = data_files[-1]
    base,_ = os.path.splitext(vis)
else:
    print(f"Usage: {sys.argv[:1]} <metafits> <data ...>")
    sys.exit(1)

# sky-subtract https://ssins.readthedocs.io/en/latest/sky_subtract.html
ss = SS()
cache = f"{base}.ssa.h5"
if os.path.exists(cache):
    print(f"reading from {cache=}")
    ss.read_uvh5(cache, read_data=True)
else:
    print(f"reading from {data_files=}")
    ss.read(
        data_files, read_data=True,
        diff=True,                              # difference timesteps
        remove_coarse_band=False,               # does not work with low freq res
        correct_van_vleck=False,                # slow
        remove_flagged_ants=True,               # remove flagged antennas
    )
    # just look at autos
    unflagged_ants = np.unique(ss.ant_1_array)
    ss=ss.select(antenna_nums=[(a,a) for a in unflagged_ants], inplace=False)
    ss.apply_flags(flag_choice='original')
    ss.write_uvh5(cache)
    print(f"wrote ss to {cache=}")

# incoherent noise spectrum https://ssins.readthedocs.io/en/latest/incoherent_noise_spectrum.html
ins = INS( ss, spectrum_type='auto' )

# match filter https://ssins.readthedocs.io/en/latest/match_filter.html
threshold=5
mf = MF(ss.freq_array[0], threshold, streak=True, narrow=False)
mf.apply_match_test(ins)
ins.sig_array[~np.isfinite(ins.sig_array)] = 0

# #### #
# PLOT #
# #### #
plt.style.use('dark_background')
cmap = mpl.colormaps.get_cmap('viridis')
cmap.set_bad(color='pink')

fontsize=8
figsize=(16, 16)
pols = ss.get_pols()
subplot_rows = 2

subplots = plt.subplots(
    subplot_rows, len(pols),
    figsize=figsize,
    sharex=True, sharey=True,
)[1]

time_labels = [*Time(np.unique(ss.time_array), format='jd').iso]
ntimes_visible = figsize[1] * 72 / fontsize / 2.4 / subplot_rows
time_stride = int(max(1, len(time_labels) // ntimes_visible))
chan_labels = [f'{ch: 8.3f}' for ch in ss.freq_array[0] / 1e6]
nchans_visible = figsize[0] * 72 / fontsize / 2.0 / len(pols)
chan_stride = int(max(1, len(chan_labels) // nchans_visible))
print(f'{time_stride=}, {chan_stride=}')

for i, pol in enumerate(ss.get_pols()):
    ax_met, ax_sig = subplots[:, i]

    ax_met.set_title(f'{base.split("/")[-1]} ss vis amps {pol}')
    ax_met.imshow(ins.metric_array[...,i], aspect='auto', interpolation='none', cmap=cmap)
    ax_sig.set_title(f'{base.split("/")[-1]} z-score {pol}')
    ax_sig.imshow(ins.sig_array[...,i], aspect='auto', interpolation='none', cmap=cmap)
    if i == 0:
        ax_met.set_ylabel('Timestep [UTC]')
        ax_met.set_yticks(np.arange(ss.Ntimes)[::time_stride])
        ax_met.set_yticklabels(time_labels[::time_stride], fontsize=fontsize, fontfamily='monospace')
        ax_sig.set_ylabel('Timestep [UTC]')
        ax_sig.set_yticks(np.arange(ss.Ntimes)[::time_stride])
        ax_sig.set_yticklabels(time_labels[::time_stride], fontsize=fontsize, fontfamily='monospace')

    ax_sig.set_xlabel('Frequency channel [MHz]')
    ax_sig.set_xticks(np.arange(ss.Nfreqs)[::chan_stride])
    ax_sig.set_xticklabels(chan_labels[::chan_stride], fontsize=fontsize, rotation=90)

figname = f'{base}.auto_spectrum.png'
plt.savefig(figname, bbox_inches='tight')
print(f"wrote {figname}")