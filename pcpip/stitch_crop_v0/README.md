# Stitch & Crop v0 - Usage Guide

Fiji-based stitching and cropping workflow.

## Provenance

The core Jython script `stitch_crop_v0.py` is a verbatim copy of the original reference implementation:

**Source:** <https://github.com/broadinstitute/pooled-cell-painting-image-processing/blob/a06b3ae6072c35ee79b4ba27bdb943240ca90c02/FIJI/BatchStitchPooledCellPainting_StitchAndCrop_Headless.py>

This is the reference implementation for the stitching workflow. The wrapper scripts (`stitch_crop_v0_run.sh`, `stitch_crop_v0_flatten.py`) and documentation were created to enable local Docker-based execution.

**Note:** This guide uses the **fix-s1** test data fixture (3 wells × 4 sites, 2×2 grid) for all examples. Commands and output file counts are specific to fix-s1 but the workflow is expected to apply to any dataset.

## Prerequisites

- Docker with `cellprofiler/distributed-fiji:latest` image
- Input images from CellProfiler pipelines (corrected images organized by site)

## Workflow Steps

### Step 1: Flatten Directory Structure

The Fiji stitching script expects all images in a flat directory. The original script includes internal flattening when downloading from AWS, but for local file workflows (required for Nextflow integration), external flattening is necessary. Convert nested site folders to flat structure:

```bash
cd pcpip/
python stitch_crop_v0/stitch_crop_v0_flatten.py \
  --source data/Source1/images/Batch1/images_corrected \
  --target data/Source1/images/Batch1/images_corrected_flattened \
  --track painting  # or 'barcoding' or 'both'
```

**Input structure:**

```text
images_corrected/painting/Plate1/
  Plate1-A1-0/
    Plate_Plate1_Well_A1_Site_0_CorrDNA.tiff
    Plate_Plate1_Well_A1_Site_0_CorrCHN2.tiff
    ...
  Plate1-A1-1/
    ...
```

**Output structure:**

```text
images_corrected_flattened/painting/Plate1/
  Plate_Plate1_Well_A1_Site_0_CorrDNA.tiff
  Plate_Plate1_Well_A1_Site_0_CorrCHN2.tiff
  Plate_Plate1_Well_A1_Site_1_CorrDNA.tiff
  ...
```

### Step 2: Stitch and Crop

Run the Fiji stitching workflow via Docker:

```bash
cd pcpip/
./stitch_crop_v0/stitch_crop_v0_run.sh
```

**Configure via environment variables:**

```bash
# Painting track
SC_PLATE=Plate1 SC_WELL=A1 SC_TRACK=painting ./stitch_crop_v0/stitch_crop_v0_run.sh

# Barcoding track
SC_PLATE=Plate1 SC_WELL=A1 SC_TRACK=barcoding ./stitch_crop_v0/stitch_crop_v0_run.sh

# Custom paths
SC_HOST_DATA_DIR=/path/to/data \
SC_WORKDIR=/app/data/Source1/images/Batch1 \
SC_PLATE=Plate2 \
SC_WELL=B3 \
./stitch_crop_v0/stitch_crop_v0_run.sh
```

**Key environment variables:**

- `SC_PLATE` - Plate name (default: `Plate1`)
- `SC_WELL` - Well name (default: `A1`)
- `SC_TRACK` - Track type: `painting` or `barcoding` (default: `painting`)
- `SC_TILE_SIZE` - Input tile size in pixels (default: `400` for 25% cropped)
- `SC_HOST_DATA_DIR` - Host data directory to mount (auto-detected)
- `SC_WORKDIR` - Working directory inside container (default: `/app/data/Source1/images/Batch1`)

See script header for full list of configurable parameters.

## Expected Output

Output is created at `$SC_WORKDIR/output/` (default: `data/Source1/images/Batch1/output/`):

### Painting Track (3 channels → 18 TIFFs)

```text
output/
├── painting_stitched/          # Full-resolution stitched whole-well images
│   └── Plate1-A1/
│       ├── StitchedPlate_Plate1_Well_A1_Site__CorrDNA.tiff      (1600×1600)
│       ├── StitchedPlate_Plate1_Well_A1_Site__CorrCHN2.tiff
│       └── StitchedPlate_Plate1_Well_A1_Site__CorrPhalloidin.tiff
├── painting_stitched_10X/      # Downsampled QC previews (160×160)
└── painting_cropped/           # Cropped tiles for downstream analysis (800×800)
    └── Plate1-A1/
        ├── CorrDNA/           [4 tiles: Site_1.tiff ... Site_4.tiff]
        ├── CorrCHN2/          [4 tiles per channel]
        └── CorrPhalloidin/    [4 tiles per channel]
```

### Barcoding Track (13 channels → 78 TIFFs)

```text
output/
├── barcoding_stitched/
│   └── Plate1-A1/
│       ├── StitchedPlate_Plate1_Well_A1_Site__Cycle01_DNA.tiff
│       ├── StitchedPlate_Plate1_Well_A1_Site__Cycle01_A.tiff
│       └── ... [Cycle01-03 × A/C/G/T + DNA per cycle = 13 channels]
├── barcoding_stitched_10X/
└── barcoding_cropped/
    └── Plate1-A1/
        ├── Cycle01_DNA/       [4 tiles per channel × 13 channels = 52 tiles]
        ├── Cycle01_A/
        └── ... [13 channel subdirectories]
```

**Output formats:**

- **Stitched images**: Full-resolution whole-well composite (1600×1600 for 2×2 grid with 400px tiles)
- **10X images**: Downsampled previews (160×160) for quick QC visualization
- **Cropped tiles**: Regular grid of tiles (800×800, 4 per channel) for CellProfiler analysis

### Step 3: Restructure to Production Format (Optional)

Convert legacy output to production `stitch_crop.py` format for comparison or validation:

```bash
cd pcpip/

# Preview transformations (dry run)
python stitch_crop_v0/stitch_crop_v0_restructure.py \
  --source data/Source1/images/Batch1/output \
  --dest data/Source1/images/Batch1 \
  --dry-run

# Execute conversion
python stitch_crop_v0/stitch_crop_v0_restructure.py \
  --source data/Source1/images/Batch1/output \
  --dest data/Source1/images/Batch1 \
  --execute
```

**Transformations:**

- Directory: `output/{track}_{type}/` → `images_corrected_{type}/{track}/{plate}/`
- Stitched: `StitchedPlate_Plate1_Well_A1_Site__CorrDNA.tiff` → `Plate1-A1-CorrDNA-Stitched.tiff`
- Cropped: `CorrDNA/CorrDNA_Site_1.tiff` → `Plate_Plate1_Well_A1_Site_1_CorrDNA.tiff`

Script copies files (preserves originals) and is idempotent (skips existing files).

## Notes

- Script uses Fiji Grid/Collection stitching with computed overlap
- Output dimensions depend on `SC_TILE_SIZE` and grid layout (2×2 default)
- Barcoding track processes all cycles × channels (e.g., Cycle01-03 × A/C/G/T/DNA)
- Same process applies to both painting and barcoding tracks
