# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Supporting assets and resources for the pooled Cell Painting Nextflow pipeline, primarily containing the containerized PCPIP (Pooled Cell Painting Image Processing) demo workflow.

See [@README.md](README.md) and [@pcpip/README.md](pcpip/README.md) for complete documentation.

## Working Directory

Always work from the `pcpip/` directory when running pipeline commands.

## Critical Constraints

When working with this codebase, be aware of these critical requirements:

1. **Wells Consistency**: Wells in `load_data_filter.py` MUST match WELLS array in `run_pcpip.sh`
2. **Crop Consistency**: Same `CROP_PERCENT` must be used for preprocessing AND stitching (steps 4 & 8)
3. **LoadData CSVs**: Generated programmatically via `load_data_generate.py`, not manually edited
4. **Memory**: Pipeline 9 requires Docker Desktop with 16GB+ memory allocation
5. **Data Structure**: Strict adherence to `Source1/images/Batch1/` directory nesting required

## Quick Reference

```bash
# Setup (one-time)
cd pcpip/
git clone https://github.com/CellProfiler/CellProfiler-plugins.git plugins/

# Get pre-cropped test data (recommended for faster testing)
aws s3 sync s3://nf-pooled-cellpainting-sandbox/data/test-data/fix-s1_sub25/ data/ --profile cslab

# Generate LoadData CSVs
uv run scripts/load_data_filter.py --wells "A1"
uv run scripts/load_data_generate.py data/Source1/workspace/samplesheets/samplesheet1.csv --validate

# Run pipeline (see pcpip/README.md for complete workflow)
PIPELINE_STEP=1 docker-compose run --rm cellprofiler
# ... (refer to pcpip/README.md for full sequence)

# Debug shells
docker-compose run --rm cellprofiler-shell
docker-compose run --rm fiji-shell
docker-compose run --rm qc-shell

# Code quality
pre-commit run --all-files
ruff check --fix .
ruff format .
```

## Related Repositories

- Main pipeline: <https://github.com/seqera-services/nf-pooled-cellpainting>
- Infrastructure: <https://github.com/broadinstitute/nf-pooled-cellpainting-infra>
- Working directories may include: `/Users/shsingh/Documents/GitHub/nf/starrynight/`
