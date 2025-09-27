#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "pandas",
# ]
# ///
"""
Filter LoadData CSV files in place to only include specified wells.

Usage:
  uv run scripts/load_data_filter.py --wells A1
  uv run scripts/load_data_filter.py --wells A1,A2,B1
"""

import pandas as pd
from pathlib import Path
import argparse


def filter_csvs(csv_dir, wells_to_keep):
    """Filter all load_data_pipeline*_revised.csv files to only include specified wells."""

    # Find all revised CSV files
    csv_files = sorted(Path(csv_dir).glob("load_data_pipeline*_revised.csv"))

    if not csv_files:
        print(f"No revised CSV files found in {csv_dir}")
        return

    for csv_file in csv_files:
        # Read CSV
        df = pd.read_csv(csv_file)
        original_rows = len(df)

        # Filter by wells if Metadata_Well column exists
        if "Metadata_Well" in df.columns:
            df = df[df["Metadata_Well"].isin(wells_to_keep)]

        # Overwrite the file
        df.to_csv(csv_file, index=False)

        filtered_rows = len(df)
        print(f"Filtered {csv_file.name}: {original_rows} → {filtered_rows} rows")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Filter LoadData CSVs to specified wells"
    )
    parser.add_argument(
        "--wells",
        required=True,
        help="Comma-separated list of wells to keep (e.g., 'A1' or 'A1,A2,B1')",
    )
    parser.add_argument(
        "--csv-dir",
        default="data/Source1/workspace/load_data_csv/Batch1/Plate1_trimmed",
        help="Directory containing the CSV files",
    )

    args = parser.parse_args()

    # Parse wells
    wells = [w.strip() for w in args.wells.split(",")]
    print(f"Filtering to wells: {wells}")

    # Filter CSVs
    filter_csvs(args.csv_dir, wells)
    print("Done!")
