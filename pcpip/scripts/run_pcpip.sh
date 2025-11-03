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

# QC enablement flag (default: true) - for automatic QC within pipelines
RUN_QC=${RUN_QC:-"true"}

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
WELLS=("A1") # MUST match the wells filtered in LoadData CSVs (see filter_loaddata_csvs_inplace.py)
SITES=(0 1 2 3) # This has to be consistent with load data csv files and the settings in stitch_crop.py (rows x columns)
CYCLES=(1 2 3) # This has to be consistent with the barcoding pipeline

# Derived tile indices for cropped outputs used by Pipeline 9 (Analysis)
TILES=(1 2 3 4)

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

  # Data files - use generated CSVs
  [1,data]="load_data_pipeline1_generated.csv"
  [2,data]="load_data_pipeline2_generated.csv"
  [3,data]="load_data_pipeline3_generated.csv"
  [5,data]="load_data_pipeline5_generated.csv"
  [6,data]="load_data_pipeline6_generated.csv"
  [7,data]="load_data_pipeline7_generated.csv"
  [9,data]="load_data_pipeline9_generated.csv"

  # Output directory patterns
  [1,output]="illum/PLATE"
  [2,output]="images_corrected/painting/PLATE/PLATE-WELL-SITE"
  [3,output]="images_segmentation/painting/PLATE/PLATE-WELL"
  [5,output]="illum/PLATE"
  [6,output]="images_aligned/barcoding/PLATE/PLATE-WELL-SITE"
  [7,output]="images_corrected/barcoding/PLATE/PLATE-WELL-SITE"
  [9,output]="../../workspace/analysis/Batch1/PLATE-WELL-SITE"

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
  [2,group]="Metadata_Plate=PLATE,Metadata_Well=WELL,Metadata_Site=SITE"
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
  [1,background]="true" # true is fine for 25% CROPS but false otherwise
  [2,background]="true"
  [3,background]="true"
  [5,background]="true"
  [6,background]="true" # true is fine for 25% CROPS but false otherwise
  [7,background]="true" # true is fine for 25% CROPS but false otherwise
  [9,background]="true" # true is fine for 25% CROPS but false otherwise

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
# Note: stitch_crop.py auto-discovers wells from the filesystem and processes ALL of them
# Each well's output goes to a separate subdirectory (e.g., Plate1-A1/, Plate1-A2/)
declare -A STITCH_CONFIG=(
  # Track type for each pipeline (actually used by stitch_crop.py)
  [4,track]="painting"
  [8,track]="barcoding"

  # Log filename patterns
  [4,log]="pipeline4_painting_${PLATE}"
  [8,log]="pipeline8_barcoding_${PLATE}"

  # Run in background (false for sequential execution)
  [4,background]="true"
  [8,background]="true"
)

# Define QC check configurations
declare -A QC_CONFIG=(
  # QC after Pipeline 1 - Cell Painting Illumination (no Cycle in filename)
  [1_qc_illum,script]="montage.py"
  [1_qc_illum,input]="illum/PLATE"
  [1_qc_illum,output]="../../workspace/qc_reports/1_illumination_cp/PLATE"
  [1_qc_illum,output_type]="file"  # 'file' or 'dir'
  [1_qc_illum,output_name]="montage.png"  # Name for single file outputs
  [1_qc_illum,log]="1_qc_illum_PLATE"
  [1_qc_illum,extra_args]="--pattern \"^(?!.*Cycle).*\.npy$\""  # Regex: .npy files NOT containing 'Cycle'

  # QC after Pipeline 3 - Segmentation Check
  [3_qc_seg,script]="montage.py"
  [3_qc_seg,input]="images_segmentation/painting/PLATE/PLATE-WELL"
  [3_qc_seg,output]="../../workspace/qc_reports/3_segmentation/PLATE/PLATE-WELL"
  [3_qc_seg,output_type]="file"
  [3_qc_seg,output_name]="montage.png"
  [3_qc_seg,log]="3_qc_seg_PLATE_WELL"
  [3_qc_seg,extra_args]="--pattern \".*SegmentCheck\.png$\""  # Regex: files ending with SegmentCheck.png

  # QC after Pipeline 5 - Barcoding Illumination (with Cycle in filename)
  [5_qc_illum,script]="montage.py"
  [5_qc_illum,input]="illum/PLATE"
  [5_qc_illum,output]="../../workspace/qc_reports/5_illumination_bc/PLATE"
  [5_qc_illum,output_type]="file"
  [5_qc_illum,output_name]="montage.png"
  [5_qc_illum,log]="5_qc_illum_PLATE"
  [5_qc_illum,extra_args]="--pattern \".*Cycle.*\.npy$\""  # Regex: .npy files containing 'Cycle'

  # QC after Pipeline 4 - Cell Painting Stitching (10X preview images)
  [4_qc_stitch,script]="montage.py"
  [4_qc_stitch,input]="images_corrected_stitched_10X/painting/PLATE"
  [4_qc_stitch,output]="../../workspace/qc_reports/4_stitching_cp/PLATE"
  [4_qc_stitch,output_type]="file"
  [4_qc_stitch,output_name]="montage.png"
  [4_qc_stitch,log]="4_qc_stitch_PLATE"
  [4_qc_stitch,extra_args]="--pattern \"Stitched_CorrDNA\.tiff$\""  # DNA channel only

  # QC after Pipeline 6 - Barcoding Alignment Analysis
  [6_qc_align,script]="qc_barcode_align.py"
  [6_qc_align,input]="images_aligned/barcoding/PLATE"
  [6_qc_align,output]="../../workspace/qc_reports/6_alignment/PLATE"
  [6_qc_align,output_type]="dir"  # Outputs multiple CSV files
  [6_qc_align,log]="6_qc_align_PLATE"
  [6_qc_align,extra_args]="--numcycles 3 --shift-threshold 50 --corr-threshold 0.9"

  # QC after Pipeline 8 - Barcoding Stitching (10X preview images)
  [8_qc_stitch,script]="montage.py"
  [8_qc_stitch,input]="images_corrected_stitched_10X/barcoding/PLATE"
  [8_qc_stitch,output]="../../workspace/qc_reports/8_stitching_bc/PLATE"
  [8_qc_stitch,output_type]="file"
  [8_qc_stitch,output_name]="montage.png"
  [8_qc_stitch,log]="8_qc_stitch_PLATE"
  [8_qc_stitch,extra_args]="--pattern \"Stitched_Cycle01_DNA\.tiff$\""  # Cycle 1 DNA only
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
  cmd+=" --output-directory $(apply_pattern "${REPRODUCE_DIR}/Source1/images/Batch1/${PIPELINE_CONFIG[$pipeline,output]}")"

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

# Function to run stitch-crop pipeline
# Note: This processes ALL wells found in the input directory
# Each well gets its own output subdirectory (e.g., Plate1/A1/, Plate1/A2/)
run_stitchcrop_pipeline() {
  local pipeline=$1  # 4 or 8
  local run_background=${STITCH_CONFIG[$pipeline,background]}
  local track_type=${STITCH_CONFIG[$pipeline,track]}
  local log_file="${LOG_DIR}/${STITCH_CONFIG[$pipeline,log]}.log"

  echo "Running Pipeline $pipeline (Stitch-Crop for ${track_type}), logging to: $log_file"
  echo "Processing ALL wells found in ${track_type} directory - each to its own subdirectory"

  # Set environment variables for the Python script to read
  local cmd="STITCH_INPUT_BASE=\"${REPRODUCE_DIR}/Source1/images/Batch1\" \
STITCH_TRACK_TYPE=\"${track_type}\" \
STITCH_AUTORUN=\"true\" \
/opt/fiji/Fiji.app/ImageJ-linux64 --ij2 --headless --run /app/scripts/stitch_crop.py"

  # Run with logging
  run_with_logging "$cmd" "$log_file" "$run_background"
}

# Function to run QC checks
run_qc_check() {
  local qc_key=$1
  local script=${QC_CONFIG[$qc_key,script]}
  local output_type=${QC_CONFIG[$qc_key,output_type]:-"file"}
  local output_name=${QC_CONFIG[$qc_key,output_name]:-"output.png"}
  local extra_args=${QC_CONFIG[$qc_key,extra_args]:-""}

  # Build input and output paths
  local input_dir=$(apply_pattern "${REPRODUCE_DIR}/Source1/images/Batch1/${QC_CONFIG[$qc_key,input]}")
  local output_dir=$(apply_pattern "${REPRODUCE_DIR}/Source1/images/Batch1/${QC_CONFIG[$qc_key,output]}")

  # Determine output path based on output type
  local output_path
  if [[ "$output_type" == "file" ]]; then
    output_path="${output_dir}/${output_name}"
  else
    # For directory outputs, just pass the directory
    output_path="${output_dir}"
  fi

  # Create output directory if needed
  mkdir -p "${output_dir}"

  # Build command - scripts have shebang and execute permissions
  local cmd="/app/scripts/${script} \"${input_dir}\" \"${output_path}\""
  if [[ -n "$extra_args" ]]; then
    cmd+=" ${extra_args}"
  fi

  # Get log filename using pattern substitution
  local log_pattern=${QC_CONFIG[$qc_key,log]}
  local log_file="${LOG_DIR}/$(apply_pattern "$log_pattern").log"

  # Log the QC execution
  echo "Running QC check: $qc_key"
  echo "Input: $input_dir"
  echo "Output: $output_path"
  if [[ -n "$extra_args" ]]; then
    echo "Extra args: $extra_args"
  fi
  echo "Logging to: $log_file"

  # Run with logging
  run_with_logging "$cmd" "$log_file" "false"
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
wait

# 1_qc_illum - QC for Cell Painting illumination
if should_run_step 1_qc_illum; then
  echo "Running QC for Pipeline 1: Illumination Montage"
  run_qc_check "1_qc_illum"
fi
wait

# 2_CP_Apply_Illum - PLATE, WELL
if should_run_step 2; then
  echo "Running Pipeline 2: CP_Apply_Illum"
  PIPELINE=2
  for WELL in "${WELLS[@]}"; do
      for SITE in "${SITES[@]}"; do
        run_pipeline $PIPELINE
      done
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

# 3_qc_seg - QC for Segmentation Check
if should_run_step 3_qc_seg; then
  echo "Running QC for Pipeline 3: Segmentation Montage"
  for WELL in "${WELLS[@]}"; do
      run_qc_check "3_qc_seg"
  done
  wait
fi

# 4_CP_StitchCrop - Processes ALL wells found in painting directory
if should_run_step 4; then
  echo "Running Pipeline 4: CP_StitchCrop (painting)"
  # Note: Only run once - the script auto-discovers and processes ALL wells
  run_stitchcrop_pipeline 4
  wait
fi

# 4_qc_stitch - QC for Cell Painting stitching
if should_run_step 4_qc_stitch; then
  echo "Running QC for Pipeline 4: Stitching Montage"
  run_qc_check "4_qc_stitch"
fi
wait

# 5_BC_Illum - PLATE, CYCLE
if should_run_step 5; then
  echo "Running Pipeline 5: BC_Illum"
  PIPELINE=5
  for CYCLE in "${CYCLES[@]}"; do
      run_pipeline $PIPELINE
  done
  wait
fi

# 5_qc_illum - QC for Barcoding illumination
if should_run_step 5_qc_illum; then
  echo "Running QC for Pipeline 5: Illumination Montage"
  run_qc_check "5_qc_illum"
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

# 6_qc_align - QC for Barcoding alignment
if should_run_step 6_qc_align; then
  echo "Running QC for Pipeline 6: Alignment Analysis"
  run_qc_check "6_qc_align"
fi
wait

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

# 8_BC_StitchCrop - Processes ALL wells found in barcoding directory
if should_run_step 8; then
  echo "Running Pipeline 8: BC_StitchCrop (barcoding)"
  # Note: Only run once - the script auto-discovers and processes ALL wells
  run_stitchcrop_pipeline 8
  wait
fi

# 8_qc_stitch - QC for Barcoding stitching
if should_run_step 8_qc_stitch; then
  echo "Running QC for Pipeline 8: Stitching Montage"
  run_qc_check "8_qc_stitch"
fi
wait

# 9_Analysis - PLATE, WELL, SITE
if should_run_step 9; then
  echo "Running Pipeline 9: Analysis"
  PIPELINE=9
  for WELL in "${WELLS[@]}"; do
      # Use TILES instead of SITES for Analysis
      for SITE in "${TILES[@]}"; do
          run_pipeline $PIPELINE
      done
  done
  wait
fi

echo "=== Pipeline execution complete ==="
