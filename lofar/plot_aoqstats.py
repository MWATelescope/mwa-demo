#!/usr/bin/env python
"""
Plot aoquality statistics.

source: https://github.com/kariukic/lofar-eor-demo/blob/main/templates/plot_aoqstats.py
"""

import aoquality as ao
import click
import matplotlib.pyplot as plt
import numpy as np


class QualityStats:
    """Helper for reading and plotting AOQuality statistics."""

    def __init__(self, qs_file, name, plot_crosses=False):
        """Initialize the plotter.

        Args:
            qs_file: Path to an AOQuality HDF5/NPZ file.
            name: Output name prefix for saved figures.
            plot_crosses: If True, include cross-pol XY/YX plots.
        """
        self.qs_file = qs_file
        self.name = name
        self.plot_crosses = plot_crosses
        self.pols = ["XX", "XY", "YX", "YY"]

    def pol_idx(self):
        """Return indices of polarisations to plot.

        Returns
        -------
            List[int]: `[0, 1, 2, 3]` if including crosses, else `[0, 3]`.
        """
        return [0, 1, 2, 3] if self.plot_crosses else [0, 3]

    def get_available_stats(self):
        """Describe the available statistics and their display metadata."""
        return {
            "Mean": {"label": "Vis. Mean", "xfactor": 1, "units": "Jy"},
            "SNR": {"label": "Vis. SNR", "xfactor": 1, "units": None},
            "Std": {"label": "Vis Std", "xfactor": 1, "units": "Jy"},
            "DStd": {"label": "Vis. Dstd", "xfactor": 1, "units": "Jy"},
            "RFIPercentage": {"label": "Flagged vis.", "xfactor": 1e2, "units": r"%"},
        }

    def plot_freq_qstats(self):
        """Plot statistics versus frequency and save a summary PDF."""
        aof = ao.AOQualityFrequencyStat(self.qs_file)
        stats = self.get_available_stats()

        fig, axes = plt.subplots(nrows=3, ncols=2, figsize=(12, 8), sharex=True)
        axes = axes.ravel()
        for k, stat in enumerate(stats.keys()):
            for p in self.pol_idx():
                axes[k].plot(
                    aof.freqs / 1e6,
                    aof.get_stat(stat)[:, p] * stats[stat]["xfactor"],
                    label=self.pols[p],
                )
            axes[k].set_ylabel(f"{stats[stat]['label']} ({stats[stat]['units']})")
            axes[k].set_title(stat)
            # axes[k].set_yscale("log")
            axes[k].legend()
        for ax in axes[-3:]:
            ax.set_xlabel("Frequency (MHz)")
        axes[-1].remove()
        fig.tight_layout()
        plt.savefig(f"{self.name}_aoq_frequency_stats.pdf", bbox_inches="tight")
        plt.show()
        plt.close(fig)
        return

    def plot_time_qstats(self):
        """Plot statistics versus time (averaged over frequency) and save a PDF."""
        aot = ao.AOQualityTimeStat(self.qs_file)
        stats = self.get_available_stats()

        fig, axes = plt.subplots(nrows=3, ncols=2, figsize=(16, 8), sharex=True)
        axes = axes.ravel()

        time = np.unique(aot.time)
        ntimesteps = time.shape[0]
        duration_sec = time[-1] - time[0]
        divisor = 3600 if duration_sec > 3600 else 60
        time = np.linspace(0, duration_sec, ntimesteps) / divisor

        for k, stat in enumerate(stats.keys()):
            for p in self.pol_idx():
                data = np.nanmean(
                    aot.get_stat(stat)[:, p].reshape(-1, ntimesteps), axis=0
                )
                data *= stats[stat]["xfactor"]
                axes[k].plot(time, data, label=self.pols[p])
            axes[k].set_ylabel(f"{stats[stat]['label']} ({stats[stat]['units']})")
            axes[k].legend()
        for ax in axes[-3:]:
            ax.set_xlabel("Time (hr)" if divisor == 3660 else "Time (min)")

        axes[-1].remove()
        fig.tight_layout()
        plt.savefig(f"{self.name}_aoq_time_stats.pdf", bbox_inches="tight")
        plt.close(fig)
        return

    def plot_baseline_qstats(self):
        """Plot baseline-, antenna-, and baseline-length stats and save PDFs."""
        aob = ao.AOQualityBaselineStat(self.qs_file)
        stats = self.get_available_stats()

        for stat in stats:
            for p in self.pol_idx():
                fb1 = aob.plot_baseline_stats(stat, log=False, name="", pol=p)
                fb2 = aob.plot_antennae_stats(stat, log=False, name="", pol=p)
                fb3 = aob.plot_baseline_length_stats(stat, log=False, name="", pol=p)

                fb1.savefig(
                    f"{self.name}_aoq_baseline_{stat}_{self.pols[p]}.pdf",
                    bbox_inches="tight",
                )
                fb2.savefig(
                    f"{self.name}_aoq_antenna_{stat}_{self.pols[p]}.pdf",
                    bbox_inches="tight",
                )
                fb3.savefig(
                    f"{self.name}_aoq_baseline_length_{stat}_{self.pols[p]}.pdf",
                    bbox_inches="tight",
                )
                for ff in [fb1, fb2, fb3]:
                    plt.close(ff)
        return


@click.group()
def main():
    """Plot data quality statistics..."""


@main.command("plot_aoq")
@click.argument("qstats_file")
@click.option("--name", help="output name", type=str, default="")
def plot_aoqstats(qstats_file, name=""):
    """Plot aoquality statistics."""
    qq = QualityStats(qstats_file, name)

    qq.plot_time_qstats()
    qq.plot_freq_qstats()
    qq.plot_baseline_qstats()


if __name__ == "__main__":
    main()
