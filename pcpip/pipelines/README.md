# PCPIP Pipelines

This directory contains the core CellProfiler pipeline files (.cppipe) for the PCPIP workflow.

## Source

These pipeline files are sourced from the StarryNight repository:
https://github.com/broadinstitute/starrynight/tree/main/docs/developer/legacy/pcpip-pipelines

**Note**: These are reference pipeline files that have been carefully selected and trimmed in various ways from the original PCPIP workflow. They represent curated implementations that serve as references for the PCPIP processing sequence.

## Pipeline Files

- `ref_1_CP_Illum.cppipe` - Cell Painting illumination correction
- `ref_2_CP_Apply_Illum.cppipe` - Apply Cell Painting illumination correction
- `ref_3_CP_SegmentationCheck.cppipe` - Cell Painting segmentation validation
- `ref_5_BC_Illum.cppipe` - Barcode illumination correction
- `ref_6_BC_Apply_Illum.cppipe` - Apply barcode illumination correction
- `ref_7_BC_Preprocess.cppipe` - Barcode preprocessing
- `ref_9_Analysis.cppipe` - Final analysis and feature extraction

## Additional Resources

For additional documentation, comparisons, original 12-cycle versions, source variants, and pipeline visualizations, see the original StarryNight repository location above. The full collection includes pipeline diffs, visualizations in multiple formats (JSON, DOT, SVG, PNG), and development versions.
