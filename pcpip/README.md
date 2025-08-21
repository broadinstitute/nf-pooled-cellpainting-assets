# PCPIP Docker Demo

This directory contains a containerized demonstration of the PCPIP (Pooled Cell Painting Image Processing) pipeline. The demo implements a complete end-to-end workflow using both CellProfiler and ImageJ/Fiji in a multi-container architecture.

## Directory Structure

```
pcpip/
├── pipelines/                             # CellProfiler pipeline files (.cppipe)
├── plugins/                               # CellProfiler plugins (cloned separately)
├── scripts/                               # Processing scripts and utilities
│   ├── run_pcpip.sh                       # Main pipeline orchestration script
│   ├── stitch_crop.py                     # ImageJ/Fiji stitching and cropping
│   ├── transform_pipeline9_csv.py         # CSV transformation for cropped tiles
│   └── check_csv_files.py                 # File validation utility
├── references/                            # Documentation and specifications
│   └── pcpip-io.json                      # Pipeline input/output specifications
├── data/                                  # Unified data directory (inputs, outputs, logs)
│   ├── Source1/Batch1/
│   │   ├── images/                        # INPUT: Original microscopy images
│   │   ├── images_corrected/              # OUTPUT: Illumination-corrected images
│   │   ├── images_corrected_stitched/     # OUTPUT: Stitched whole-well images
│   │   ├── images_corrected_cropped/      # OUTPUT: Cropped tiles for analysis
│   │   ├── images_corrected_stitched_10X/ # OUTPUT: Downsampled QC images
│   │   ├── images_aligned/                # OUTPUT: Aligned barcode images
│   │   └── illum/                         # OUTPUT: Illumination correction files
│   └── workspace/
│       ├── load_data_csv/                 # INPUT: Pipeline CSV configurations
│       ├── analysis/                      # OUTPUT: Final analysis results
│       └── metadata/                      # INPUT: Metadata files
├── docker-compose.yml                     # Multi-container configuration
└── README.md                              # This file
```

## Prerequisites

- Docker and Docker Compose installed
- Git (for cloning plugins)
- `uv` (for running utility scripts)
- Input data in the expected format
- **For Pipeline 9 (Analysis)**: Docker Desktop memory ≥16GB (macOS/Windows only)
  - Open Docker Desktop → Settings → Resources → Advanced → Memory Limit: 16GB
  - Pipelines 1-8 work fine with default 8GB settings

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

### Run the Complete Workflow

Execute the full end-to-end workflow:

```bash
# 1. Cell Painting track (illumination correction)
PIPELINE_STEP="1,2,3" docker-compose run --rm cellprofiler

# 2. Cell Painting stitching and cropping
PIPELINE_STEP=4 docker-compose run --rm fiji

# 3. Barcoding track (illumination correction + preprocessing)
PIPELINE_STEP="5,6,7" docker-compose run --rm cellprofiler

# 4. Barcoding stitching and cropping
PIPELINE_STEP=8 docker-compose run --rm fiji

# 5. Analysis using cropped tiles (memory-intensive)
PIPELINE_STEP=9 docker-compose run --rm cellprofiler
```

### File Validation

Check if expected files exist using the validation utility:

```bash
# Verify cropped tile files exist for Pipeline 9
uv run scripts/check_csv_files.py data/Source1/workspace/load_data_csv/Batch1/Plate1_trimmed/load_data_pipeline9_cropped.csv
```

### Interactive Shell (Optional)

For debugging or manual execution:
```bash
docker-compose run --rm cellprofiler-shell  # CellProfiler environment
docker-compose run --rm fiji-shell          # ImageJ/Fiji environment
```

### Cleanup

```bash
base_dir=data/Source1/Batch1

# Remove output directories
rm -rf "${base_dir}"/illum \
       "${base_dir}"/images_aligned \
       "${base_dir}"/images_corrected*
```

## Pipeline Overview

Complete 9-step workflow with multi-container architecture:

| Step | Pipeline                 | Container    | Description                     |
| ---- | ------------------------ | ------------ | ------------------------------- |
| 1    | **CP_Illum**             | CellProfiler | Calculate painting illumination |
| 2    | **CP_Apply_Illum**       | CellProfiler | Apply painting illumination     |
| 3    | **CP_SegmentationCheck** | CellProfiler | Validate segmentation           |
| 4    | **CP_StitchCrop**        | **Fiji**     | Stitch & crop painting images   |
| 5    | **BC_Illum**             | CellProfiler | Calculate barcode illumination  |
| 6    | **BC_Apply_Illum**       | CellProfiler | Apply barcode illumination      |
| 7    | **BC_Preprocess**        | CellProfiler | Preprocess barcode images       |
| 8    | **BC_StitchCrop**        | **Fiji**     | Stitch & crop barcode images    |
| 9    | **Analysis**             | CellProfiler | Feature extraction from tiles   |

## Utility Scripts

```bash
# Transform Pipeline 9 CSV for cropped tiles
uv run scripts/transform_pipeline9_csv.py input.csv output.csv

# Validate file existence from CSV
uv run scripts/check_csv_files.py load_data.csv

# Interactive debugging
docker-compose run --rm cellprofiler-shell
docker-compose run --rm fiji-shell
```

## Troubleshooting

### Pipeline 9 Memory Issues
If Pipeline 9 gets killed, increase Docker Desktop memory to 24GB or 32GB (see Prerequisites).

### Common Issues

1. **Missing Files**: Use `check_csv_files.py` to verify expected files exist
2. **Memory Issues**: Stitching steps may require sequential execution for large datasets
3. **Path Errors**: Check that container paths (`/app/data/`) match expected structure

### Debug Commands

```bash
# Check logs
ls data/logs/*/        # Find latest timestamp
tail data/logs/*/pipeline*.log  # View recent logs

# Verify data structure
docker-compose run --rm cellprofiler-shell
ls -la /app/data/      # Inside container
```
