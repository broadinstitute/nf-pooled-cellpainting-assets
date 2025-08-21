# CLAUDE.md - AI Assistant Context

## Project Overview
This repository contains **nf-pooled-cellpainting-assets**, supporting assets for Nextflow-based pooled cell painting analysis pipelines. This repo houses reusable components, reference implementations, and demo workflows.

### Repository Structure
- `pcpip/` - Miniaturized PCPIP demo (containerized CellProfiler workflow)
- *(Future)* - Additional pipeline components, reference datasets, shared configs, etc.

### Current Focus: PCPIP Demo (`pcpip/`)
- **Purpose**: Reference implementation of PCPIP workflow
- **Scope**: End-to-end demo that runs in a single script
- **Technology**: Docker + CellProfiler 4.2.6 + Bio-Formats

## General Principles

### Repository Organization
- **Self-contained components**: Each directory should be independently usable
- **Documentation-first**: Every component includes README.md with setup/usage
- **Containerization**: Prefer Docker for reproducibility and portability
- **Reference implementations**: Provide working examples, not just configs

### Asset Categories *(as repo grows)*
- **Demo workflows**: Complete end-to-end examples (like `pcpip/`)
- **Shared configurations**: Reusable configs for Nextflow/CellProfiler/etc.
- **Reference datasets**: Curated test data for validation
- **Utility scripts**: Common tools for pipeline development

## Domain Knowledge

### Cell Painting Pipeline Stages
1. **CP_Illum**: Calculate illumination correction from painting images
2. **CP_Apply_Illum**: Apply corrections to painting images
3. **CP_SegmentationCheck**: Validate cell segmentation quality
4. **BC_Illum**: Calculate illumination correction for barcode images
5. **BC_Apply_Illum**: Apply corrections to barcode images
6. **BC_Preprocess**: Barcode preprocessing (requires plugins)
7. **Analysis**: Feature extraction and colocalization analysis

### File Types & Formats
- **Images**: `.ome.tiff` files with Bio-Formats metadata
- **Pipelines**: `.cppipe` files (CellProfiler pipeline definitions)
- **Data**: CSV files with path/metadata configurations
- **Outputs**: TIFF images, HDF5 measurements, analysis CSVs

## Common Tasks

### Modifying Pipeline Configuration
- Edit `scripts/run_pcpip.sh` variables: `PLATE`, `WELLS`, `SITES`, `CYCLES`
- Pipeline execution controlled by `PIPELINE_CONFIG` associative array
- Memory behavior: Set `background="false"` for sequential execution

### Path Handling
- **Setup**: CSV files need path corrections for containerization
- **Pattern**: Replace hardcoded host paths with `/app/data/`
- **Well directories**: Convert `Plate1-WellA1` → `Plate1-A1` format

### Debugging Approach
1. Check logs in `data/logs/[timestamp]/`
2. Use interactive shell: `docker-compose run --rm cellprofiler-shell`
3. Verify data structure: `ls -la /app/data/`
4. Run with debug: `bash -x /app/scripts/run_pcpip.sh`

## Important Gotchas

### Memory Issues
- **Symptom**: Processes getting killed during pipeline 6-9
- **Cause**: Multiple CellProfiler instances + Java + large images
- **Solution**: Sequential execution for heavy pipelines

### CSV Path Corrections
- Downloaded datasets contain hardcoded host paths
- Must run sed replacements during setup
- Both host paths AND well directory naming need fixes

### Plugin Dependencies
- Pipelines 7,9 require CellProfiler-plugins repository
- Clone to `plugins/` directory before running
- Plugin path: `/app/plugins/active_plugins/` in container

## File Priorities

### Critical Files
- `scripts/run_pcpip.sh`: Main orchestration script
- `docker-compose.yml`: Container configuration
- `pipelines/*.cppipe`: CellProfiler pipeline definitions
- `README.md`: User-facing documentation

### Configuration Files
- `.gitignore`: Excludes data/ and plugins/
- `.pre-commit-config.yaml`: Code quality hooks

## Development Workflow
1. **Test locally**: Use miniaturized dataset
2. **Memory-aware**: Consider parallel vs sequential execution
3. **Container-first**: All paths assume containerized environment
4. **Document changes**: Keep README.md current with major changes

## Testing
- **Dataset**: FIX-S1 test data from starrynight releases
- **Validation**: Check output directories and log files
- **Performance**: Monitor memory usage during execution
