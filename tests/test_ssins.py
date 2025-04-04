"""Provides partial test coverage for ssins.py as part of the refactoring effort.

Longer term should also afford baselining for peak memory usage, which is the core metric.

Must: use < 240GB of RAM peak for ~ 60 GB fits file.

"""
from ctypes import memset
import pytest
import importlib.util
import sys
from pathlib import Path
from SSINS import INS, MF, SS
from argparse import Namespace
import numpy as np
from numpy.testing import assert_array_equal
import os
from memory_profiler import memory_usage

MAX_MEM = 240 # GB
MAX_FILE = 60 # GB
MAX_MEM_FACTOR = MAX_MEM // MAX_FILE

args = Namespace(files=['/Users/raf/source/repos/mwa-demo/demo/data//1061312152/raw/1061312152.metafits',
    '/Users/raf/source/repos/mwa-demo/demo/data//1061312272/raw/1061312272.metafits',
    '/Users/raf/source/repos/mwa-demo/demo/data//1061312152/raw/1061312152_20130823165634_gpubox12_01.fits',
    '/Users/raf/source/repos/mwa-demo/demo/data//1061312272/raw/1061312272_20130823165735_gpubox12_00.fits',
    '/Users/raf/source/repos/mwa-demo/demo/data//1061312152/raw/1061312152_20130823165635_gpubox14_01.fits',
    '/Users/raf/source/repos/mwa-demo/demo/data//1061312272/raw/1061312272_20130823165734_gpubox14_00.fits'],
diff=True, flag_init=True, remove_coarse_band=False, correct_van_vleck=False, remove_flagged_ants=True, flag_choice=None, sel_ants=[], skip_ants=[], sel_pols=[], freq_range=None, time_limit=None, suffix='.1061312X', debug=True, cmap='viridis', spectrum_type='cross', threshold=5, narrow=7, streak=8, tb_aggro=0.6, plot_type='spectrum', fontsize=8, export_tsv=False)

def define_memory_limit(files: list[str] | list[Path],
    factor: int = MAX_MEM_FACTOR,
    suffix: str = '.fits') -> float:
       """Defines the memory limit as a function of the size of the initial files to ensure that
       if the files were max_size, they would not use more than max memory"""
       total_size_bytes = sum(Path(f).stat().st_size for f in files
           if Path(f).exists() and Path(f).suffix == suffix)
       return factor * total_size_bytes / (1024 * 1024) # MBs

MEMORY_LIMIT = define_memory_limit(args.files)


@pytest.fixture
def ssins_module():
    module_path = Path(__file__).parent.parent / "demo" / "04_ssins.py"
    module_name = module_path.stem
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec) # type: ignore
    sys.modules[module_name] = module
    spec.loader.exec_module(module) # type: ignore
    return module

@pytest.mark.parametrize("diff", [True, False])
def test_run_ssins_select(ssins_module, diff: bool):
    ss = SS()
    baseline_time = np.load('tests/ss_time_array.npy')
    baseline_freq = np.load('tests/ss_freq_array.npy')
    args.diff = diff
    def call_ssins_read_select():
        _ = ssins_module.read_select(ss, args)
    peak_memory = memory_usage(call_ssins_read_select, interval=0.01,  max_usage=True)
    assert peak_memory  < MEMORY_LIMIT, f"{peak_memory = }MB exceeded  {MEMORY_LIMIT = }MB"
    assert_array_equal(ss.time_array, baseline_time)
    assert_array_equal(ss.freq_array, baseline_freq)
