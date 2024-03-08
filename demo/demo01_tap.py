#!/usr/bin/env python
# query the MWA TAP server with ADQL using the pyvo library
# details: https://mwatelescope.atlassian.net/wiki/spaces/MP/pages/24970532/MWA+ASVO+VO+Services

import pyvo; from astropy.time import Time, TimeDelta
# proprietary period is 18 months
proprietary = (Time.now() - TimeDelta(548, format='jd')).gps
tap = pyvo.dal.TAPService("http://vo.mwatelescope.org/mwa_asvo/tap")
obs = tap.search(f"""
SELECT TOP 10 *
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
""").to_table().to_pandas().dropna(axis=1, how='all')
print(len(obs))
print(obs[['obs_id', 'starttime_utc', 'obsname']])
obs['obs_id'].astype(int).to_csv(f'obsids-cena.csv', index=False, header=False)
obs.to_csv(f'cena.csv', index=False, header=True)