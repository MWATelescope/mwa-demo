#!/usr/bin/env python

from casacore.tables import taql
from astropy.time import Time
import numpy as np
import sys

print(''.join(taql(f"show table '{sys.argv[-1]}'")))

t = taql(f"select * from '{sys.argv[-1]}'")
print("\nData Manager Info:")
dminfo = t.getdminfo()
for name, info in dminfo.items():
    print(f"  {name}: {info['TYPE']} (columns: {', '.join(info['COLUMNS'])})")
times = Time(np.unique(t.getcol("TIME")) / 86400.0, format="mjd", scale="utc")
print(f"times ({len(times)}):\n{times.iso}")

history = taql(f"select * from '{sys.argv[-1]}/HISTORY'").getcol("MESSAGE")
print(f"history ({len(history)}):\n{history}")