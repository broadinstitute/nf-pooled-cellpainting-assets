#!/usr/bin/env python3
"""Transform load_data_pipeline7.csv to accommodate plate-level nesting from pipeline 6.

This script updates paths to reflect the new folder structure from pipeline 6:
  From: .../images_aligned/barcoding/Plate1-A1-0
  To:   .../images_aligned/barcoding/Plate1/Plate1-A1-0
"""

# /// script
# dependencies = ["pandas"]
# ///

import pandas as pd
import sys
import re


def main():
    if len(sys.argv) != 3:
        print("Usage: python transform_pipeline7_csv.py input.csv output.csv")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    print(f"Transforming {input_file} -> {output_file}")

    # Read CSV
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} rows")

    # Update all PathName columns that contain barcoding paths
    for col in df.columns:
        if col.startswith("PathName_"):
            # Add plate nesting for barcoding paths
            # From: .../images_aligned/barcoding/Plate1-A1-0
            # To:   .../images_aligned/barcoding/Plate1/Plate1-A1-0
            df[col] = df[col].apply(
                lambda path: re.sub(
                    r"/images_aligned/barcoding/(Plate\d+)-",
                    r"/images_aligned/barcoding/\1/\1-",
                    path,
                )
            )

    # Save revised CSV
    df.to_csv(output_file, index=False)
    print(f"Saved revised CSV with {len(df)} rows")

    # Show sample of transformed data
    print("\nSample of revised data:")
    # Find a PathName column to show as example
    pathcols = [col for col in df.columns if col.startswith("PathName_")]
    if pathcols and len(df) > 0:
        for i in range(min(2, len(df))):
            row = df.iloc[i]
            if "Metadata_Well" in row and "Metadata_Site" in row:
                print(f"  Well {row['Metadata_Well']}, Site {row['Metadata_Site']}:")
                print(f"    {row[pathcols[0]]}")


if __name__ == "__main__":
    main()
