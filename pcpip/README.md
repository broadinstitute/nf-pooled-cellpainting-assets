# PCPIP Docker Demo

Containerized PCPIP (Pooled Cell Painting Image Processing) pipeline demo using CellProfiler and Fiji.

## Quick Start

### Prerequisites
- Docker Desktop with **16GB memory** for Pipeline 9 (Settings → Resources → Advanced)
- Git and `uv` installed

### Setup & Run

```bash
# Run all commands from the pcpip/ directory
cd pcpip/

# 1. Clone plugins
git clone https://github.com/CellProfiler/CellProfiler-plugins.git plugins/active_plugins

# 2. Get test data (~3GB)
aws s3 sync s3://nf-pooled-cellpainting-sandbox/data/test-data/fix-s1/ data/ --no-sign-request

# 3. Run complete workflow
PIPELINE_STEP="1,2,3" docker-compose run --rm cellprofiler  # Cell painting illumination
PIPELINE_STEP=4 docker-compose run --rm fiji                # Cell painting stitching
PIPELINE_STEP="5,6,7" docker-compose run --rm cellprofiler  # Barcoding processing
PIPELINE_STEP=8 docker-compose run --rm fiji                # Barcoding stitching
PIPELINE_STEP=9 docker-compose run --rm cellprofiler        # Analysis (needs 16GB RAM)
```

<details>
<summary>Pipeline Details</summary>

| Step | Name                 | Container    | Description                                |
| ---- | -------------------- | ------------ | ------------------------------------------ |
| 1    | CP_Illum             | CellProfiler | Calculate painting illumination correction |
| 2    | CP_Apply_Illum       | CellProfiler | Apply painting illumination correction     |
| 3    | CP_SegmentationCheck | CellProfiler | Validate cell segmentation                 |
| 4    | CP_StitchCrop        | Fiji         | Stitch & crop painting images              |
| 5    | BC_Illum             | CellProfiler | Calculate barcode illumination correction  |
| 6    | BC_Apply_Illum       | CellProfiler | Apply barcode illumination correction      |
| 7    | BC_Preprocess        | CellProfiler | Preprocess barcode images with plugins     |
| 8    | BC_StitchCrop        | Fiji         | Stitch & crop barcode images               |
| 9    | Analysis             | CellProfiler | Feature extraction from cropped tiles      |
</details>

## Reference

### Directory Structure

```
pcpip/
├── pipelines/                             # CellProfiler pipeline files (.cppipe)
├── plugins/                               # CellProfiler plugins (cloned separately)
├── scripts/                               # Processing scripts and utilities
│   ├── run_pcpip.sh                       # Main pipeline orchestration script
│   ├── stitch_crop.py                     # ImageJ/Fiji stitching and cropping
│   ├── transform_pipeline9_csv.py         # CSV transformation for cropped tiles
│   └── check_csv_files.py                 # File validation utility
├── data/                                  # Unified data directory
└── docker-compose.yml                     # Container configuration
```


### Troubleshooting

### Pipeline 9 Memory Issues

- Requires Docker Desktop with 16GB+ memory allocation
- If still failing, increase to 24GB or 32GB

### Debug Commands

```bash
# Check logs
ls data/logs/*/
tail data/logs/*/pipeline*.log

# Interactive shells
docker-compose run --rm cellprofiler-shell
docker-compose run --rm fiji-shell

# Cleanup outputs
rm -rf data/Source1/Batch1/{illum,images_aligned,images_corrected*}
```

### Utility Scripts

```bash
# Transform Pipeline 9 CSV for cropped tiles
uv run scripts/transform_pipeline9_csv.py input.csv output.csv

# Validate files exist
uv run scripts/check_csv_files.py load_data.csv
```
