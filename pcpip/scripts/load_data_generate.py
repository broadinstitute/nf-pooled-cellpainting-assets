#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "pandas",
# ]
# ///
"""
LoadData CSV generator for PCPIP CellProfiler pipelines.

Generates LoadData CSVs by predicting output filenames from patterns, eliminating
the need for filesystem scanning. Each pipeline's outputs are deterministic based
on the input samplesheet metadata.

Key concepts:
- Pipelines 1,5: Read raw images, output illumination functions
- Pipelines 2,6: Apply illumination using outputs from 1,5
- Pipelines 3,7: Use corrected images from 2,6 (no scanning needed - we predict the names)
- Pipeline 9: Uses stitched tiles from pipelines 4,8 (FIJI-based, not implemented here)

Nextflow handles file staging into img1/, img2/ subdirectories at runtime.
LoadData CSVs specify the actual input file paths.

Usage:
  uv run scripts/load_data_generate.py data/Source1/workspace/samplesheets/samplesheet1.csv
"""

import pandas as pd
from pathlib import Path

# Default base path used in load_data CSVs (can be overridden via CLI)
DEFAULT_BASE_PATH = "/app/data/Source1/images/Batch1"


def pipeline1(samplesheet_df, base_path=None):
    """
    Pipeline 1: Cell Painting Illumination Calculation
    Input: Raw painting images
    Output: {Plate}_Illum{Channel}.npy
    Groups by: plate
    """
    base_path = base_path or DEFAULT_BASE_PATH
    df = samplesheet_df[samplesheet_df.arm == "painting"]
    rows = []

    for _, row in df.iterrows():
        channels = row["channels"].split(",")
        filename = Path(row["path"]).name
        # Extract parent directory (acquisition folder) from the full path
        # E.g., .../Plate1/20X_CP_Plate1_20240319_122800_179/WellA1_Point...
        # We need the acquisition folder name (parent of the image file)
        acq_folder = Path(row["path"]).parent.name
        plate_dir = (
            f"{base_path}/images/{row['plate']}/{acq_folder}/"  # Add trailing slash
        )

        data = {
            "Metadata_Plate": row["plate"],
            "Metadata_Site": row["site"],
            "Metadata_Well": row["well"],
        }

        # Add all data naturally without worrying about column order
        for ch in channels:
            data[f"PathName_Orig{ch}"] = plate_dir
            data[f"FileName_Orig{ch}"] = filename
            data[f"Frame_Orig{ch}"] = channels.index(ch)

        rows.append(data)

    return pd.DataFrame(rows)


def pipeline2(samplesheet_df, base_path=None):
    """
    Pipeline 2: Cell Painting Apply Illumination
    Input: Raw images + illumination functions
    Output: Plate_{Plate}_Well_{Well}_Site_{Site}_Corr{Channel}.tiff
    Groups by: plate, well
    """
    base_path = base_path or DEFAULT_BASE_PATH
    df = samplesheet_df[samplesheet_df.arm == "painting"]
    rows = []

    for _, row in df.iterrows():
        channels = row["channels"].split(",")
        filename = Path(row["path"]).name
        acq_folder = Path(row["path"]).parent.name
        plate_dir = (
            f"{base_path}/images/{row['plate']}/{acq_folder}/"  # Add trailing slash
        )
        illum_dir = f"{base_path}/illum/{row['plate']}"  # No trailing slash for illum

        data = {
            "Metadata_Plate": row["plate"],
            "Metadata_Site": row["site"],
            "Metadata_Well": row["well"],
        }

        # Add all data naturally without worrying about column order
        for ch in channels:
            data[f"PathName_Orig{ch}"] = plate_dir
            data[f"FileName_Orig{ch}"] = filename
            data[f"Frame_Orig{ch}"] = channels.index(ch)
            data[f"PathName_Illum{ch}"] = illum_dir
            data[f"FileName_Illum{ch}"] = f"{row['plate']}_Illum{ch}.npy"

        rows.append(data)

    return pd.DataFrame(rows)


def pipeline3(samplesheet_df, base_path=None, qc_sites=None):
    """
    Pipeline 3: Cell Painting Segmentation Check
    Input: Corrected images from Pipeline 2
    Output: QC metrics (no new images)
    """
    base_path = base_path or DEFAULT_BASE_PATH
    df = samplesheet_df[samplesheet_df.arm == "painting"]
    rows = []

    # Sample subset for QC
    if qc_sites is None:
        qc_sites = [0, 2]

    for _, row in df[df.site.isin(qc_sites)].iterrows():
        channels = row["channels"].split(",")
        output_dir = f"{base_path}/images_corrected/painting/{row['plate']}/{row['plate']}-{row['well']}-{row['site']}/"  # Add trailing slash

        data = {
            "Metadata_Plate": row["plate"],
            "Metadata_Site": row["site"],
            "Metadata_Well": row["well"]
        }

        # Add all data naturally without worrying about column order
        for ch in channels:
            data[f"PathName_{ch}"] = output_dir
            data[f"FileName_{ch}"] = (
                f"Plate_{row['plate']}_Well_{row['well']}_Site_{row['site']}_Corr{ch}.tiff"
            )

        rows.append(data)

    return pd.DataFrame(rows)


def pipeline4(samplesheet_df):
    """
    Pipeline 4: Cell Painting Stitching (FIJI)
    Input: Corrected images from Pipeline 2
    Output: Stitched whole-well images and cropped tiles
    Note: Not CellProfiler - this would be metadata for FIJI
    """
    # Pipeline 4 uses FIJI, not CellProfiler, so no load_data.csv
    # But we can predict outputs for Pipeline 9
    pass


def pipeline5(samplesheet_df, base_path=None):
    """
    Pipeline 5: Barcoding Illumination Calculation
    Input: Raw barcoding images
    Output: {Plate}_Cycle{N}_Illum{Channel}.npy
    Groups by: plate, cycle
    """
    base_path = base_path or DEFAULT_BASE_PATH
    df = samplesheet_df[samplesheet_df.arm == "barcoding"]
    rows = []

    for _, row in df.iterrows():
        channels = row["channels"].split(",")
        filename = Path(row["path"]).name
        # Extract actual acquisition folder from path instead of hardcoding
        acq_folder = Path(row["path"]).parent.name
        cycle_dir = (
            f"{base_path}/images/{row['plate']}/{acq_folder}/"  # Add trailing slash
        )

        data = {
            "Metadata_Plate": row["plate"],
            "Metadata_Site": row["site"],
            "Metadata_Cycle": row["cycle"],
            "Metadata_Well": row["well"],
        }

        # Add all data naturally without worrying about column order
        for ch in channels:
            data[f"PathName_Orig{ch}"] = cycle_dir
            data[f"FileName_Orig{ch}"] = filename
            data[f"Frame_Orig{ch}"] = channels.index(ch)

        rows.append(data)

    return pd.DataFrame(rows)


def pipeline6(samplesheet_df, base_path=None):
    """
    Pipeline 6: Barcoding Apply Illumination + Alignment

    Complex cycle-based format where columns are Cycle{NN}_{Channel}_{Orig|Illum}.
    Groups across cycles to align multi-cycle barcoding sequences.
    """
    base_path = base_path or DEFAULT_BASE_PATH
    df = samplesheet_df[samplesheet_df.arm == "barcoding"]
    rows = []

    for (well, site), group in df.groupby(["well", "site"]):
        plate = group.iloc[0]["plate"]
        channels = group.iloc[0]["channels"].split(",")

        data = {
            "Metadata_Plate": plate,
            "Metadata_Site": site,
            "Metadata_Well": well
        }

        # Build paths for each cycle
        for cycle in sorted(group["cycle"].unique()):
            cycle_row = group[group["cycle"] == cycle].iloc[0]
            # Extract actual acquisition folder from path instead of hardcoding
            acq_folder = Path(cycle_row["path"]).parent.name
            cycle_dir = (
                f"{base_path}/images/{plate}/{acq_folder}/"  # Add trailing slash
            )
            illum_dir = f"{base_path}/illum/{plate}"  # No trailing slash for illum

            for ch in channels:
                # Use different naming convention for pipeline 6
                # Original images
                data[f"PathName_Cycle{cycle:02d}_Orig{ch}"] = cycle_dir
                data[f"FileName_Cycle{cycle:02d}_Orig{ch}"] = Path(
                    cycle_row["path"]
                ).name
                data[f"Frame_Cycle{cycle:02d}_Orig{ch}"] = channels.index(ch)

                # Illumination files
                data[f"PathName_Cycle{cycle:02d}_Illum{ch}"] = illum_dir
                data[f"FileName_Cycle{cycle:02d}_Illum{ch}"] = (
                    f"{plate}_Cycle{cycle}_Illum{ch}.npy"
                )
                # Add Frame column for illumination (even though .npy files don't have frames)
                data[f"Frame_Cycle{cycle:02d}_Illum{ch}"] = 0

        rows.append(data)

    return pd.DataFrame(rows)


def pipeline7(samplesheet_df, base_path=None):
    """
    Pipeline 7: Barcode Preprocessing
    Input: Aligned images from Pipeline 6
    Output: Preprocessed images for barcode calling
    """
    base_path = base_path or DEFAULT_BASE_PATH
    df = samplesheet_df[samplesheet_df.arm == "barcoding"]
    rows = []

    for (well, site), group in df.groupby(["well", "site"]):
        plate = group.iloc[0]["plate"]
        channels = group.iloc[0]["channels"].split(",")
        output_dir = f"{base_path}/images_aligned/barcoding/{plate}/{plate}-{well}/"  # Well-level dir (Pipeline 6 groups by well)

        data = {
            "Metadata_Plate": plate,
            "Metadata_Site": site,
            "Metadata_Well": well
        }

        # Predict Pipeline 6 outputs for each cycle/channel
        for cycle in sorted(group["cycle"].unique()):
            for ch in channels:
                if ch == "DNA":
                    # DNA only from cycle 1
                    if cycle == 1:
                        col = f"Cycle{cycle:02d}_DNA"
                        data[f"PathName_{col}"] = output_dir
                        data[f"FileName_{col}"] = (
                            f"Plate_{plate}_Well_{well}_Site_{site}_{col}.tiff"
                        )
                else:
                    col = f"Cycle{cycle:02d}_{ch}"
                    data[f"PathName_{col}"] = output_dir
                    data[f"FileName_{col}"] = (
                        f"Plate_{plate}_Well_{well}_Site_{site}_{col}.tiff"
                    )

        rows.append(data)

    return pd.DataFrame(rows)


def pipeline8(samplesheet_df):
    """
    Pipeline 8: Barcoding Stitching (FIJI)
    Input: Preprocessed barcoding images
    Output: Stitched and cropped tiles
    Note: Not CellProfiler - this would be metadata for FIJI
    """
    # Pipeline 8 uses FIJI, not CellProfiler
    pass


def pipeline9(samplesheet_df, base_path=None, tiles_per_well=None):
    """
    Pipeline 9: Combined Analysis
    Input: Cropped tiles from Pipelines 4 & 8
    Output: Final measurements
    Groups by: well, tile
    """
    base_path = base_path or DEFAULT_BASE_PATH
    df = samplesheet_df[samplesheet_df.arm == "barcoding"]
    rows = []

    # Tiles created by stitching - predict based on grid
    if tiles_per_well is None:
        tiles_per_well = 4  # 2x2 grid for this dataset

    for well in df["well"].unique():
        plate = df.iloc[0]["plate"]
        channels_bc = ["A", "C", "T", "G"]
        channels_cp = ["DNA", "CHN2", "Phalloidin"]

        for tile in range(1, tiles_per_well + 1):
            data = {
                "Metadata_Plate": plate,
                "Metadata_Site": tile,  # Tile number as site
                "Metadata_Well": well
            }

            # Barcoding channels from all cycles
            for cycle in [1, 2, 3]:
                for ch in channels_bc:
                    col = f"Cycle{cycle:02d}_{ch}"
                    # No channel subdirectory - files are flat in well directory
                    path = f"{base_path}/images_corrected_cropped/barcoding/{plate}/{plate}-{well}/"
                    data[f"PathName_{col}"] = path
                    # New explicit naming: Plate_Plate1_Well_A1_Site_1_Cycle01_A.tiff
                    data[f"FileName_{col}"] = (
                        f"Plate_{plate}_Well_{well}_Site_{tile}_{col}.tiff"
                    )

            # Add Cycle01_DNA separately (special case for pipeline 9)
            # No channel subdirectory - files are flat in well directory
            data["PathName_Cycle01_DNA"] = (
                f"{base_path}/images_corrected_cropped/barcoding/{plate}/{plate}-{well}/"
            )
            # New explicit naming: Plate_Plate1_Well_A1_Site_1_Cycle01_DNA.tiff
            data["FileName_Cycle01_DNA"] = (
                f"Plate_{plate}_Well_{well}_Site_{tile}_Cycle01_DNA.tiff"
            )

            # Cell Painting channels (with Corr prefix)
            for ch in channels_cp:
                # No channel subdirectory - files are flat in well directory
                path = f"{base_path}/images_corrected_cropped/painting/{plate}/{plate}-{well}/"
                data[f"PathName_Corr{ch}"] = path
                # New explicit naming: Plate_Plate1_Well_A1_Site_1_CorrDNA.tiff
                data[f"FileName_Corr{ch}"] = (
                    f"Plate_{plate}_Well_{well}_Site_{tile}_Corr{ch}.tiff"
                )

            rows.append(data)

    return pd.DataFrame(rows)


def generate_all(samplesheet_path, base_path=None, qc_sites=None, tiles_per_well=None):
    """Generate LoadData CSVs for all pipelines with configurable parameters"""
    df = pd.read_csv(samplesheet_path)

    return {
        1: pipeline1(df, base_path),
        2: pipeline2(df, base_path),
        3: pipeline3(df, base_path, qc_sites),
        # 4 is FIJI stitching - no CSV
        5: pipeline5(df, base_path),
        6: pipeline6(df, base_path),
        7: pipeline7(df, base_path),
        # 8 is FIJI stitching - no CSV
        9: pipeline9(df, base_path, tiles_per_well),
    }

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate LoadData CSVs for PCPIP CellProfiler pipelines"
    )
    parser.add_argument("samplesheet", help="Path to samplesheet CSV")
    parser.add_argument(
        "--output-dir",
        default="data/Source1/workspace/load_data_csv/Batch1/Plate1_trimmed",
        help="Directory to save generated CSV files",
    )
    parser.add_argument(
        "--base-path",
        default=None,
        help=f"Base path for LoadData CSVs (default: {DEFAULT_BASE_PATH})",
    )
    parser.add_argument(
        "--qc-sites",
        default=None,
        help="Comma-separated list of site indices for QC (default: 0,2)",
    )
    parser.add_argument(
        "--tiles-per-well",
        type=int,
        default=None,
        help="Number of tiles per well for pipeline 9 (default: 4)",
    )

    args = parser.parse_args()

    # Parse QC sites if provided
    qc_sites = None
    if args.qc_sites:
        qc_sites = [int(s.strip()) for s in args.qc_sites.split(",")]

    # Generate CSVs with configurable parameters
    csvs = generate_all(
        args.samplesheet,
        base_path=args.base_path,
        qc_sites=qc_sites,
        tiles_per_well=args.tiles_per_well,
    )

    # Save to files
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    for num, df in csvs.items():
        output = output_dir / f"load_data_pipeline{num}_generated.csv"
        df.to_csv(output, index=False)
        print(f"Generated {output} with {len(df)} rows")
