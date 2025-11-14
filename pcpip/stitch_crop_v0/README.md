# Stitch & Crop v0 - Usage Guide

Legacy Fiji-based stitching and cropping workflow.

## Prerequisites

- Docker with `cellprofiler/distributed-fiji:latest` image
- Input images from CellProfiler pipelines (corrected images organized by site)

## Workflow Steps

### Step 1: Flatten Directory Structure

The Fiji stitching script expects all images in a flat directory. Convert nested site folders to flat structure:

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
# Minimal - just specify plate/well
SC_PLATE=Plate1 SC_WELL=A1 ./scripts/stitch_crop_v0_run.sh

# Barcoding track
SC_PLATE=Plate1 SC_WELL=A1 SC_TRACK=barcoding ./scripts/stitch_crop_v0_run.sh

# Custom paths
SC_HOST_DATA_DIR=/path/to/data \
SC_WORKDIR=/app/data/Source1/images/Batch1 \
SC_PLATE=Plate2 \
SC_WELL=B3 \
./scripts/stitch_crop_v0_run.sh
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

```text
output/
├── painting_stitched/          # Full-resolution stitched whole-well images
│   └── Plate1-A1/
│       ├── StitchedPlate_Plate1_Well_A1_Site__CorrDNA.tiff      (1600×1600)
│       ├── StitchedPlate_Plate1_Well_A1_Site__CorrCHN2.tiff
│       ├── StitchedPlate_Plate1_Well_A1_Site__CorrPhalloidin.tiff
│       └── TileConfiguration*.txt                               (stitching logs)
│
├── painting_stitched_10X/      # Downsampled QC previews
│   └── Plate1-A1/
│       └── [3 downsampled TIFFs at 160×160]
│
└── painting_cropped/           # Cropped tiles for downstream analysis
    └── Plate1-A1/
        ├── CorrDNA/
        │   ├── CorrDNA_Site_1.tiff                              (800×800)
        │   ├── CorrDNA_Site_2.tiff
        │   ├── CorrDNA_Site_3.tiff
        │   └── CorrDNA_Site_4.tiff
        ├── CorrCHN2/
        │   └── [4 tiles per channel]
        └── CorrPhalloidin/
            └── [4 tiles per channel]
```

**Output formats:**

- **Stitched images**: Full-resolution, scaled and padded whole-well composite (1600×1600 for 2×2 grid)
- **10X images**: Downsampled previews for quick QC visualization
- **Cropped tiles**: Regular grid of tiles (800×800) for CellProfiler analysis

## Notes

- Script uses Fiji Grid/Collection stitching with computed overlap
- Output dimensions depend on `SC_TILE_SIZE` and grid layout (2×2 default)
- Barcoding track processes all cycles × channels (e.g., Cycle01-03 × A/C/G/T/DNA)
- Same process applies to both painting and barcoding tracks
