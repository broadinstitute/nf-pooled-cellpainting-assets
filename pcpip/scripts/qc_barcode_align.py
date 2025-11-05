#!/usr/bin/env python
"""
Pipeline 6 QC: Barcode Alignment Analysis

Analyzes alignment quality between barcoding cycles by extracting pixel shifts
and correlation scores from Pipeline 6 outputs. Generates CSV reports for
downstream analysis and visualization.

Design philosophy:
- CSV-first approach: Generate greppable, queryable data files
- Two-stage architecture: (1) data extraction, (2) visualization/reporting
- Clear separation enables integration with interactive tools (e.g., Marimo)
- Summary statistics printed to stdout for quick assessment

Architecture:
    Stage 1: extract_qc_data()     → 4 CSV files (deterministic, batch-friendly)
    Stage 2: generate_qc_reports() → plots + markdown + HTML (flexible, replaceable)

Usage:

    # Full run (both stages)
    python qc_barcode_align.py \
        data/Source1/images/Batch1/images_aligned/barcoding/Plate1 \
        data/Source1/workspace/qc_reports/6_alignment/Plate1 \
        --numcycles 3

    # CSV generation only (for batch processing or custom visualization)
    python qc_barcode_align.py \
        data/Source1/images/Batch1/images_aligned/barcoding/Plate1 \
        data/Source1/workspace/qc_reports/6_alignment/Plate1 \
        --numcycles 3 \
        --csv-only

    # spatial analysis (square acquisition):
    python qc_barcode_align.py input/ output/ --numcycles 3 \
        --rows 32 --columns 32

    # spatial analysis (circular acquisition):
    python qc_barcode_align.py input/ output/ --numcycles 3 \
        --row-widths "5,11,17,19,23,25,27,29,29,31,33,33,33,35,35,35,37,37,37,37,37,35,35,35,33,33,33,31,29,29,27,25,23,19,17,11,5"

Input:
    - BarcodingApplication_Image.csv from Pipeline 6 (barcoding illumination application)
    - Located in: SOURCE/images/BATCH/images_aligned/barcoding/PLATE/{Well-Site}/

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

Output Reports:

    alignment_report.md
       - Comprehensive markdown report with embedded visualizations
       - Includes: summary statistics table, all plots, flagged sites, interpretation guidance

    alignment_report.html (if pandoc available)
       - Self-contained HTML version with embedded images

Output Plots:

    1. alignment_shifts_catplot.png
       - Horizontal catplot showing pixel shift distributions
       - Faceted by Plate (rows) and Well (columns)
       - X-axis limited to (-200, 200) pixels
       - Shows all X and Y shifts for each cycle vs Cycle 1

    2. alignment_correlations_all.png
       - Catplot of all pairwise cycle correlations
       - Red reference line at correlation threshold (default 0.9)
       - Faceted by Plate (rows) and Well (columns)

    3. alignment_correlations_cycle01.png
       - Catplot of correlations to Cycle 1 only (primary QC)
       - Red reference line at correlation threshold
       - Faceted by Plate (rows) and Well (columns)

    4. alignment_shifts_spatial.png (requires --rows/--columns or --row-widths)
       - Spatial heatmap showing location of problematic sites
       - Color-coded by shift magnitude
       - Shows WHERE in the well alignment issues occur
       - Useful for identifying edge effects or debris zones

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
import subprocess
import shutil
from pathlib import Path
import pandas as pd
import numpy as np

import matplotlib

matplotlib.use("Agg")  # Non-interactive backend for Docker/headless environments
import matplotlib.pyplot as plt
import seaborn as sns


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
                "Metadata_Site": "nunique",  # Total unique sites
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

    # Count unique sites with large shifts
    large_shifts = (
        df_shifts[df_shifts["shift_magnitude"] > shift_threshold]
        .groupby(["Metadata_Plate", "Metadata_Well"])["Metadata_Site"]
        .nunique()
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

    # Count unique sites with poor correlations
    poor_corr = (
        df_corr_cycle01[df_corr_cycle01["correlation"] < corr_threshold]
        .groupby(["Metadata_Plate", "Metadata_Well"])["Metadata_Site"]
        .nunique()
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
    Print brief summary to stdout for quick assessment.

    Args:
        summary: Summary statistics DataFrame
        flagged: Flagged sites DataFrame
        shift_threshold: Shift threshold used
        corr_threshold: Correlation threshold used
    """
    # Calculate key metrics
    total_sites = summary["total_sites"].sum()
    total_large_shifts = summary[f"sites_shift_gt{int(shift_threshold)}"].sum()
    pct_large_shifts = (
        (total_large_shifts / total_sites * 100) if total_sites > 0 else 0
    )
    col_name = f"sites_corr_lt{corr_threshold:.2f}".replace(".", "")
    total_poor_corr = summary[col_name].sum()
    pct_poor_corr = (total_poor_corr / total_sites * 100) if total_sites > 0 else 0

    # Determine overall status
    if len(flagged) == 0:
        status = "✅ PASS"
    elif pct_large_shifts < 5 and pct_poor_corr < 5:
        status = "⚠️  PASS WITH WARNINGS"
    else:
        status = "❌ REVIEW REQUIRED"

    # Print concise summary
    print(f"\n{'=' * 60}")
    print(f"Pipeline 6 QC: {status}")
    print(f"{'=' * 60}")
    print(
        f"  {total_sites} sites analyzed | "
        f"{total_large_shifts} with large shifts ({pct_large_shifts:.1f}%) | "
        f"{total_poor_corr} with poor correlation ({pct_poor_corr:.1f}%)"
    )
    print("  → See alignment_report.html for full details")
    print()


def create_position_mapping_square(rows: int, columns: int) -> pd.DataFrame:
    """
    Create position mapping for square/rectangular acquisition pattern.

    Args:
        rows: Number of rows in the grid
        columns: Number of columns in the grid

    Returns:
        DataFrame with columns: Metadata_Site, x_loc, y_loc
    """
    pos_data = []
    for site in range(rows * columns):
        row = site // columns
        col = site % columns
        pos_data.append({"Metadata_Site": site, "x_loc": col, "y_loc": row})
    return pd.DataFrame(pos_data)


def create_position_mapping_circular(row_widths: list) -> pd.DataFrame:
    """
    Create position mapping for circular acquisition pattern.

    Based on original PCPIP notebook logic where images snake back and forth
    (even rows go left→right, odd rows go right→left).

    Args:
        row_widths: List where each element is the number of images in that row

    Returns:
        DataFrame with columns: Metadata_Site, x_loc, y_loc
    """
    max_width = max(row_widths)
    pos_data = []
    site_count = 0

    for row_idx, row_width in enumerate(row_widths):
        left_pos = int((max_width - row_width) / 2)

        for col_idx in range(row_width):
            if row_idx % 2 == 0:
                # Even rows: left to right
                x_pos = int(left_pos + col_idx)
            else:
                # Odd rows: right to left (snake pattern)
                right_pos = left_pos + row_width - 1
                x_pos = int(right_pos - col_idx)

            pos_data.append(
                {"Metadata_Site": site_count, "x_loc": x_pos, "y_loc": row_idx}
            )
            site_count += 1

    return pd.DataFrame(pos_data)


def plot_shifts_catplot(
    df_shifts: pd.DataFrame, output_path: Path, shift_threshold: float
):
    """
    Create catplot of pixel shifts with limited x-axis.

    Args:
        df_shifts: Shift data from extract_shifts()
        output_path: Path to save the plot
        shift_threshold: Threshold value (for reference)
    """

    # Prepare data in long format for seaborn
    id_cols = ["Metadata_Plate", "Metadata_Well", "Metadata_Site", "cycle"]
    df_melted = pd.melt(
        df_shifts[id_cols + ["Xshift", "Yshift"]],
        id_vars=id_cols,
        var_name="direction",
        value_name="shift_pixels",
    )

    # Create variable name like "Cycle02_X" for y-axis
    df_melted["variable"] = (
        "Cycle"
        + df_melted["cycle"].astype(str).str.zfill(2)
        + "_"
        + df_melted["direction"]
    )

    # Create catplot
    g = sns.catplot(
        data=df_melted,
        x="shift_pixels",
        y="variable",
        orient="h",
        col="Metadata_Well",
        row="Metadata_Plate",
        height=4,
        aspect=1.5,
        kind="strip",
        s=3,
        alpha=0.5,
    )

    g.set(xlim=(-200, 200))
    g.set_axis_labels("Pixel Shift", "Cycle vs Cycle 1")
    g.fig.suptitle(
        f"Pixel Shifts for Alignment (threshold: {shift_threshold}px)", y=1.02
    )

    plt.tight_layout()
    g.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_correlations_catplot(
    df_corr: pd.DataFrame,
    output_path: Path,
    corr_threshold: float,
    only_cycle01: bool = False,
):
    """
    Create catplot of correlation scores.

    Args:
        df_corr: Correlation data from extract_correlations()
        output_path: Path to save the plot
        corr_threshold: Threshold value for reference line
        only_cycle01: If True, only show correlations to Cycle 1
    """

    # Filter to Cycle01 comparisons if requested
    plot_data = df_corr.copy()
    if only_cycle01:
        plot_data = plot_data[plot_data["cycle1"] == 1].copy()
        title_suffix = "(Cycle 1 vs Others)"
    else:
        title_suffix = "(All Pairwise Comparisons)"

    # Create catplot
    g = sns.catplot(
        data=plot_data,
        x="correlation",
        y="cycle_pair_label",
        orient="h",
        col="Metadata_Well",
        row="Metadata_Plate",
        height=4,
        aspect=1.5,
        kind="strip",
        s=3,
        alpha=0.5,
    )

    # Add reference line at threshold
    for ax in g.axes.flat:
        ax.axvline(
            x=corr_threshold, color="red", linestyle="--", linewidth=1, alpha=0.7
        )

    g.set(xlim=(0, 1.0))
    g.set_axis_labels("Correlation Score", "Cycle Pair")
    g.fig.suptitle(
        f"DAPI Correlations After Alignment {title_suffix}\n(threshold: {corr_threshold})",
        y=1.02,
    )

    plt.tight_layout()
    g.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def plot_shifts_spatial(
    df_shifts: pd.DataFrame,
    pos_df: pd.DataFrame,
    output_path: Path,
    shift_threshold: float,
):
    """
    Create spatial heatmap of sites with large shifts.

    Args:
        df_shifts: Shift data from extract_shifts()
        pos_df: Position mapping from create_position_mapping_*()
        output_path: Path to save the plot
        shift_threshold: Only plot sites with shifts above this threshold
    """

    # Get sites with shifts greater than threshold
    flagged_shifts = (
        df_shifts[df_shifts["shift_magnitude"] > shift_threshold]
        .groupby(["Metadata_Plate", "Metadata_Well", "Metadata_Site"])
        .agg({"shift_magnitude": "max"})
        .reset_index()
    )

    if len(flagged_shifts) == 0:
        print(f"  ℹ No sites with shifts >{shift_threshold}px, skipping spatial plot")
        return

    # Merge with position data
    plot_data = flagged_shifts.merge(pos_df, on="Metadata_Site", how="inner")

    if len(plot_data) == 0:
        print(f"  ℹ No sites with shifts >{shift_threshold}px found")
        return

    # Cap extreme values for color scale (but keep all sites in plot)
    plot_data["shift_magnitude_capped"] = plot_data["shift_magnitude"].clip(upper=200)

    # Determine number of wells for subplot layout
    n_wells = plot_data["Metadata_Well"].nunique()
    if n_wells == 1:
        fig, ax = plt.subplots(1, 1, figsize=(10, 10))
        axes = [ax]
    else:
        ncols = min(3, n_wells)
        nrows = int(np.ceil(n_wells / ncols))
        fig, axes = plt.subplots(nrows, ncols, figsize=(6 * ncols, 6 * nrows))
        axes = axes.flatten() if n_wells > 1 else [axes]

    # Plot each well
    for idx, well in enumerate(sorted(plot_data["Metadata_Well"].unique())):
        if idx >= len(axes):
            break

        well_data = plot_data[plot_data["Metadata_Well"] == well]

        ax = axes[idx]
        scatter = ax.scatter(
            well_data["x_loc"],
            well_data["y_loc"],
            c=well_data["shift_magnitude_capped"],
            cmap="viridis",
            s=150,
            marker="s",
            vmin=shift_threshold,
            vmax=200,
            alpha=0.8,
        )

        ax.set_xlabel("X Position")
        ax.set_ylabel("Y Position")
        ax.set_title(f"Well {well}")
        ax.set_aspect("equal")
        ax.invert_yaxis()  # Match image coordinates (0,0 at top-left)

        # Add colorbar
        cbar = plt.colorbar(scatter, ax=ax)
        cbar.set_label("Shift Magnitude (pixels)")

    # Hide unused subplots
    for idx in range(n_wells, len(axes)):
        axes[idx].set_visible(False)

    # Check if any values exceed 200px for title annotation
    max_shift = plot_data["shift_magnitude"].max()
    title = f"Spatial Distribution of Large Shifts (>{shift_threshold}px)"
    if max_shift > 200:
        title += (
            f"\nNote: Color scale capped at 200px (max observed: {max_shift:.0f}px)"
        )

    fig.suptitle(title, fontsize=14, y=0.995)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()


def generate_markdown_report(
    summary: pd.DataFrame,
    flagged: pd.DataFrame,
    df_shifts: pd.DataFrame,
    output_dir: Path,
    shift_threshold: float,
    corr_threshold: float,
    numcycles: int,
    has_spatial_plot: bool,
):
    """
    Generate a markdown QC report summarizing alignment analysis.

    Args:
        summary: Summary statistics DataFrame
        flagged: Flagged sites DataFrame
        df_shifts: Shift data (for row counts)
        output_dir: Directory to save the report
        shift_threshold: Shift threshold used
        corr_threshold: Correlation threshold used
        numcycles: Number of barcoding cycles
        has_spatial_plot: Whether spatial plot was generated
    """
    report_path = output_dir / "alignment_report.md"
    print(f"\nGenerating markdown report: {report_path.name}...")

    # Overall statistics
    total_sites = summary["total_sites"].sum()
    plates = summary["Metadata_Plate"].unique()
    wells = summary["Metadata_Well"].unique()
    total_large_shifts = summary[f"sites_shift_gt{int(shift_threshold)}"].sum()
    pct_large_shifts = (
        (total_large_shifts / total_sites * 100) if total_sites > 0 else 0
    )
    max_shift = summary["max_shift_magnitude"].max()
    mean_shift = summary["mean_shift_magnitude"].mean()

    col_name = f"sites_corr_lt{corr_threshold:.2f}".replace(".", "")
    total_poor_corr = summary[col_name].sum()
    pct_poor_corr = (total_poor_corr / total_sites * 100) if total_sites > 0 else 0
    min_corr = summary["min_correlation"].min()
    mean_corr = summary["mean_correlation"].mean()

    # Determine overall status
    if len(flagged) == 0:
        status = "✅ PASS"
        status_message = "All alignment metrics within acceptable thresholds"
    elif pct_large_shifts < 5 and pct_poor_corr < 5:
        status = "⚠️ PASS WITH WARNINGS"
        status_message = f"{len(flagged)} flagged sites ({pct_large_shifts:.1f}% shifts, {pct_poor_corr:.1f}% correlations)"
    else:
        status = "❌ REVIEW REQUIRED"
        status_message = (
            f"Significant alignment issues detected ({len(flagged)} flagged sites)"
        )

    # Start building markdown
    md_lines = [
        "# Pipeline 6 QC: Barcode Alignment Report\n",
        f"**Plate(s)**: {', '.join(plates)}  ",
        f"**Well(s)**: {', '.join(wells)}  ",
        f"**Barcoding Cycles**: {numcycles}  ",
        f"**Generated**: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}  \n",
        "---\n",
        "## Summary Statistics\n",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total sites analyzed | {total_sites} |",
        f"| Sites with shifts >{shift_threshold}px | {total_large_shifts} ({pct_large_shifts:.1f}%) |",
        f"| Sites with correlation <{corr_threshold} | {total_poor_corr} ({pct_poor_corr:.1f}%) |",
        f"| Maximum shift observed | {max_shift:.1f} pixels |",
        f"| Mean shift across sites | {mean_shift:.1f} pixels |",
        f"| Minimum correlation | {min_corr:.3f} |",
        f"| Mean correlation | {mean_corr:.3f} |\n",
        f"**Status**: {status}\n",
        f"*{status_message}*\n",
        "---\n",
        "## Visualizations\n",
        "### Pixel Shifts\n",
        "Distribution of X and Y pixel shifts for each cycle relative to Cycle 1.\n",
        "![Pixel Shifts](alignment_shifts_catplot.png)\n",
        "### Cycle Correlations (vs Cycle 1)\n",
        f"Correlation scores between Cycle 1 DAPI and subsequent cycles. Red line indicates threshold ({corr_threshold}).\n",
        "![Correlations to Cycle 1](alignment_correlations_cycle01.png)\n",
        "### All Pairwise Correlations\n",
        "Correlation scores between all cycle pairs.\n",
        "![All Correlations](alignment_correlations_all.png)\n",
    ]

    # Add spatial plot if generated
    if has_spatial_plot:
        md_lines.extend(
            [
                "### Spatial Distribution\n",
                f"Heatmap showing location of sites with shifts >{shift_threshold}px.\n",
                "![Spatial Heatmap](alignment_shifts_spatial.png)\n",
            ]
        )

    md_lines.append("---\n")

    # Flagged sites section
    if len(flagged) > 0:
        md_lines.extend(
            [
                "## Flagged Sites\n",
                f"Sites that exceed QC thresholds (showing top {min(10, len(flagged))}):\n",
                "| Plate | Well | Site | Cycle | Issue | Value | Threshold | Details |",
                "|-------|------|------|-------|-------|-------|-----------|---------|",
            ]
        )
        for _, row in flagged.head(10).iterrows():
            md_lines.append(
                f"| {row['Metadata_Plate']} | {row['Metadata_Well']} | "
                f"{row['Metadata_Site']} | {row['cycle']} | {row['issue_type']} | "
                f"{row['value']:.3f} | {row['threshold']} | {row['details']} |"
            )
        md_lines.append("")
        if len(flagged) > 10:
            md_lines.append(
                f"*Note: Showing 10 of {len(flagged)} flagged sites. "
                "See `alignment_flagged_sites.csv` for complete list.*\n"
            )
    else:
        md_lines.extend(
            [
                "## Flagged Sites\n",
                "✅ **No sites flagged** - all alignment metrics within thresholds.\n",
            ]
        )

    md_lines.append("---\n")

    # Interpretation section
    md_lines.extend(
        [
            "## Interpretation\n",
        ]
    )

    if mean_corr > 0.95:
        md_lines.append(
            f"✅ **Excellent**: Mean correlation {mean_corr:.3f} indicates very good alignment across cycles  "
        )
    elif mean_corr > 0.90:
        md_lines.append(
            f"✅ **Good**: Mean correlation {mean_corr:.3f} indicates acceptable alignment  "
        )
    else:
        md_lines.append(
            f"⚠️ **Concern**: Mean correlation {mean_corr:.3f} is below optimal range - review alignment quality  "
        )

    if mean_shift < 10:
        md_lines.append(
            f"✅ **Excellent**: Mean shift {mean_shift:.1f}px indicates minimal stage drift  "
        )
    elif mean_shift < 30:
        md_lines.append(
            f"✅ **Good**: Mean shift {mean_shift:.1f}px is within acceptable range  "
        )
    else:
        md_lines.append(
            f"⚠️ **Concern**: Mean shift {mean_shift:.1f}px suggests possible stage drift or sample movement  "
        )

    if pct_large_shifts > 5:
        md_lines.append(
            f"⚠️ **Concern**: {pct_large_shifts:.1f}% of sites have large shifts (>{shift_threshold}px) - investigate spatial patterns  "
        )

    if pct_poor_corr > 5:
        md_lines.append(
            f"⚠️ **Concern**: {pct_poor_corr:.1f}% of sites have poor correlations (<{corr_threshold}) - may indicate alignment failure  "
        )

    md_lines.extend(
        [
            "\n**Common causes of alignment issues:**\n",
            "- Stage drift during imaging (mechanical/thermal)",
            "- Sample movement between cycles",
            "- Poor image quality in specific cycles",
            "- Debris or unstable mounting\n",
            "---\n",
        ]
    )

    # Data files section
    shift_rows = len(df_shifts)
    corr_rows = (
        len(pd.read_csv(output_dir / "alignment_correlations.csv"))
        if (output_dir / "alignment_correlations.csv").exists()
        else 0
    )
    summary_rows = len(summary)
    flagged_rows = len(flagged)

    md_lines.extend(
        [
            "## Data Files\n",
            "CSV files for downstream analysis:\n",
            f"- [`alignment_shifts.csv`](alignment_shifts.csv) - Per-site pixel shifts ({shift_rows} rows)",
            f"- [`alignment_correlations.csv`](alignment_correlations.csv) - Per-site correlations ({corr_rows} rows)",
            f"- [`alignment_summary.csv`](alignment_summary.csv) - Well-level summary ({summary_rows} rows)",
            f"- [`alignment_flagged_sites.csv`](alignment_flagged_sites.csv) - Flagged sites only ({flagged_rows} rows)\n",
            "### Example Queries\n",
            "```bash",
            "# Find sites with shifts >100px",
            "grep -E ',[0-9]{3}\\.' alignment_shifts.csv\n",
            "# Count flagged sites by issue type",
            "awk -F',' 'NR>1 {print $5}' alignment_flagged_sites.csv | sort | uniq -c\n",
            "# Get worst correlations using duckdb",
            "duckdb -c \"SELECT * FROM read_csv_auto('alignment_correlations.csv') ",
            '           WHERE cycle1 = 1 ORDER BY correlation ASC LIMIT 10;"',
            "```\n",
        ]
    )

    # Write to file
    with open(report_path, "w") as f:
        f.write("\n".join(md_lines))

    print(f"  ✓ Markdown report written to {report_path}")


def generate_html_report(output_dir: Path):
    """
    Generate HTML report from markdown using pandoc (if available).

    Args:
        output_dir: Directory containing the markdown report
    """
    # Check if pandoc is available
    if not shutil.which("pandoc"):
        print(
            "\n  ℹ pandoc not found - skipping HTML generation"
            "\n    Install pandoc to enable HTML reports: https://pandoc.org/installing.html"
        )
        return

    md_filename = "alignment_report.md"
    html_filename = "alignment_report.html"

    print(f"\nGenerating HTML report: {html_filename}...")

    try:
        # Run pandoc from the output directory so it can find and embed images
        result = subprocess.run(
            [
                "pandoc",
                md_filename,
                "-o",
                html_filename,
                "--embed-resources",
                "--standalone",
                "--metadata",
                "title=Pipeline 6 QC: Barcode Alignment Report",
            ],
            cwd=output_dir,  # Run from output directory to find images
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            # Get file size for reporting
            html_path = output_dir / html_filename
            size_kb = html_path.stat().st_size / 1024
            print(f"  ✓ HTML report written to {html_path} ({size_kb:.1f} KB)")
        else:
            print(f"  ⚠ pandoc conversion failed: {result.stderr}")

    except subprocess.TimeoutExpired:
        print("  ⚠ pandoc conversion timed out")
    except Exception as e:
        print(f"  ⚠ Failed to generate HTML report: {e}")


def generate_plots(
    df_shifts: pd.DataFrame,
    df_corr: pd.DataFrame,
    output_dir: Path,
    shift_threshold: float,
    corr_threshold: float,
    rows: int = None,
    columns: int = None,
    row_widths: list = None,
):
    """
    Generate all QC plots.

    Args:
        df_shifts: Shift data from extract_shifts()
        df_corr: Correlation data from extract_correlations()
        output_dir: Directory to save plots
        shift_threshold: Shift threshold for flagging
        corr_threshold: Correlation threshold for flagging
        rows: Number of rows (for square acquisition)
        columns: Number of columns (for square acquisition)
        row_widths: Row width array (for circular acquisition)

    Returns:
        bool: True if spatial plot was generated, False otherwise
    """

    print("\nGenerating QC plots...")

    # 1. Shifts catplot
    shifts_plot_path = output_dir / "alignment_shifts_catplot.png"
    print(f"  Creating {shifts_plot_path.name}...")
    plot_shifts_catplot(df_shifts, shifts_plot_path, shift_threshold)

    # 2. All correlations catplot
    corr_all_path = output_dir / "alignment_correlations_all.png"
    print(f"  Creating {corr_all_path.name}...")
    plot_correlations_catplot(
        df_corr, corr_all_path, corr_threshold, only_cycle01=False
    )

    # 3. Cycle01 correlations catplot (primary QC)
    corr_cycle01_path = output_dir / "alignment_correlations_cycle01.png"
    print(f"  Creating {corr_cycle01_path.name}...")
    plot_correlations_catplot(
        df_corr, corr_cycle01_path, corr_threshold, only_cycle01=True
    )

    # 4. Spatial heatmap (if geometry provided)
    has_spatial_plot = False
    if rows is not None and columns is not None:
        print(f"  Creating spatial plot (square: {rows}x{columns})...")
        pos_df = create_position_mapping_square(rows, columns)
        spatial_plot_path = output_dir / "alignment_shifts_spatial.png"
        plot_shifts_spatial(df_shifts, pos_df, spatial_plot_path, shift_threshold)
        has_spatial_plot = True
    elif row_widths is not None:
        print(f"  Creating spatial plot (circular: {len(row_widths)} rows)...")
        pos_df = create_position_mapping_circular(row_widths)
        spatial_plot_path = output_dir / "alignment_shifts_spatial.png"
        plot_shifts_spatial(df_shifts, pos_df, spatial_plot_path, shift_threshold)
        has_spatial_plot = True
    else:
        print("  ℹ No acquisition geometry provided, skipping spatial plot")
        print("    (Use --rows/--columns or --row-widths to enable)")

    print("  ✓ Plot generation complete")
    return has_spatial_plot


def extract_qc_data(
    input_dir: Path,
    output_dir: Path,
    numcycles: int = 3,
    shift_threshold: float = 50.0,
    corr_threshold: float = 0.9,
) -> Path:
    """
    Stage 1: Extract alignment metrics and write CSV files.

    Reads Pipeline 6 output and generates 4 CSV files containing alignment
    analysis. This stage is deterministic and batch-friendly.

    Args:
        input_dir: Directory containing BarcodingApplication_Image.csv
        output_dir: Directory to write QC CSV files
        numcycles: Number of barcoding cycles
        shift_threshold: Threshold for flagging large shifts (pixels)
        corr_threshold: Threshold for flagging poor correlations

    Returns:
        Path to output directory containing CSV files
    """
    print("Stage 1: Extracting QC data from Pipeline 6 outputs")
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
    print("\nWriting QC CSV files...")

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

    print(f"\nStage 1 complete. CSV files written to: {output_dir}")
    return output_dir


def generate_qc_reports(
    csv_dir: Path,
    numcycles: int = 3,
    shift_threshold: float = 50.0,
    corr_threshold: float = 0.9,
    rows: int = None,
    columns: int = None,
    row_widths: list = None,
):
    """
    Stage 2: Generate visualizations and reports from CSV files.

    Reads the 4 CSV files produced by Stage 1 and generates plots, markdown,
    and HTML reports. This stage is flexible and can be replaced by interactive
    tools like Marimo notebooks.

    Args:
        csv_dir: Directory containing the 4 QC CSV files
        numcycles: Number of barcoding cycles
        shift_threshold: Threshold for flagging large shifts (pixels)
        corr_threshold: Threshold for flagging poor correlations
        rows: Number of rows for square acquisition (for spatial plot)
        columns: Number of columns for square acquisition (for spatial plot)
        row_widths: Row widths array for circular acquisition (for spatial plot)
    """
    print("\nStage 2: Generating visualizations and reports")
    print(f"Reading CSV files from: {csv_dir}")

    # Load CSV files
    print("\nLoading QC data from CSV files...")
    df_shifts = pd.read_csv(csv_dir / "alignment_shifts.csv")
    df_corr = pd.read_csv(csv_dir / "alignment_correlations.csv")
    summary = pd.read_csv(csv_dir / "alignment_summary.csv")
    flagged = pd.read_csv(csv_dir / "alignment_flagged_sites.csv")

    print(
        f"  Loaded: {len(df_shifts)} shifts, {len(df_corr)} correlations, "
        f"{len(summary)} wells, {len(flagged)} flagged sites"
    )

    # Generate plots
    has_spatial_plot = generate_plots(
        df_shifts,
        df_corr,
        csv_dir,
        shift_threshold,
        corr_threshold,
        rows=rows,
        columns=columns,
        row_widths=row_widths,
    )

    # Generate markdown report
    generate_markdown_report(
        summary,
        flagged,
        df_shifts,
        csv_dir,
        shift_threshold,
        corr_threshold,
        numcycles,
        has_spatial_plot,
    )

    # Generate HTML report from markdown (if pandoc available)
    generate_html_report(csv_dir)

    print(f"\nStage 2 complete. Reports written to: {csv_dir}")


def main(
    input_dir: Path,
    output_dir: Path,
    numcycles: int = 3,
    shift_threshold: float = 50.0,
    corr_threshold: float = 0.9,
    rows: int = None,
    columns: int = None,
    row_widths: list = None,
    csv_only: bool = False,
):
    """
    Main execution function for Pipeline 6 QC.

    Runs a two-stage process:
    1. Extract alignment metrics and write CSV files
    2. Generate visualizations and reports (skipped if csv_only=True)

    Args:
        input_dir: Directory containing BarcodingApplication_Image.csv
        output_dir: Directory to write QC reports
        numcycles: Number of barcoding cycles
        shift_threshold: Threshold for flagging large shifts (pixels)
        corr_threshold: Threshold for flagging poor correlations
        rows: Number of rows for square acquisition (for spatial plot)
        columns: Number of columns for square acquisition (for spatial plot)
        row_widths: Row widths array for circular acquisition (for spatial plot)
        csv_only: If True, only run Stage 1 (CSV generation)
    """
    print("Pipeline 6 QC: Barcode Alignment Analysis")

    # Stage 1: Extract QC data and write CSVs
    csv_dir = extract_qc_data(
        input_dir, output_dir, numcycles, shift_threshold, corr_threshold
    )

    # Stage 2: Generate reports (skip if csv_only)
    if csv_only:
        print("\n--csv-only flag set. Skipping visualization and report generation.")
        print("To generate reports later, run with the CSV directory as input.")
    else:
        generate_qc_reports(
            csv_dir,
            numcycles,
            shift_threshold,
            corr_threshold,
            rows=rows,
            columns=columns,
            row_widths=row_widths,
        )

    print(f"\nQC analysis complete. Output: {output_dir}")


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

    # Acquisition geometry for spatial plot (optional)
    geometry_group = parser.add_argument_group(
        "acquisition geometry",
        "Optional parameters for spatial heatmap visualization. "
        "Provide EITHER (--rows AND --columns) for square acquisition "
        "OR --row-widths for circular acquisition.",
    )

    geometry_group.add_argument(
        "--rows",
        type=int,
        help="Number of rows in square acquisition grid",
    )

    geometry_group.add_argument(
        "--columns",
        type=int,
        help="Number of columns in square acquisition grid",
    )

    geometry_group.add_argument(
        "--row-widths",
        type=str,
        help="Comma-separated row widths for circular acquisition (e.g., '5,11,17,19,...')",
    )

    # Processing mode
    parser.add_argument(
        "--csv-only",
        action="store_true",
        help="Only generate CSV files (skip plots and reports). Useful for batch processing.",
    )

    args = parser.parse_args()

    # Validate geometry arguments
    if (args.rows is not None) != (args.columns is not None):
        parser.error("--rows and --columns must be used together")

    if args.row_widths and (args.rows or args.columns):
        parser.error(
            "Cannot use --row-widths with --rows/--columns (choose one acquisition pattern)"
        )

    # Parse row_widths if provided
    row_widths_list = None
    if args.row_widths:
        try:
            row_widths_list = [int(x.strip()) for x in args.row_widths.split(",")]
        except ValueError:
            parser.error("--row-widths must be comma-separated integers")

    try:
        main(
            args.input_dir,
            args.output_dir,
            numcycles=args.numcycles,
            shift_threshold=args.shift_threshold,
            corr_threshold=args.corr_threshold,
            rows=args.rows,
            columns=args.columns,
            row_widths=row_widths_list,
            csv_only=args.csv_only,
        )
    except Exception as e:
        print(f"\nERROR: {e}", file=sys.stderr)
        sys.exit(1)
