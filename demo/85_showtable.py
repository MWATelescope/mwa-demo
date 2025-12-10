#!/usr/bin/env python

from casacore.tables import taql
from astropy.time import Time
import numpy as np
import sys

print(''.join(taql(f"show table '{sys.argv[-1]}'")))
times = Time(np.unique(taql(f"select TIME from '{sys.argv[-1]}'").getcol("TIME")) / 86400.0, format="mjd", scale="utc")
print(f"times ({len(times)}):\n{times.iso}")

# print()