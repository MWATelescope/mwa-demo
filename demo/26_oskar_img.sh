#!/bin/bash
# image an OSKAR measurement set with wsclean, faceted the way rapthor does it:
# a 3600 px x 3" (3.00 deg) field cut into 3 x 3 facets of 1200 px (1 deg),
# each gridded with 2x padding (2400 px), Briggs 0, 5 major cycles and a fixed
# 10.43" x 12.79" restoring beam.
# runs inside the mwa-demo container.

# ### #
# ENV #
# ### #
# see: 00_env.sh
if [ -n "$ZSH_VERSION" ]; then ME="${0:A}"; else ME=$(realpath "${BASH_SOURCE:0}"); fi
export SCRIPT_BASE=${SCRIPT_BASE:-$(dirname "$ME")}
source "$SCRIPT_BASE/00_env.sh"

export oskar_dir=${oskar_dir:-${outdir}/oskar}
export config=${config:-aa2}
export duration_s=${duration_s:-120}
# the visibilities to image, e.g. a peeled MS from 27_oskar_peel.sh
export ms=${ms:-${oskar_dir}/vis/${config}_${duration_s}s.ms}
export data_column=${data_column:-DATA}
export imgname=${imgname:-${oskar_dir}/img/$(basename "${ms%.ms}")_${data_column}}
export size=${size:-3600}
export scale=${scale:-3asec}
export facet_px=${facet_px:-1200}
export padding=${padding:-2}
export briggs=${briggs:-0}
export nmiter=${nmiter:-5}
export niter=${niter:-1000000}
export mgain=${mgain:-0.8}
export auto_threshold=${auto_threshold:-3}
export auto_mask=${auto_mask:-5}
export beam_shape=${beam_shape:-12.79asec 10.43asec 0deg}
export cpus=${cpus:-$(nproc --all)}
export temp_dir=${temp_dir:-/tmp}

set -eux
mkdir -p "$(dirname "$imgname")"

# facet regions: square facets on the SIN projection about the phase centre
facets="${imgname%/*}/facets_${size}px_${facet_px}px.reg"
python - "$ms" "$size" "${scale%asec}" "$facet_px" "$facets" <<'EOF'
import sys

import numpy as np
from astropy.wcs import WCS
from casacore.tables import table

ms, size, scale, facet, out = sys.argv[1], int(sys.argv[2]), float(sys.argv[3]), int(sys.argv[4]), sys.argv[5]
ra, dec = np.degrees(table(f"{ms}/FIELD", ack=False).getcol("PHASE_DIR")[0, 0])
w = WCS(naxis=2)
w.wcs.ctype = ["RA---SIN", "DEC--SIN"]
w.wcs.crval = [ra % 360, dec]
w.wcs.crpix = [size / 2 + 1, size / 2 + 1]
w.wcs.cdelt = [-scale / 3600, scale / 3600]
with open(out, "w") as f:
    f.write("# Region file format: DS9 version 4.1\nglobal color=green\nfk5\n")
    for y0 in range(0, size, facet):
        for x0 in range(0, size, facet):
            px = np.array([[x0, y0], [x0 + facet, y0], [x0 + facet, y0 + facet], [x0, y0 + facet]]) + 0.5
            corners = w.wcs_pix2world(px, 1)
            f.write("polygon(" + ",".join(f"{a:.6f},{b:.6f}" for a, b in corners) + ")\n")
print(f"wrote {out}")
EOF

if [[ -f "${imgname}-image.fits" ]]; then
    echo "found ${imgname}-image.fits, skipping wsclean"
    exit 0
fi
SECONDS=0
# shellcheck disable=SC2086 # beam_shape and wsclean_args are word lists
wsclean \
    -name "$imgname" \
    -data-column "$data_column" \
    -size "$size" "$size" \
    -scale "$scale" \
    -facet-regions "$facets" \
    -padding "$padding" \
    -weight briggs "$briggs" \
    -niter "$niter" \
    -nmiter "$nmiter" \
    -mgain "$mgain" \
    -auto-threshold "$auto_threshold" \
    -auto-mask "$auto_mask" \
    -beam-shape $beam_shape \
    -pol I \
    -no-update-model-required \
    -j "$cpus" \
    -temp-dir "$temp_dir" \
    ${wsclean_args:-} \
    "$ms"
echo "wsclean took ${SECONDS} s" | tee "${imgname}-wsclean.time"
