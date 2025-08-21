#!/bin/bash
#
# run_pcpip.sh - Run the PCPIP test suite (Docker version)
#
# Description:
#   This script automates the execution of multiple CellProfiler pipelines in sequence,
#   applying them to plate/well/site data according to a predefined workflow.
#   Modified for containerized execution with Docker.
#
# Usage:
#   ./run_pcpip.sh
#   PIPELINE_STEP=1 ./run_pcpip.sh
#   PIPELINE_STEP=2 ./run_pcpip.sh
#   PIPELINE_STEP=4 ./run_pcpip.sh
#   PIPELINE_STEP="1,2,3" ./run_pcpip.sh
#

# Pipeline step to run (required - no default)
PIPELINE_STEP=${PIPELINE_STEP}

# Docker-based paths
LOAD_DATA_DIR="/app/data/Source1/workspace/load_data_csv/Batch1/Plate1_trimmed"
REPRODUCE_DIR="/app/data"
METADATA_DIR="/app/data/Source1/workspace/metadata"
PIPELINE_DIR="/app/pipelines"

# Create a timestamp for this run
TIMESTAMP=$(date +"%Y-%m-%d_%H%M%S")

# Directory for logs with timestamp
LOG_DIR="${REPRODUCE_DIR}/logs/${TIMESTAMP}"
mkdir -p ${LOG_DIR}

PLATE=Plate1
# WELLS=("A1" "A2" "B1")
WELLS=("A1")
SITES=(0 1)
# CYCLES=(1 2 3)
CYCLES=(1 2)

# Define CellProfiler pipeline configurations
declare -A PIPELINE_CONFIG=(
  # Pipeline file names
  [1,file]="ref_1_CP_Illum.cppipe"
  [2,file]="ref_2_CP_Apply_Illum.cppipe"
  [3,file]="ref_3_CP_SegmentationCheck.cppipe"
  [5,file]="ref_5_BC_Illum.cppipe"
  [6,file]="ref_6_BC_Apply_Illum.cppipe"
  [7,file]="ref_7_BC_Preprocess.cppipe"
  [9,file]="ref_9_Analysis.cppipe"

  # Data files
  [1,data]="load_data_pipeline1.csv"
  [2,data]="load_data_pipeline2.csv"
  [3,data]="load_data_pipeline3.csv"
  [5,data]="load_data_pipeline5.csv"
  [6,data]="load_data_pipeline6.csv"
  [7,data]="load_data_pipeline7.csv"
  [9,data]="load_data_pipeline9.csv"

  # Output directory patterns
  [1,output]="illum/PLATE"
  [2,output]="images_corrected/painting/PLATE-WELL"
  [3,output]="images_segmentation/PLATE-WELL"
  [5,output]="illum/PLATE"
  [6,output]="images_aligned/barcoding/PLATE-WELL-SITE"
  [7,output]="images_corrected/barcoding/PLATE-WELL-SITE"
  [9,output]="../workspace/analysis/Batch1/PLATE-WELL-SITE"

  # Log filename patterns
  [1,log]="pipeline1_PLATE"
  [2,log]="pipeline2_PLATE_WELL"
  [3,log]="pipeline3_PLATE_WELL"
  [5,log]="pipeline5_PLATE_CYCLE"
  [6,log]="pipeline6_PLATE_WELL_SITE"
  [7,log]="pipeline7_PLATE_WELL_SITE"
  [9,log]="pipeline9_PLATE_WELL_SITE"

  # Group patterns
  [1,group]="Metadata_Plate=PLATE"
  [2,group]="Metadata_Plate=PLATE,Metadata_Well=WELL"
  [3,group]="Metadata_Plate=PLATE,Metadata_Well=WELL"
  [5,group]="Metadata_Plate=PLATE,Metadata_Cycle=CYCLE"
  [6,group]="Metadata_Plate=PLATE,Metadata_Well=WELL,Metadata_Site=SITE"
  [7,group]="Metadata_Plate=PLATE,Metadata_Well=WELL,Metadata_Site=SITE"
  [9,group]="Metadata_Plate=PLATE,Metadata_Well=WELL,Metadata_Site=SITE"

  # Required parameters (comma-separated)
  [1,params]="PLATE"
  [2,params]="PLATE,WELL"
  [3,params]="PLATE,WELL"
  [5,params]="PLATE,CYCLE"
  [6,params]="PLATE,WELL,SITE"
  [7,params]="PLATE,WELL,SITE"
  [9,params]="PLATE,WELL,SITE"

  # Needs metadata flag (true/false)
  [1,metadata]="false"
  [2,metadata]="false"
  [3,metadata]="false"
  [5,metadata]="false"
  [6,metadata]="false"
  [7,metadata]="true"
  [9,metadata]="true"

  # Run in background (true/false) - memory-heavy pipelines run sequentially
  [1,background]="false"
  [2,background]="true"
  [3,background]="true"
  [5,background]="true"
  [6,background]="false"
  [7,background]="false"
  [9,background]="false"

  # Needs plugins (true/false)
  [1,plugins]="false"
  [2,plugins]="false"
  [3,plugins]="false"
  [5,plugins]="false"
  [6,plugins]="false"
  [7,plugins]="true"
  [9,plugins]="true"
)

# Define Fiji/ImageJ stitching pipeline configurations
declare -A STITCH_CONFIG=(
  # Input directory patterns (relative to /app/data/Source1/Batch1/)
  [4,input]="images_corrected/painting/PLATE-WELL"
  [8,input]="images_corrected/barcoding/PLATE-WELL-SITE"

  # Output directory patterns - all 3 outputs per pipeline
  [4,output_stitched]="images_corrected_stitched/cellpainting/PLATE/PLATE_WELL"
  [4,output_cropped]="images_corrected_cropped/cellpainting/PLATE/PLATE_WELL"
  [4,output_downsampled]="images_corrected_stitched_10X/cellpainting/PLATE/PLATE_WELL"
  [8,output_stitched]="images_corrected_stitched/barcoding/PLATE/PLATE_WELL_SITE"
  [8,output_cropped]="images_corrected_cropped/barcoding/PLATE/PLATE_WELL_SITE"
  [8,output_downsampled]="images_corrected_stitched_10X/barcoding/PLATE/PLATE_WELL_SITE"

  # Log filename patterns
  [4,log]="pipeline4_PLATE_WELL"
  [8,log]="pipeline8_PLATE_WELL_SITE"

  # Required parameters (comma-separated)
  [4,params]="PLATE,WELL"
  [8,params]="PLATE,WELL,SITE"

  # Script to run (single parameterized script)
  [4,script]="stitch_crop.py"
  [8,script]="stitch_crop.py"

  # Run in background (false for sequential execution)
  [4,background]="false"
  [8,background]="false"
)

# Function to apply variable substitution to a pattern
apply_pattern() {
  local pattern=$1
  local result=$pattern

  # Apply all available substitutions
  result=${result//PLATE/$PLATE}

  if [[ -n "$WELL" ]]; then
    result=${result//WELL/$WELL}
  fi

  if [[ -n "$SITE" ]]; then
    result=${result//SITE/$SITE}
  fi

  if [[ -n "$CYCLE" ]]; then
    result=${result//CYCLE/$CYCLE}
  fi

  echo "$result"
}

# Function to run a command with logging
run_with_logging() {
  local cmd=$1
  local log_file=$2
  local run_bg=$3

  # Create log directory if it doesn't exist
  mkdir -p "$(dirname "$log_file")"

  # Add header to log file with timestamp and command
  {
    echo "===================================================="
    echo "  STARTED: $(date)"
    echo "  COMMAND: $cmd"
    echo "===================================================="
    echo ""
  } > "$log_file"

  # Run the command and log output
  if [[ "$run_bg" == "true" ]]; then
    # For background processes, redirect output to log
    eval "$cmd" >> "$log_file" 2>&1 &
  else
    # For foreground processes, redirect output to log
    eval "$cmd" >> "$log_file" 2>&1
  fi

  # Log completion for foreground processes
  if [[ "$run_bg" != "true" ]]; then
    {
      echo ""
      echo "===================================================="
      echo "  COMPLETED: $(date)"
      echo "  EXIT CODE: $?"
      echo "===================================================="
    } >> "$log_file"
  fi
}

# Function to run a pipeline with the right parameters
run_pipeline() {
  local pipeline=$1
  local required_params=${PIPELINE_CONFIG[$pipeline,params]}
  local use_metadata=${PIPELINE_CONFIG[$pipeline,metadata]}
  local run_background=${PIPELINE_CONFIG[$pipeline,background]}
  local use_plugins=${PIPELINE_CONFIG[$pipeline,plugins]}

  # Build the basic command
  local cmd="cellprofiler -c -L 10"

  # Add group parameter
  cmd+=" -g \"$(apply_pattern "${PIPELINE_CONFIG[$pipeline,group]}")\""

  # Add metadata path if needed
  if [[ "$use_metadata" == "true" ]]; then
    cmd+=" -i ${METADATA_DIR}/"
  fi

  # Add pipeline, data file and output directory
  cmd+=" --pipeline ${PIPELINE_DIR}/${PIPELINE_CONFIG[$pipeline,file]}"
  cmd+=" --data-file ${LOAD_DATA_DIR}/${PIPELINE_CONFIG[$pipeline,data]}"
  cmd+=" --output-directory $(apply_pattern "${REPRODUCE_DIR}/Source1/Batch1/${PIPELINE_CONFIG[$pipeline,output]}")"

  # Add plugins if needed
  if [[ "$use_plugins" == "true" ]]; then
    cmd+=" --plugins-directory /app/plugins/active_plugins/"
  fi

  # Get log filename using pattern substitution
  local log_pattern=${PIPELINE_CONFIG[$pipeline,log]}
  local log_file="${LOG_DIR}/$(apply_pattern "$log_pattern").log"

  # Log the command execution
  echo "Running pipeline $pipeline, logging to: $log_file"

  # Run with logging
  run_with_logging "$cmd" "$log_file" "$run_background"
}

# Function to run stitch-crop pipeline using STITCH_CONFIG
run_stitchcrop_pipeline() {
  local pipeline=$1  # 4 or 8
  local required_params=${STITCH_CONFIG[$pipeline,params]}
  local run_background=${STITCH_CONFIG[$pipeline,background]}
  local script_name=${STITCH_CONFIG[$pipeline,script]}

  # Get log filename using pattern substitution
  local log_pattern=${STITCH_CONFIG[$pipeline,log]}
  local log_file="${LOG_DIR}/$(apply_pattern "$log_pattern").log"

  echo "Running Pipeline $pipeline (Stitch-Crop), logging to: $log_file"

  # Determine track type and output pattern based on pipeline
  local track_type=""
  local output_pattern=""
  if [[ "$pipeline" == "4" ]]; then
    track_type="painting"
    output_pattern="PLATE_WELL"
  elif [[ "$pipeline" == "8" ]]; then
    track_type="barcoding"
    output_pattern="PLATE_WELL_SITE"
  fi

  # Set environment variables for the Python script to read
  local cmd="STITCH_INPUT_BASE=\"${REPRODUCE_DIR}/Source1/Batch1\" \
STITCH_TRACK_TYPE=\"${track_type}\" \
STITCH_OUTPUT_TAG=\"$(apply_pattern "$output_pattern")\" \
STITCH_CHANNEL=\"DNA\" \
STITCH_AUTORUN=\"true\" \
/opt/fiji/Fiji.app/ImageJ-linux64 --ij2 --headless --run /app/scripts/${script_name}"

  # Run with logging
  run_with_logging "$cmd" "$log_file" "$run_background"
}

# Function to check if a pipeline step should run
should_run_step() {
  local step=$1

  # Check if PIPELINE_STEP is set
  if [[ -z "$PIPELINE_STEP" ]]; then
    echo "ERROR: PIPELINE_STEP environment variable is required"
    echo "Usage: PIPELINE_STEP=1 docker-compose run --rm cellprofiler"
    echo "       PIPELINE_STEP=\"1,2,3\" docker-compose run --rm cellprofiler"
    exit 1
  fi

  # Check if step is in the comma-separated list
  IFS=',' read -ra STEPS <<< "$PIPELINE_STEP"
  for s in "${STEPS[@]}"; do
    if [[ "$s" == "$step" ]]; then
      return 0
    fi
  done

  return 1
}

# Pipeline execution sequence based on PIPELINE_STEP
# --------------------------

echo "Pipeline steps to run: $PIPELINE_STEP"

# 1_CP_Illum - PLATE only
if should_run_step 1; then
  echo "Running Pipeline 1: CP_Illum"
  PIPELINE=1
  run_pipeline $PIPELINE
fi

# 2_CP_Apply_Illum - PLATE, WELL
if should_run_step 2; then
  echo "Running Pipeline 2: CP_Apply_Illum"
  PIPELINE=2
  for WELL in "${WELLS[@]}"; do
      run_pipeline $PIPELINE
  done
  wait
fi

# 3_CP_SegmentationCheck - PLATE, WELL
if should_run_step 3; then
  echo "Running Pipeline 3: CP_SegmentationCheck"
  PIPELINE=3
  for WELL in "${WELLS[@]}"; do
      run_pipeline $PIPELINE
  done
  wait
fi

# 4_CP_StitchCrop - NEW
if should_run_step 4; then
  echo "Running Pipeline 4: CP_StitchCrop"
  PIPELINE=4
  for WELL in "${WELLS[@]}"; do
      run_stitchcrop_pipeline $PIPELINE
  done
  wait
fi

# 5_BC_Illum - PLATE, CYCLE
if should_run_step 5; then
  echo "Running Pipeline 5: BC_Illum"
  PIPELINE=5
  for CYCLE in "${CYCLES[@]}"; do
      run_pipeline $PIPELINE
  done
  wait
fi

# 6_BC_Apply_Illum - PLATE, WELL, SITE
if should_run_step 6; then
  echo "Running Pipeline 6: BC_Apply_Illum"
  PIPELINE=6
  for WELL in "${WELLS[@]}"; do
      for SITE in "${SITES[@]}"; do
          run_pipeline $PIPELINE
      done
  done
  wait
fi

# 7_BC_Preprocess - PLATE, WELL, SITE
if should_run_step 7; then
  echo "Running Pipeline 7: BC_Preprocess"
  PIPELINE=7
  for WELL in "${WELLS[@]}"; do
      for SITE in "${SITES[@]}"; do
          run_pipeline $PIPELINE
      done
  done
  wait
fi

# 8_BC_StitchCrop - NEW
if should_run_step 8; then
  echo "Running Pipeline 8: BC_StitchCrop"
  PIPELINE=8
  for WELL in "${WELLS[@]}"; do
      for SITE in "${SITES[@]}"; do
          run_stitchcrop_pipeline $PIPELINE
      done
  done
  wait
fi

# 9_Analysis - PLATE, WELL, SITE
if should_run_step 9; then
  echo "Running Pipeline 9: Analysis"
  PIPELINE=9
  for WELL in "${WELLS[@]}"; do
      for SITE in "${SITES[@]}"; do
          run_pipeline $PIPELINE
      done
  done
  wait
fi

echo "=== Pipeline execution complete ==="
