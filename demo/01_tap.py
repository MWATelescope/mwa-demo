#!/usr/bin/env python
# query the MWA TAP server with ADQL using the pyvo library
# details: https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/24970532/MWA+ASVO+VO+Services
# and https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/24970424/TAP+mwa.observation+Schema+and+Examples

from sys import argv, stderr

import pyvo
from astropy.time import Time, TimeDelta

if not argv:
    print(
        f"""
          Usage: {argv[0]}
          or: {argv[0]} obsids.csv details.csv
          """,
        file=stderr,
    )
    exit(1)

# get gpstime of proprietary period, 18 months (548 days) ago
proprietary = (Time.now() - TimeDelta(548, format="jd")).gps
tap = pyvo.dal.TAPService("http://vo.mwatelescope.org/mwa_asvo/tap")
obs = (
    tap.search(
        f"""
SELECT TOP 99 *
FROM mwa.observation
WHERE CONTAINS(
    POINT('ICRS', ra_pointing, dec_pointing),  -- pointing center
    CIRCLE('ICRS', 201.3667, -43.0192, 5)      -- is 5 degrees off CenA
) = 1
AND channel_numbers_csv LIKE '%137%'           -- has channel 137 (175MHz)
AND obs_id < {proprietary}                     -- nonproprietary
AND good_tiles >= 112                          -- 14 good receivers
AND dataquality <= 1                           -- no known issues
AND sun_elevation < 0                          -- sun is not up
AND deleted_flag!='TRUE'                       -- not deleted
AND gpubox_files_archived > 1                  -- data available
-- AND freq_res <= 10                          -- (optional) 10kHz resolution or less
-- AND int_time <= 1                           -- (optional) 1s integration or less
-- AND mwa_array_configuration = 'Phase II Compact' -- (optional) compact => more short baselines
ORDER BY obs_id DESC
"""
    )
    .to_table()
    .to_pandas()
    .dropna(axis=1, how="all")
)
obs["config"] = obs["mwa_array_configuration"].str.split(" ").str[-1]
obs["gigabytes"] = obs["total_archived_data_bytes"] / 1e9
print(f"{len(obs)} results. preview:", file=stderr)
print(obs[["obs_id", "starttime_utc", "obsname", "config", "gigabytes"]], file=stderr)

out_obsids = "obsids.csv"
if len(argv) > 1:
    out_obsids = argv[1]
    assert not out_obsids.endswith(".py"), "output file should not end with .py"
out_details = "details.csv"
if len(argv) > 2:
    out_details = argv[2]
    assert not out_details.endswith(".py"), "output file should not end with .py"
obs["obs_id"].astype(int).to_csv(out_obsids, index=False, header=False)
obs.to_csv(out_details, index=False, header=True)
