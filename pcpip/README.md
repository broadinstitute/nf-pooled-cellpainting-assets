# PCPIP Docker Setup

This directory contains a containerized version of the PCPIP (Pooled Cell Painting Image Processing) pipeline using CellProfiler.

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
│   │   │   ├── images/                    # Original microscopy images
│   │   │   ├── images_corrected/          # Pipeline-corrected images
│   │   │   ├── images_aligned/            # Aligned barcode images
│   │   │   ├── images_segmentation/       # Segmentation results
│   │   │   └── illum/                     # Illumination correction files
│   │   └── workspace/
│   │       ├── load_data_csv/             # Pipeline CSV configurations
│   │       ├── analysis/                  # Final analysis results
│   │       └── metadata/                  # Metadata files
│   └── logs/                              # Timestamped execution logs
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

## Pipeline Sequence

The script runs 7 CellProfiler pipelines in sequence:

1. **Pipeline 1**: CP_Illum (illumination correction)
2. **Pipeline 2**: CP_Apply_Illum (apply illumination correction)
3. **Pipeline 3**: CP_SegmentationCheck (segmentation validation)
4. **Pipeline 5**: BC_Illum (barcode illumination)
5. **Pipeline 6**: BC_Apply_Illum (apply barcode illumination)
6. **Pipeline 7**: BC_Preprocess (barcode preprocessing)
7. **Pipeline 9**: Analysis (final analysis)

## Configuration

The pipeline processes:
- **Plate**: Plate1
- **Wells**: WellA1, WellA2, WellB1
- **Sites**: 0, 1
- **SBS Cycles**: 1, 2, 3

Modify these values in `scripts/run_pcpip.sh` as needed.

## Troubleshooting

- Check logs in `data/logs/[timestamp]/`
- Ensure input data structure matches expected format
- Verify all required CSV files are present
- For plugin issues, check `plugins/CellProfiler-plugins/active_plugins/`

### Debug Steps

If the pipeline fails, try the interactive shell to debug:

```bash
# Start interactive shell
docker-compose run --rm cellprofiler-shell

# Inside the container, check:
ls -la /app/data/     # Verify data structure
ls -la /app/pipelines/      # Verify pipeline files
ls -la /app/plugins/        # Verify plugins
ls -la /app/data/Source1/workspace/load_data_csv/  # Check CSV files
bash -x /app/scripts/run_pcpip.sh  # Run script with debug output
```

## Notes

- The `plugins/` directory is not included in this repository - clone it separately as shown in setup
- Use `.gitignore` to prevent committing large datasets in `data/` directories and the `plugins/` directory
- For plugin documentation and issues, see the [CellProfiler-plugins repository](https://github.com/CellProfiler/CellProfiler-plugins)
