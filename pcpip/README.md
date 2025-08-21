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

Execute specific pipeline steps using the `PIPELINE_STEP` environment variable:

```bash
# Run individual steps
PIPELINE_STEP=1 docker-compose run --rm cellprofiler
PIPELINE_STEP=4 docker-compose run --rm cellprofiler  # CP stitching (placeholder)
PIPELINE_STEP=8 docker-compose run --rm cellprofiler  # BC stitching (placeholder)
PIPELINE_STEP=9 docker-compose run --rm cellprofiler

# Run multiple steps
PIPELINE_STEP="1,2,3" docker-compose run --rm cellprofiler
PIPELINE_STEP="4,8" docker-compose run --rm cellprofiler

# Run by track
PIPELINE_STEP="1,2,3" docker-compose run --rm cellprofiler     # CP core
PIPELINE_STEP="5,6,7" docker-compose run --rm cellprofiler     # BC core
PIPELINE_STEP=4 docker-compose run --rm cellprofiler           # CP stitching
PIPELINE_STEP=8 docker-compose run --rm cellprofiler           # BC stitching
PIPELINE_STEP=9 docker-compose run --rm cellprofiler           # Analysis
```

> [!NOTE]
> `PIPELINE_STEP` is required - there is no default "run all" option since steps 4 and 8 will eventually use a separate Fiji container.

### 2. Interactive Shell (Optional)

For debugging or manual execution:
```bash
docker-compose run --rm cellprofiler-shell
```

### 3. Check Results

All outputs are generated in `data/` - corrected images, analysis results, and logs in timestamped subdirectories.

### 4. Cleanup

```bash
base_dir=data/Source1

dirs=(
    Batch1/illum
    Batch1/images_aligned
    Batch1/images_corrected
    Batch1/images_segmentation
    workspace/analysis
)

rm -rf -- "${dirs[@]/#/${base_dir}/}"
```

## Pipeline Overview

Runs 9 pipelines in sequence:

1. **CP_Illum** (Pipeline 1) - Calculate CP illumination correction
2. **CP_Apply_Illum** (Pipeline 2) - Apply CP illumination correction
3. **CP_SegmentationCheck** (Pipeline 3) - Validate CP segmentation
4. **CP_StitchCrop** (Pipeline 4) - Stitch CP images *(placeholder)*
5. **BC_Illum** (Pipeline 5) - Calculate BC illumination correction
6. **BC_Apply_Illum** (Pipeline 6) - Apply BC illumination correction
7. **BC_Preprocess** (Pipeline 7) - Preprocess barcoding images
8. **BC_StitchCrop** (Pipeline 8) - Stitch BC images *(placeholder)*
9. **Analysis** (Pipeline 9) - Final feature extraction

*Steps 4 and 8 are currently no-op placeholders for future ImageJ/Fiji integration.*

## Troubleshooting

Check logs in `data/logs/[timestamp]/` for errors. For debugging:

```bash
# Interactive shell
docker-compose run --rm cellprofiler-shell

# Inside container
ls -la /app/data/     # Verify data structure
bash -x /app/scripts/run_pcpip.sh  # Run with debug output
```
