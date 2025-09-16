#!/usr/bin/env python3
"""Transform load_data_pipeline3.csv for segmentation QC with updated folder structure.

This script:
1. Duplicates rows to create sites 0 and 2 (skip pattern for QC)
2. Updates paths to include plate-level nesting and site subdirectories

Path transformation:
  From: .../images_corrected/painting/Plate1-A1
  To:   .../images_corrected/painting/Plate1/Plate1-A1-0 (for site 0)
        .../images_corrected/painting/Plate1/Plate1-A1-2 (for site 2)
"""

# /// script
# dependencies = ["pandas"]
# ///

import pandas as pd
import sys


def main():
    if len(sys.argv) != 3:
        print("Usage: python transform_pipeline3_csv.py input.csv output.csv")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    print(f"Transforming {input_file} -> {output_file}")

    # Read CSV
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} rows")

    # First, fix paths in original dataframe to include plate nesting and site
    for col in df.columns:
        if col.startswith("PathName_"):
            # Add plate nesting and site suffix
            # From: .../painting/Plate1-A1
            # To:   .../painting/Plate1/Plate1-A1-{site}
            df[col] = df.apply(
                lambda row: row[col].replace(
                    f"/painting/{row['Metadata_Plate']}-{row['Metadata_Well']}",
                    f"/painting/{row['Metadata_Plate']}/{row['Metadata_Plate']}-{row['Metadata_Well']}-{int(row['Metadata_Site'])}",
                ),
                axis=1,
            )

    # Create a copy for site 2
    df_new_site = df.copy()

    # Update Metadata_Site from 0 to 2
    if "Metadata_Site" in df_new_site.columns:
        df_new_site["Metadata_Site"] = 2

    # Update paths for site 2
    for col in df_new_site.columns:
        if col.startswith("PathName_"):
            # Update site suffix in path from -0 to -2
            df_new_site[col] = df_new_site[col].str.replace("-0", "-2", regex=False)

    # Update all FileName columns: replace Site_0 with Site_2
    for col in df_new_site.columns:
        if col.startswith("FileName_"):
            df_new_site[col] = df_new_site[col].str.replace(
                r"Site_0", "Site_2", regex=False
            )

    # Combine original and new site data
    df_revised = pd.concat([df, df_new_site], ignore_index=True)

    # Sort by Well and Site for better organization
    if "Metadata_Well" in df_revised.columns and "Metadata_Site" in df_revised.columns:
        df_revised = df_revised.sort_values(
            ["Metadata_Well", "Metadata_Site"], ignore_index=True
        )

    # Save revised CSV
    df_revised.to_csv(output_file, index=False)
    print(f"Saved revised CSV with {len(df_revised)} rows (original: {len(df)} rows)")

    # Show summary
    if "Metadata_Site" in df_revised.columns:
        sites = df_revised["Metadata_Site"].unique()
        print(f"Sites in output: {sorted(sites)}")

    # Show sample of transformed data
    print("\nSample of revised data:")
    if "Metadata_Well" in df_revised.columns and "Metadata_Site" in df_revised.columns:
        for well in df_revised["Metadata_Well"].unique()[:2]:  # Show first 2 wells
            well_data = df_revised[df_revised["Metadata_Well"] == well]
            print(f"  Well {well}: Sites {sorted(well_data['Metadata_Site'].unique())}")
            for _, row in well_data.head(2).iterrows():
                if "PathName_DNA" in row:
                    print(f"    Site {row['Metadata_Site']}: {row['PathName_DNA']}")
                if "FileName_DNA" in row:
                    print(f"      File: {row['FileName_DNA']}")


if __name__ == "__main__":
    main()
