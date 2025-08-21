#!/usr/bin/env python3
"""Transform load_data_pipeline9.csv to use cropped tile outputs from Pipeline 4 and 8.

WARNING: Highly customized for the FIX-S1 demo dataset.
- This script exploits a one-off coincidence where the number of cropped tiles
  equals the number of original acquisition sites. In general experiments this
  is NOT true and these assumptions will not hold.
- It also relies on specific filename and path patterns for regex-based
  rewrites (e.g., Plate_*_Well_*_Site_*). If your data do not match these
  patterns, the transforms will be incorrect.

Use with care and adapt the transforms for your dataset before production use.
"""

# /// script
# dependencies = ["pandas"]
# ///

import pandas as pd
import sys


def main():
    if len(sys.argv) != 3:
        print("Usage: python transform_pipeline9_csv.py input.csv output.csv")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2]

    print(f"Transforming {input_file} -> {output_file}")

    # Read CSV
    df = pd.read_csv(input_file)
    print(f"Loaded {len(df)} rows")

    # 1. Transform all paths: images_corrected -> images_corrected_cropped
    for col in df.columns:
        if col.startswith("PathName_"):
            df[col] = df[col].str.replace(
                "images_corrected/", "images_corrected_cropped/"
            )

    # 2. Transform barcoding paths: remove site suffix and add channel subdirectories
    barcoding_cols = [col for col in df.columns if col.startswith("PathName_Cycle")]
    for col in barcoding_cols:
        # Remove site suffix from paths (e.g., Plate1-A1-0 -> Plate1-A1)
        df[col] = df[col].str.replace(r"/(Plate\d+-[A-Z]\d+)-\d+$", r"/\1", regex=True)
        # Extract channel from column name: PathName_Cycle01_A -> Cycle01_A
        channel = col.replace("PathName_", "")
        df[col] = df[col] + "/" + channel + "/"

    # 3. Add channel subdirectories to painting paths
    painting_cols = [col for col in df.columns if col.startswith("PathName_Corr")]
    for col in painting_cols:
        # Extract channel from column name: PathName_CorrDNA -> CorrDNA
        channel = col.replace("PathName_", "")
        df[col] = df[col] + channel + "/"

    # 4. Transform all filenames
    for col in df.columns:
        if col.startswith("FileName_"):
            # Transform barcoding: Plate_Plate1_Well_A1_Site_0_Cycle01_A.tiff -> Cycle01_A_Site_0.tiff
            df[col] = df[col].str.replace(
                r"Plate_[^_]*_Well_[^_]*_Site_(\d+)_(Cycle\d+_\w+)\.tiff",
                r"\2_Site_\1.tiff",
                regex=True,
            )
            # Transform painting: Plate_Plate1_Well_A1_Site_0_CorrDNA.tiff -> CorrDNA_Site_0.tiff
            df[col] = df[col].str.replace(
                r"Plate_[^_]*_Well_[^_]*_Site_(\d+)_(Corr\w+)\.tiff",
                r"\2_Site_\1.tiff",
                regex=True,
            )

    # 5. HACK: Increment sites 0->1, 1->2, etc because:
    #    - CSV has sites 0,1,2,3 and cropped tiles happen to be numbered 1,2,3,4
    #    - This is pure coincidence for this test case (4 sites -> 4 tiles)
    #    - In reality, cropped tile numbering has no relation to original site numbering
    for col in df.columns:
        if col.startswith("FileName_"):
            df[col] = df[col].str.replace(
                r"Site_(\d+)", lambda m: f"Site_{int(m.group(1)) + 1}", regex=True
            )

    # 5b. Increment numeric Metadata_Site to keep it consistent with filename site increments
    if "Metadata_Site" in df.columns:
        # Coerce to integer and increment
        df["Metadata_Site"] = (
            pd.to_numeric(df["Metadata_Site"], errors="raise").astype(int) + 1
        )

    # Save transformed CSV
    df.to_csv(output_file, index=False)
    print(f"Saved transformed CSV with {len(df)} rows")

    # Show sample of first transformed row
    print("\nSample transformed paths:")
    print(f"  Barcoding: {df.iloc[0]['PathName_Cycle01_A']}")
    print(f"  Painting: {df.iloc[0]['PathName_CorrDNA']}")
    print("Sample transformed filenames:")
    print(f"  Barcoding: {df.iloc[0]['FileName_Cycle01_A']}")
    print(f"  Painting: {df.iloc[0]['FileName_CorrDNA']}")


if __name__ == "__main__":
    main()
