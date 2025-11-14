#!/bin/bash
set -e

# Wrapper script to run stitch_crop_v0.py with cellprofiler/distributed-fiji
# Can be run from anywhere - uses script location to find directories

# Get the directory above the directory containing this script (for local dev defaults)
SCRIPTS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Get the pcpip directory (parent of scripts/, for local dev defaults)
PCPIP_DIR="$(dirname "$SCRIPTS_DIR")"

# === Configuration from Environment Variables (with defaults) ===
# All parameters can be overridden via SC_* environment variables
# Example: SC_PLATE=Plate2 SC_WELL=B3 ./stitch_crop_v0_run.sh

# Docker volume mount paths (host side)
SC_HOST_DATA_DIR="${SC_HOST_DATA_DIR:-$PCPIP_DIR/data}"
SC_HOST_SCRIPTS_DIR="${SC_HOST_SCRIPTS_DIR:-$SCRIPTS_DIR}"

# Docker working directory (inside container)
SC_WORKDIR="${SC_WORKDIR:-/app/data/Source1/images/Batch1}"

# Fiji/ImageJ script paths
SC_INPUT_FILE_LOCATION="${SC_INPUT_FILE_LOCATION:-./}"
SC_PLATE="${SC_PLATE:-Plate1}"
SC_WELL="${SC_WELL:-A1}"
SC_TRACK="${SC_TRACK:-painting}"
SC_LOCALTEMP="${SC_LOCALTEMP:-./output}"  # Only used if SC_AWS_DOWNLOAD=True (not our workflow)
                                                  # Actual output goes to hardcoded 'output/' in script

# Computed paths
SC_INPUT_SUBDIR="${SC_INPUT_SUBDIR:-images_corrected_flattened/${SC_TRACK}/${SC_PLATE}}"
SC_OUT_SUBDIR_TAG="${SC_OUT_SUBDIR_TAG:-${SC_PLATE}-${SC_WELL}}"
SC_DOWNLOADFILTER="${SC_DOWNLOADFILTER:-${SC_PLATE}-${SC_WELL}*}"

# Grid layout (2x2 square grid for test data)
SC_ROWS="${SC_ROWS:-2}"
SC_COLUMNS="${SC_COLUMNS:-2}"
SC_IMPERWELL="${SC_IMPERWELL:-4}"
SC_STITCH_ORDER="${SC_STITCH_ORDER:-Grid: snake by rows}"
SC_ROUND_OR_SQUARE="${SC_ROUND_OR_SQUARE:-square}"

# Image dimensions (for 25% cropped images)
SC_TILE_SIZE="${SC_TILE_SIZE:-400}"              # Input tile size
SC_FINAL_TILE_SIZE="${SC_FINAL_TILE_SIZE:-800}"  # Output tile size after stitching & scaling
SC_OVERLAP_PCT="${SC_OVERLAP_PCT:-10}"
SC_TILEPERSIDE="${SC_TILEPERSIDE:-2}"
SC_SCALING="${SC_SCALING:-1.99}"
SC_XOFFSET_TILES="${SC_XOFFSET_TILES:-0}"
SC_YOFFSET_TILES="${SC_YOFFSET_TILES:-0}"

# Processing options
SC_CHAN_NAME="${SC_CHAN_NAME:-DNA}"              # Reference channel for registration
SC_FILTERSTRING="${SC_FILTERSTRING:-${SC_WELL}}"
SC_QUARTER_IF_ROUND="${SC_QUARTER_IF_ROUND:-False}"
SC_COMPRESS="${SC_COMPRESS:-True}"

# AWS (not used in this workflow)
SC_AWS_DOWNLOAD="${SC_AWS_DOWNLOAD:-False}"
SC_BUCKET="${SC_BUCKET:-pooled-cell-painting}"

# === Build Parameters Array ===
PARAMS_ARRAY=(
  "input_file_location=\"${SC_INPUT_FILE_LOCATION}\""
  "step_to_stitch=\"${SC_TRACK}\""
  "subdir=\"${SC_INPUT_SUBDIR}\""
  "out_subdir_tag=\"${SC_OUT_SUBDIR_TAG}\""
  "rows=\"${SC_ROWS}\""
  "columns=\"${SC_COLUMNS}\""
  "imperwell=\"${SC_IMPERWELL}\""
  "stitchorder=\"${SC_STITCH_ORDER}\""
  "channame=\"${SC_CHAN_NAME}\""
  "size=\"${SC_TILE_SIZE}\""
  "overlap_pct=\"${SC_OVERLAP_PCT}\""
  "tileperside=\"${SC_TILEPERSIDE}\""
  "filterstring=\"${SC_FILTERSTRING}\""
  "scalingstring=\"${SC_SCALING}\""
  "awsdownload=\"${SC_AWS_DOWNLOAD}\""
  "bucketname=\"${SC_BUCKET}\""
  "localtemp=\"${SC_LOCALTEMP}\""
  "downloadfilter=\"${SC_DOWNLOADFILTER}\""
  "round_or_square=\"${SC_ROUND_OR_SQUARE}\""
  "quarter_if_round=\"${SC_QUARTER_IF_ROUND}\""
  "final_tile_size=\"${SC_FINAL_TILE_SIZE}\""
  "xoffset_tiles=\"${SC_XOFFSET_TILES}\""
  "yoffset_tiles=\"${SC_YOFFSET_TILES}\""
  "compress=\"${SC_COMPRESS}\""
)

# Join array into comma-separated string with proper spacing
printf -v PARAMS '%s, ' "${PARAMS_ARRAY[@]}"
PARAMS="${PARAMS%, }"  # Remove trailing comma-space

docker run --rm \
  --platform linux/amd64 \
  --entrypoint /opt/fiji/Fiji.app/ImageJ-linux64 \
  -v "$SC_HOST_SCRIPTS_DIR:/app/scripts:ro" \
  -v "$SC_HOST_DATA_DIR:/app/data:rw" \
  -w "$SC_WORKDIR" \
  cellprofiler/distributed-fiji:latest \
  --headless --console --run /app/scripts/stitch_crop_v0.py \
  "$PARAMS"
