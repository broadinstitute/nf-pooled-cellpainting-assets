# PCPIP Docker Setup

This directory contains a containerized, miniaturized version of the PCPIP (Pooled Cell Painting Image Processing) pipeline using CellProfiler. This demo implementation processes a small subset of data that can run end-to-end in a single script.

## Directory Structure

```
pcpip/
├── pipelines/           # CellProfiler pipeline files (.cppipe)
├── plugins/            # CellProfiler plugins (cloned separately)
├── scripts/            # Processing scripts
│   └── run_pcpip.sh   # Main pipeline execution script
├── data/              # Unified data directory (inputs, outputs, logs)
│   ├── Source1/
│   │   ├── Batch1/
│   │   │   ├── images/                    # INPUT: Original microscopy images
│   │   │   ├── images_corrected/          # OUTPUT: Pipeline-corrected images
│   │   │   ├── images_aligned/            # OUTPUT: Aligned barcode images
│   │   │   ├── images_segmentation/       # OUTPUT: Segmentation results
│   │   │   └── illum/                     # OUTPUT: Illumination correction files
│   │   └── workspace/
│   │       ├── load_data_csv/             # INPUT: Pipeline CSV configurations
│   │       ├── analysis/                  # OUTPUT: Final analysis results
│   │       └── metadata/                  # INPUT: Metadata files (barcodes, etc.)
│   └── logs/                              # OUTPUT: Timestamped execution logs
├── docker-compose.yml # Docker configuration
└── README.md          # This file
```

## Prerequisites

- Docker and Docker Compose installed
- Git (for cloning plugins)
- Input data in the expected format

## Setup

### 1. Clone CellProfiler Plugins

```bash
# Clone the CellProfiler plugins repository
git clone https://github.com/CellProfiler/CellProfiler-plugins.git plugins
```

### 2. Prepare Data

Download and extract both the FIX-S1 input and output test datasets:

```bash
mkdir -p data

# Download FIX-S1 input data (images)
wget https://github.com/shntnu/starrynight/releases/download/v0.0.1/fix_s1_input.tar.gz
tar -xzf fix_s1_input.tar.gz
mv fix_s1_input/* data/ && rmdir fix_s1_input && rm fix_s1_input.tar.gz

# Download FIX-S1 output data (contains load_data CSV files)
wget https://github.com/shntnu/starrynight/releases/download/v0.0.1/fix_s1_output.tar.gz
tar -xzf fix_s1_output.tar.gz
# Copy the load_data CSV files to input location where the script expects them
mv fix_s1_pcpip_output/Source1/workspace/load_data_csv data/Source1/workspace/
rm -rf fix_s1_pcpip_output && rm fix_s1_output.tar.gz

# Fix hardcoded paths in CSV files to use container paths
cd data/Source1/workspace/load_data_csv/Batch1/Plate1_trimmed
for csvfile in load_data_pipeline*.csv; do
  if [ -f "$csvfile" ]; then
    sed -i.bak \
      -e 's,/Users/shsingh/Documents/GitHub/starrynight/scratch/fix_s1_pcpip_output/,/app/data/,g' \
      -e 's/Plate1-Well/Plate1-/g' \
      "$csvfile"
  fi
done
cd -
```

## Usage

### 1. Run the Pipeline

Execute the complete PCPIP pipeline:
```bash
docker-compose up cellprofiler
```

### 2. Interactive Shell (Optional)

For debugging or manual execution:
```bash
docker-compose run --rm cellprofiler-shell
```

### 3. Check Results

All outputs are generated in `data/` - corrected images, analysis results, and logs in timestamped subdirectories.

## Pipeline Overview

Runs 7 CellProfiler pipelines in sequence:

1. **CP_Illum** → **CP_Apply_Illum** → **CP_SegmentationCheck**
2. **BC_Illum** → **BC_Apply_Illum** → **BC_Preprocess**
3. **Analysis** (final feature extraction)

*Configure in `scripts/run_pcpip.sh` as needed.*

## Troubleshooting

Check logs in `data/logs/[timestamp]/` for errors. For debugging:

```bash
# Interactive shell
docker-compose run --rm cellprofiler-shell

# Inside container
ls -la /app/data/     # Verify data structure
bash -x /app/scripts/run_pcpip.sh  # Run with debug output
```
