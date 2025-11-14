#!/bin/bash
set -e

# Wrapper script to run stitch_crop_pcpip_v0.py with cellprofiler/distributed-fiji
# Can be run from anywhere - uses script location to find directories

# Get the directory containing this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the pcpip directory (parent of scripts/)
PCPIP_DIR="$(dirname "$SCRIPT_DIR")"

PARAMS='input_file_location="./", step_to_stitch="painting", subdir="images_corrected_flattened/painting/Plate1", out_subdir_tag="Plate1-A1", rows="2", columns="2", imperwell="4", stitchorder="Grid: snake by rows", channame="DNA", size="400", overlap_pct="10", tileperside="2", filterstring="A1", scalingstring="1.99", awsdownload="False", bucketname="pooled-cell-painting", localtemp="./output", downloadfilter="Plate1-A1*", round_or_square="square", quarter_if_round="False", final_tile_size="800", xoffset_tiles="0", yoffset_tiles="0", compress="True"'

docker run --rm \
  --platform linux/amd64 \
  --entrypoint /opt/fiji/Fiji.app/ImageJ-linux64 \
  -v "$SCRIPT_DIR:/app/scripts:ro" \
  -v "$PCPIP_DIR/data:/app/data:rw" \
  -w /app/data/Source1/images/Batch1 \
  cellprofiler/distributed-fiji:latest \
  --headless --console --run /app/scripts/stitch_crop_v0.py \
  "$PARAMS"
