#!/usr/bin/env python
"""
Pipeline 6 QC: Barcode Alignment Analysis

Analyzes alignment quality between barcoding cycles by extracting pixel shifts
and correlation scores from Pipeline 6 outputs. Generates CSV reports for
downstream analysis and visualization.

Design philosophy:
- CSV-first approach: Generate greppable, queryable data files
- No plotting dependencies (plots can be added in iteration 2)
- Clear separation of data extraction and visualization
- Summary statistics printed to stdout for quick assessment

Usage:
    # Direct execution with pixi:
    pixi exec -c conda-forge --spec python=3.13 --spec pandas=2.2.3 --spec numpy=2.3.3 -- \
        python qc_barcode_align.py \
        data/Source1/images/Batch1/images_aligned/barcoding/Plate1 \
        data/Source1/workspace/qc_reports/6_alignment/Plate1 \
        --numcycles 3 \
        --shift-threshold 50 \
        --corr-threshold 0.9

    # Via Docker (recommended):
    PIPELINE_STEP=6_qc_align docker-compose run --rm qc

Input:
    - BarcodingApplication_Image.csv from Pipeline 6 (barcoding illumination application)
    - Located in: data/Source1/images/Batch1/images_aligned/barcoding/Plate1/{Well-Site}/

Output CSVs (written to qc_reports/6_alignment/{Plate}/):

    1. alignment_shifts.csv
       - Per-site pixel shifts for each cycle
       - Columns: Metadata_Plate, Metadata_Well, Metadata_Site, cycle,
                 Xshift, Yshift, shift_magnitude
       - Use for: Identifying sites with large alignment shifts
       - Rows: (N sites) × (numcycles - 1) [Cycle 1 is reference]

    2. alignment_correlations.csv
       - Per-site correlation scores between all cycle pairs
       - Columns: Metadata_Plate, Metadata_Well, Metadata_Site, cycle_pair_label,
                 cycle1, cycle2, correlation
       - Use for: Finding poorly-aligned cycle pairs
       - Rows: (N sites) × (numcycles × (numcycles-1) / 2) pairwise comparisons

    3. alignment_summary.csv
       - Summary statistics per plate/well
       - Columns: Metadata_Plate, Metadata_Well, total_sites, max_shift_magnitude,
                 mean_shift_magnitude, std_shift_magnitude, sites_shift_gt{threshold},
                 min_correlation, mean_correlation, std_correlation, sites_corr_lt{threshold}
       - Use for: Quick overview and pass/fail assessment at well level
       - Rows: One per unique plate-well combination

    4. alignment_flagged_sites.csv
       - Only sites that fail QC thresholds (empty if all pass)
       - Columns: Metadata_Plate, Metadata_Well, Metadata_Site, cycle,
                 issue_type, value, threshold, details
       - issue_type: "large_shift" or "poor_correlation"
       - Use for: Immediate attention to problematic sites
       - Rows: Variable (one per flagged issue)

Example Queries:

    # Find all sites with shifts >100 pixels using grep
    grep -E ",[0-9]{3}\\." alignment_shifts.csv

    # Count flagged sites by issue type using awk
    awk -F',' 'NR>1 {print $5}' alignment_flagged_sites.csv | sort | uniq -c

    # Query with duckdb for complex analysis
    duckdb -c "SELECT Metadata_Well, COUNT(*) as flagged_count
                FROM read_csv_auto('alignment_flagged_sites.csv')
                GROUP BY Metadata_Well
                ORDER BY flagged_count DESC;"

    # Get worst correlation scores across all sites
    duckdb -c "SELECT * FROM read_csv_auto('alignment_correlations.csv')
                WHERE cycle1 = 1
                ORDER BY correlation ASC
                LIMIT 10;"

    # Calculate mean shift magnitude by well
    duckdb -c "SELECT Metadata_Well, AVG(shift_magnitude) as mean_shift
                FROM read_csv_auto('alignment_shifts.csv')
                GROUP BY Metadata_Well;"

Interpretation:

    Good alignment:
        - Pixel shifts < 50 pixels (configurable via --shift-threshold)
        - Correlations > 0.9 (configurable via --corr-threshold)
        - Few or no flagged sites

    Problematic alignment:
        - Large pixel shifts (>100 pixels) suggest:
          * Stage drift during imaging
          * Sample movement between cycles
          * Alignment algorithm issues
        - Low correlations (<0.8) suggest:
          * Poor image quality
          * Extreme misalignment
          * Different tissue regions captured

    Typical causes:
        - Mechanical issues: Stage drift, temperature changes
        - Sample issues: Unstable mounting, tissue deformation
        - Imaging issues: Focus drift, illumination changes

Parameters:
    --numcycles: Number of barcoding cycles (default: 3)
    --shift-threshold: Max acceptable pixel shift in any direction (default: 50.0)
    --corr-threshold: Min acceptable correlation between cycles (default: 0.9)
"""

import argparse
import sys
from pathlib import Path
import pandas as pd
import numpy as np


def find_image_csv(input_dir: Path) -> Path:
    """
    Find BarcodingApplication_Image.csv in the input directory structure.

    Handles both:
    - Direct path: input_dir/BarcodingApplication_Image.csv
    - Nested structure: input_dir/*/BarcodingApplication_Image.csv
    """
    # Try direct path first
    direct_path = input_dir / "BarcodingApplication_Image.csv"
    if direct_path.exists():
        return direct_path

    # Search in subdirectories (for well-based structure like Plate1-A1/)
    csv_files = list(input_dir.rglob("BarcodingApplication_Image.csv"))

    if not csv_files:
        raise FileNotFoundError(
            f"Could not find BarcodingApplication_Image.csv in {input_dir} or subdirectories"
        )

    if len(csv_files) == 1:
        return csv_files[0]

    # Multiple CSVs found - need to merge them
    print(f"Found {len(csv_files)} BarcodingApplication_Image.csv files - merging them")
    return csv_files  # Return list for merging


def load_alignment_data(input_dir: Path, numcycles: int) -> pd.DataFrame:
    """
    Load Pipeline 6 output CSV(s) and extract alignment-related columns.

    Args:
        input_dir: Directory containing BarcodingApplication_Image.csv
        numcycles: Number of barcoding cycles

    Returns:
        DataFrame with metadata and alignment columns
    """
    csv_path = find_image_csv(input_dir)

    # Build list of columns we need
    id_cols = ["Metadata_Plate", "Metadata_Well", "Metadata_Site"]

    # Shift columns: Cycle 2+ have X/Y shifts relative to Cycle 1
    # Note: Pipeline uses "DNA" not "DAPI" for the channel name
    shift_cols = []
    for cycle in range(2, numcycles + 1):
        shift_cols.append(f"Align_Xshift_Cycle{cycle:02d}_DNA")
        shift_cols.append(f"Align_Yshift_Cycle{cycle:02d}_DNA")

    # Correlation columns: All pairwise cycle comparisons
    # Note: Pipeline uses "DNA" not "DAPI" for the channel name
    corr_cols = []
    for cycle1 in range(1, numcycles + 1):
        for cycle2 in range(cycle1 + 1, numcycles + 1):
            corr_cols.append(
                f"Correlation_Correlation_Cycle{cycle1:02d}_DNA_Cycle{cycle2:02d}_DNA"
            )

    column_list = id_cols + shift_cols + corr_cols

    # Load CSV(s)
    if isinstance(csv_path, list):
        # Multiple CSVs - merge them
        dfs = []
        for path in csv_path:
            df = pd.read_csv(path, usecols=column_list)
            dfs.append(df)
        df = pd.concat(dfs, ignore_index=True)
        print(f"Merged {len(dfs)} CSV files into {len(df)} rows")
    else:
        # Single CSV
        df = pd.read_csv(csv_path, usecols=column_list)
        print(f"Loaded {len(df)} rows from {csv_path.name}")

    return df


def extract_shifts(df: pd.DataFrame, numcycles: int) -> pd.DataFrame:
    """
    Extract and reshape pixel shift data into long format.

    Args:
        df: DataFrame with shift columns
        numcycles: Number of barcoding cycles

    Returns:
        Long-format DataFrame with one row per site-cycle shift
    """
    id_cols = ["Metadata_Plate", "Metadata_Well", "Metadata_Site"]

    # Extract X and Y shift columns
    # Note: Pipeline uses "DNA" not "DAPI" for the channel name
    shift_cols = []
    for cycle in range(2, numcycles + 1):
        shift_cols.append(f"Align_Xshift_Cycle{cycle:02d}_DNA")
        shift_cols.append(f"Align_Yshift_Cycle{cycle:02d}_DNA")

    # Melt to long format
    df_shifts = df[id_cols + shift_cols].copy()
    df_melted = pd.melt(
        df_shifts,
        id_vars=id_cols,
        value_vars=shift_cols,
        var_name="shift_column",
        value_name="shift_pixels",
    )

    # Parse cycle number and direction from column name
    # Format: "Align_Xshift_Cycle02_DAPI" -> cycle=2, direction=X
    df_melted["cycle"] = (
        df_melted["shift_column"].str.extract(r"Cycle(\d+)")[0].astype(int)
    )
    df_melted["direction"] = df_melted["shift_column"].str.extract(r"_(X|Y)shift")[0]

    # Pivot to get X and Y as separate columns
    df_pivot = df_melted.pivot_table(
        index=id_cols + ["cycle"], columns="direction", values="shift_pixels"
    ).reset_index()

    # Rename columns
    df_pivot.columns.name = None
    df_pivot = df_pivot.rename(columns={"X": "Xshift", "Y": "Yshift"})

    # Calculate magnitude of shift
    df_pivot["shift_magnitude"] = np.sqrt(
        df_pivot["Xshift"] ** 2 + df_pivot["Yshift"] ** 2
    )

    return df_pivot


def extract_correlations(df: pd.DataFrame, numcycles: int) -> pd.DataFrame:
    """
    Extract and reshape correlation data into long format.

    Args:
        df: DataFrame with correlation columns
        numcycles: Number of barcoding cycles

    Returns:
        Long-format DataFrame with one row per site-cycle-pair correlation
    """
    id_cols = ["Metadata_Plate", "Metadata_Well", "Metadata_Site"]

    # Extract correlation columns
    # Note: Pipeline uses "DNA" not "DAPI" for the channel name
    corr_cols = []
    for cycle1 in range(1, numcycles + 1):
        for cycle2 in range(cycle1 + 1, numcycles + 1):
            corr_cols.append(
                f"Correlation_Correlation_Cycle{cycle1:02d}_DNA_Cycle{cycle2:02d}_DNA"
            )

    # Melt to long format
    df_corr = df[id_cols + corr_cols].copy()
    df_melted = pd.melt(
        df_corr,
        id_vars=id_cols,
        value_vars=corr_cols,
        var_name="cycle_pair",
        value_name="correlation",
    )

    # Parse cycle numbers from column name
    # Format: "Correlation_Correlation_Cycle01_DNA_Cycle02_DNA"
    pattern = r"Cycle(\d+)_DNA_Cycle(\d+)_DNA"
    df_melted[["cycle1", "cycle2"]] = (
        df_melted["cycle_pair"].str.extract(pattern).astype(int)
    )

    # Create readable cycle pair label
    df_melted["cycle_pair_label"] = (
        "Cycle"
        + df_melted["cycle1"].astype(str).str.zfill(2)
        + "_vs_"
        + "Cycle"
        + df_melted["cycle2"].astype(str).str.zfill(2)
    )

    # Keep only useful columns
    df_final = df_melted[
        id_cols + ["cycle_pair_label", "cycle1", "cycle2", "correlation"]
    ]

    return df_final


def generate_summary(
    df_shifts: pd.DataFrame,
    df_corr: pd.DataFrame,
    shift_threshold: float,
    corr_threshold: float,
) -> pd.DataFrame:
    """
    Generate summary statistics per well.

    Args:
        df_shifts: Shift data in long format
        df_corr: Correlation data in long format
        shift_threshold: Threshold for flagging large shifts (pixels)
        corr_threshold: Threshold for flagging poor correlations

    Returns:
        Summary DataFrame with one row per plate-well combination
    """
    # Aggregate shifts by well
    shift_summary = (
        df_shifts.groupby(["Metadata_Plate", "Metadata_Well"])
        .agg(
            {
                "Metadata_Site": "count",  # Total sites
                "shift_magnitude": ["max", "mean", "std"],
            }
        )
        .reset_index()
    )

    # Flatten column names
    shift_summary.columns = [
        "Metadata_Plate",
        "Metadata_Well",
        "total_sites",
        "max_shift_magnitude",
        "mean_shift_magnitude",
        "std_shift_magnitude",
    ]

    # Count sites with large shifts
    large_shifts = (
        df_shifts[df_shifts["shift_magnitude"] > shift_threshold]
        .groupby(["Metadata_Plate", "Metadata_Well"])
        .size()
        .reset_index(name=f"sites_shift_gt{int(shift_threshold)}")
    )

    shift_summary = shift_summary.merge(
        large_shifts, on=["Metadata_Plate", "Metadata_Well"], how="left"
    )
    shift_summary[f"sites_shift_gt{int(shift_threshold)}"] = (
        shift_summary[f"sites_shift_gt{int(shift_threshold)}"].fillna(0).astype(int)
    )

    # Aggregate correlations by well (only Cycle01 comparisons)
    df_corr_cycle01 = df_corr[df_corr["cycle1"] == 1].copy()

    corr_summary = (
        df_corr_cycle01.groupby(["Metadata_Plate", "Metadata_Well"])
        .agg({"correlation": ["min", "mean", "std"]})
        .reset_index()
    )

    corr_summary.columns = [
        "Metadata_Plate",
        "Metadata_Well",
        "min_correlation",
        "mean_correlation",
        "std_correlation",
    ]

    # Count sites with poor correlations
    poor_corr = (
        df_corr_cycle01[df_corr_cycle01["correlation"] < corr_threshold]
        .groupby(["Metadata_Plate", "Metadata_Well"])
        .size()
        .reset_index(name=f"sites_corr_lt{corr_threshold:.2f}".replace(".", ""))
    )

    corr_summary = corr_summary.merge(
        poor_corr, on=["Metadata_Plate", "Metadata_Well"], how="left"
    )
    corr_summary[f"sites_corr_lt{corr_threshold:.2f}".replace(".", "")] = (
        corr_summary[f"sites_corr_lt{corr_threshold:.2f}".replace(".", "")]
        .fillna(0)
        .astype(int)
    )

    # Merge shift and correlation summaries
    summary = shift_summary.merge(
        corr_summary, on=["Metadata_Plate", "Metadata_Well"], how="outer"
    )

    return summary


def flag_problematic_sites(
    df_shifts: pd.DataFrame,
    df_corr: pd.DataFrame,
    shift_threshold: float,
    corr_threshold: float,
) -> pd.DataFrame:
    """
    Identify sites that fail QC thresholds.

    Args:
        df_shifts: Shift data in long format
        df_corr: Correlation data in long format
        shift_threshold: Threshold for flagging large shifts (pixels)
        corr_threshold: Threshold for flagging poor correlations

    Returns:
        DataFrame with flagged sites and their issues
    """
    flagged_list = []

    # Flag sites with large shifts
    large_shifts = df_shifts[df_shifts["shift_magnitude"] > shift_threshold].copy()
    for _, row in large_shifts.iterrows():
        flagged_list.append(
            {
                "Metadata_Plate": row["Metadata_Plate"],
                "Metadata_Well": row["Metadata_Well"],
                "Metadata_Site": row["Metadata_Site"],
                "cycle": row["cycle"],
                "issue_type": "large_shift",
                "value": row["shift_magnitude"],
                "threshold": shift_threshold,
                "details": f"Xshift={row['Xshift']:.1f}, Yshift={row['Yshift']:.1f}",
            }
        )

    # Flag sites with poor correlations (only Cycle01 comparisons)
    df_corr_cycle01 = df_corr[df_corr["cycle1"] == 1].copy()
    poor_corr = df_corr_cycle01[df_corr_cycle01["correlation"] < corr_threshold].copy()
    for _, row in poor_corr.iterrows():
        flagged_list.append(
            {
                "Metadata_Plate": row["Metadata_Plate"],
                "Metadata_Well": row["Metadata_Well"],
                "Metadata_Site": row["Metadata_Site"],
                "cycle": row["cycle2"],  # The cycle being compared to Cycle01
                "issue_type": "poor_correlation",
                "value": row["correlation"],
                "threshold": corr_threshold,
                "details": f"{row['cycle_pair_label']}",
            }
        )

    if not flagged_list:
        # Return empty DataFrame with correct schema
        return pd.DataFrame(
            columns=[
                "Metadata_Plate",
                "Metadata_Well",
                "Metadata_Site",
                "cycle",
                "issue_type",
                "value",
                "threshold",
                "details",
            ]
        )

    df_flagged = pd.DataFrame(flagged_list)

    # Sort by severity
    df_flagged["severity"] = df_flagged.apply(
        lambda x: abs(x["value"] - x["threshold"])
        if x["issue_type"] == "poor_correlation"
        else x["value"] - x["threshold"],
        axis=1,
    )
    df_flagged = df_flagged.sort_values("severity", ascending=False)
    df_flagged = df_flagged.drop(columns=["severity"])

    return df_flagged


def print_summary_stats(
    summary: pd.DataFrame,
    flagged: pd.DataFrame,
    shift_threshold: float,
    corr_threshold: float,
):
    """
    Print summary statistics to stdout for quick assessment.

    Args:
        summary: Summary statistics DataFrame
        flagged: Flagged sites DataFrame
        shift_threshold: Shift threshold used
        corr_threshold: Correlation threshold used
    """
    print("\n" + "=" * 60)
    print("Pipeline 6 QC: Barcode Alignment Analysis")
    print("=" * 60)

    # Overall statistics
    total_sites = summary["total_sites"].sum()
    plates = summary["Metadata_Plate"].unique()
    wells = summary["Metadata_Well"].unique()

    print("\nData Summary:")
    print(f"  Plates: {', '.join(plates)}")
    print(f"  Wells: {', '.join(wells)}")
    print(f"  Total sites analyzed: {total_sites}")

    # Shift analysis
    print(f"\nShift Analysis (threshold: {shift_threshold} pixels):")
    total_large_shifts = summary[f"sites_shift_gt{int(shift_threshold)}"].sum()
    pct_large_shifts = (
        (total_large_shifts / total_sites * 100) if total_sites > 0 else 0
    )
    max_shift = summary["max_shift_magnitude"].max()
    mean_shift = summary["mean_shift_magnitude"].mean()

    print(
        f"  Sites with shifts >{shift_threshold} pixels: {total_large_shifts} ({pct_large_shifts:.1f}%)"
    )
    print(f"  Maximum shift observed: {max_shift:.1f} pixels")
    print(f"  Mean shift across all sites: {mean_shift:.1f} pixels")

    # Correlation analysis
    print(f"\nCorrelation Analysis (threshold: {corr_threshold}):")
    col_name = f"sites_corr_lt{corr_threshold:.2f}".replace(".", "")
    total_poor_corr = summary[col_name].sum()
    pct_poor_corr = (total_poor_corr / total_sites * 100) if total_sites > 0 else 0
    min_corr = summary["min_correlation"].min()
    mean_corr = summary["mean_correlation"].mean()

    print(
        f"  Sites with correlation <{corr_threshold}: {total_poor_corr} ({pct_poor_corr:.1f}%)"
    )
    print(f"  Minimum correlation: {min_corr:.3f}")
    print(f"  Mean correlation across all sites: {mean_corr:.3f}")

    # Flagged sites breakdown
    if len(flagged) > 0:
        print("\nFlagged Sites Breakdown:")
        for issue_type in flagged["issue_type"].unique():
            count = len(flagged[flagged["issue_type"] == issue_type])
            print(f"  {issue_type}: {count}")

        # Show worst offenders
        print("\nWorst 5 Offenders:")
        for _, row in flagged.head(5).iterrows():
            print(
                f"  - {row['Metadata_Plate']}-{row['Metadata_Well']}-Site{row['Metadata_Site']}: "
                f"{row['issue_type']} = {row['value']:.2f} (threshold: {row['threshold']}) - {row['details']}"
            )
    else:
        print("\nNo sites flagged! All alignment metrics within thresholds.")

    print()


def main(
    input_dir: Path,
    output_dir: Path,
    numcycles: int = 3,
    shift_threshold: float = 50.0,
    corr_threshold: float = 0.9,
):
    """
    Main execution function for Pipeline 6 QC.

    Args:
        input_dir: Directory containing BarcodingApplication_Image.csv
        output_dir: Directory to write QC reports
        numcycles: Number of barcoding cycles
        shift_threshold: Threshold for flagging large shifts (pixels)
        corr_threshold: Threshold for flagging poor correlations
    """
    print("Pipeline 6 QC: Barcode Alignment Analysis")
    print(f"Input: {input_dir}")
    print(f"Output: {output_dir}")
    print(
        f"Parameters: numcycles={numcycles}, shift_threshold={shift_threshold}, corr_threshold={corr_threshold}"
    )

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load data
    print("\nLoading alignment data...")
    df = load_alignment_data(input_dir, numcycles)

    # Extract shifts
    print("Extracting pixel shifts...")
    df_shifts = extract_shifts(df, numcycles)

    # Extract correlations
    print("Extracting correlations...")
    df_corr = extract_correlations(df, numcycles)

    # Generate summary
    print("Generating summary statistics...")
    summary = generate_summary(df_shifts, df_corr, shift_threshold, corr_threshold)

    # Flag problematic sites
    print("Flagging problematic sites...")
    flagged = flag_problematic_sites(
        df_shifts, df_corr, shift_threshold, corr_threshold
    )

    # Write CSV outputs
    print("\nWriting QC reports...")

    shifts_path = output_dir / "alignment_shifts.csv"
    df_shifts.to_csv(shifts_path, index=False)
    print(f"  ✓ {shifts_path.name} ({len(df_shifts)} rows)")

    corr_path = output_dir / "alignment_correlations.csv"
    df_corr.to_csv(corr_path, index=False)
    print(f"  ✓ {corr_path.name} ({len(df_corr)} rows)")

    summary_path = output_dir / "alignment_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"  ✓ {summary_path.name} ({len(summary)} rows)")

    flagged_path = output_dir / "alignment_flagged_sites.csv"
    flagged.to_csv(flagged_path, index=False)
    print(f"  ✓ {flagged_path.name} ({len(flagged)} rows)")

    # Print summary to stdout
    print_summary_stats(summary, flagged, shift_threshold, corr_threshold)

    print(f"\nQC reports written to: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline 6 QC: Barcode Alignment Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "input_dir",
        type=Path,
        help="Directory containing BarcodingApplication_Image.csv (from Pipeline 6)",
    )

    parser.add_argument("output_dir", type=Path, help="Directory to write QC reports")

    parser.add_argument(
        "--numcycles",
        type=int,
        default=3,
        help="Number of barcoding cycles (default: 3)",
    )

    parser.add_argument(
        "--shift-threshold",
        type=float,
        default=50.0,
        help="Pixel shift threshold for flagging (default: 50.0)",
    )

    parser.add_argument(
        "--corr-threshold",
        type=float,
        default=0.9,
        help="Correlation threshold for flagging (default: 0.9)",
    )

    args = parser.parse_args()

    try:
        main(
            args.input_dir,
            args.output_dir,
            numcycles=args.numcycles,
            shift_threshold=args.shift_threshold,
            corr_threshold=args.corr_threshold,
        )
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
