#!/usr/bin/env python
# get the channel and antenna information from the metafits file

from mwalib import MetafitsContext
from pandas import DataFrame
import sys


def get_channel_df(ctx: MetafitsContext):
    header = [
        "gpubox_number",
        "rec_chan_number",
        "chan_start_hz",
        "chan_centre_hz",
        "chan_end_hz",
    ]
    df = DataFrame({h: [getattr(c, h) for c in ctx.metafits_coarse_chans] for h in header})
    return df


def get_antenna_df(ctx: MetafitsContext):
    header = [
        "ant",
        "tile_id",
        "tile_name",
        "electrical_length_m",
        "east_m",
        "north_m",
        "height_m",
    ]
    df = DataFrame({h: [getattr(a, h) for a in ctx.antennas] for h in header})
    df["flagged"] = [a.rfinput_x.flagged | a.rfinput_y.flagged for a in ctx.antennas]
    # get elements from antenna rfinput_x, assuming it's the same as rfinput_y
    rfheader = ["rec_number", "flavour", "has_whitening_filter"]
    for h in rfheader:
        df[h] = [getattr(a.rfinput_x, h) for a in ctx.antennas]
    # rec_type is "ReceiverType.RRI", I want just "RRI"
    df["rec_type"] = [str(a.rfinput_x.rec_type).replace("ReceiverType.", "") for a in ctx.antennas]
    return df


def main():
    metafits = sys.argv[-1]
    ctx = MetafitsContext(metafits)
    df_ch = get_channel_df(ctx)
    # where to put the channel and antenna info
    channels = metafits.replace(".metafits", "-channels.tsv")
    df_ch.to_csv(channels, index=False, sep="\t")
    print(f"wrote channels to {channels}")

    df_ant = get_antenna_df(ctx)
    antennas = metafits.replace(".metafits", "-antennas.tsv")
    df_ant.to_csv(antennas, index=False, sep="\t", float_format="%+8.3f")
    print(f"wrote antennas to {antennas}")


if __name__ == "__main__":
    main()
