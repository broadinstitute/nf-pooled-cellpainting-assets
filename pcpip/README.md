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

Download the FIX-S1 test dataset. This dataset was created using scripts in the [StarryNight repository](https://github.com/broadinstitute/starrynight/tree/main/starrynight/tests/fixtures/integration/utils) that extract representative subsets from full pooled Cell Painting experiments.

```bash
# Download pre-processed data directly from S3
aws s3 sync s3://nf-pooled-cellpainting-sandbox/data/test-data/fix-s1/ data/ --no-sign-request
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
