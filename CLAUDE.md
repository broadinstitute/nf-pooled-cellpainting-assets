# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

Supporting assets and resources for the pooled Cell Painting Nextflow pipeline, primarily containing the containerized PCPIP (Pooled Cell Painting Image Processing) demo workflow.

## Key Commands

### Running the PCPIP Pipeline

Always run from the `pcpip/` directory:

```bash
cd pcpip/

# Prerequisites setup
git clone https://github.com/CellProfiler/CellProfiler-plugins.git plugins/
aws s3 sync s3://nf-pooled-cellpainting-sandbox/data/test-data/fix-s1/ data/ --no-sign-request

# Filter and generate LoadData CSVs
uv run scripts/load_data_filter.py --wells "A1"
uv run scripts/load_data_generate.py data/Source1/workspace/samplesheets/samplesheet1.csv --validate

# Run pipelines (in order)
PIPELINE_STEP=1 docker-compose run --rm cellprofiler
PIPELINE_STEP=1_qc_illum docker-compose run --rm qc
PIPELINE_STEP="2,3" docker-compose run --rm cellprofiler
PIPELINE_STEP=3_qc_seg docker-compose run --rm qc
PIPELINE_STEP=4 docker-compose run --rm fiji
PIPELINE_STEP=5 docker-compose run --rm cellprofiler
PIPELINE_STEP=5_qc_illum docker-compose run --rm qc
PIPELINE_STEP="6,7" docker-compose run --rm cellprofiler
PIPELINE_STEP=8 docker-compose run --rm fiji
PIPELINE_STEP=9 docker-compose run --rm cellprofiler
```

### Cropping Images for Faster Testing

```bash
# Crop to 25% size (overwrites originals)
CROP_PERCENT=25 docker-compose run --rm cellprofiler python3 /app/scripts/crop_preprocess.py

# When running stitching after cropping, use same CROP_PERCENT
CROP_PERCENT=25 PIPELINE_STEP=4 docker-compose run --rm fiji
CROP_PERCENT=25 PIPELINE_STEP=8 docker-compose run --rm fiji
```

### Interactive Debugging

```bash
docker-compose run --rm cellprofiler-shell
docker-compose run --rm fiji-shell
docker-compose run --rm qc-shell
```

### QC Visualization

```bash
# Using Pixi (locally)
pixi exec -c conda-forge --spec python=3.13 --spec numpy=2.3.3 --spec pillow=11.3.0 -- \
  python scripts/montage.py data/Source1/images/Batch1/illum/Plate1 output.png --pattern ".*\\.npy$"
```

### Linting and Code Quality

```bash
# Pre-commit hooks are configured
pre-commit run --all-files

# Ruff is used for Python linting/formatting
ruff check --fix .
ruff format .
```

## Architecture Overview

### Pipeline Processing Flow

The PCPIP workflow consists of 9 main pipelines split across two tracks:

**Cell Painting Track (Pipelines 1-4):**

- Pipeline 1: Calculate illumination correction functions
- Pipeline 2: Apply corrections and segment cells
- Pipeline 3: Verify segmentation quality
- Pipeline 4: Stitch fields of view and crop into tiles

**Barcoding Track (Pipelines 5-8):**

- Pipeline 5: Calculate illumination corrections for barcoding
- Pipeline 6: Apply corrections and align cycles
- Pipeline 7: Compensate channels and call barcodes
- Pipeline 8: Stitch and crop (matching Cell Painting crops)

**Analysis (Pipeline 9):**

- Aligns Cell Painting and Barcoding images
- Performs final segmentation and feature measurement

### Container Architecture

Three specialized Docker containers handle different pipeline components:

- **cellprofiler**: Runs CellProfiler-based pipelines (1-3, 5-7, 9)
- **fiji**: Handles ImageJ/Fiji stitching operations (4, 8)
- **qc**: Generates QC visualization montages using Python

Containers are orchestrated via `docker-compose.yml` with the `PIPELINE_STEP` environment variable controlling execution.

### Critical Data Flow

1. **Wells filtering**: The wells specified in `load_data_filter.py` MUST match those in `run_pcpip.sh` WELLS array
2. **LoadData CSVs**: Generated programmatically from samplesheet metadata, not manually edited
3. **Crop percentage**: Must be consistent between preprocessing and stitching steps
4. **Output structure**: Follows Source1/images/Batch1/ nesting pattern

### Key Script Responsibilities

- `run_pcpip.sh`: Main orchestration script that routes to appropriate pipeline based on PIPELINE_STEP
- `load_data_filter.py`: Filters LoadData CSVs to specific wells for processing
- `load_data_generate.py`: Creates LoadData CSVs from samplesheet with validation
- `stitch_crop.py`: ImageJ/Fiji script for stitching and cropping operations
- `montage.py`: Creates visual QC montages from pipeline outputs
- `crop_preprocess.py`: Crops input images for faster testing (destructive operation)

## Important Constraints

1. **Memory Requirements**: Pipeline 9 requires Docker Desktop with 16GB+ memory allocation
2. **Well Consistency**: Wells in LoadData CSVs must match WELLS array in run_pcpip.sh
3. **Plugin Dependencies**: CellProfiler plugins must be cloned before running pipelines
4. **Crop Consistency**: Same CROP_PERCENT must be used for preprocessing and stitching
5. **Data Path Structure**: Strict adherence to Source1/images/Batch1/ directory structure required

## Related Repositories

- Main pipeline: <https://github.com/seqera-services/nf-pooled-cellpainting>
- Infrastructure: <https://github.com/broadinstitute/nf-pooled-cellpainting-infra>
- Working directories may include: `/Users/shsingh/Documents/GitHub/nf/starrynight/`
