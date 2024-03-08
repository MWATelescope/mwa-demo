#!/usr/bin/env python
# get the channel and antenna information from the metafits file

from mwalib import MetafitsContext
from pandas import DataFrame
import sys
metafits = sys.argv[-1]
# where to put the channel and antenna info
ctx = MetafitsContext(metafits)
header = ['gpubox_number', 'rec_chan_number', 'chan_start_hz', 'chan_centre_hz', 'chan_end_hz']
df = DataFrame({
    h: [getattr(c, h) for c in ctx.metafits_coarse_chans]
    for h in header
})
channels = metafits.replace('.metafits', '-channels.tsv')
df.to_csv(channels, index=False, sep='\t')
print(f"wrote channels to {channels}")

header=['ant', 'tile_id', 'tile_name', 'electrical_length_m', 'east_m', 'north_m', 'height_m']
df = DataFrame({
    h: [getattr(a, h) for a in ctx.antennas]
    for h in header
})
df['flagged'] = [a.rfinput_x.flagged | a.rfinput_y.flagged for a in ctx.antennas]
antennas = metafits.replace('.metafits', '-antennas.tsv')
df.to_csv(antennas, index=False, sep='\t')
print(f"wrote antennas to {antennas}")