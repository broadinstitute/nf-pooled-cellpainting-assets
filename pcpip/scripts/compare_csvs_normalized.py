#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "pandas",
# ]
# ///
"""Compare CSVs with path normalization and well filtering."""

import pandas as pd


def normalize_paths_in_df(df):
    """Normalize all paths by removing trailing slashes."""
    for col in df.columns:
        if "PathName" in col and col in df.columns:
            # Remove trailing slashes from paths
            df[col] = df[col].str.rstrip("/")
    return df


pipelines = [1, 2, 3, 5, 6, 7, 9]

for p in pipelines:
    ref_file = f"data/Source1/workspace/load_data_csv/Batch1/Plate1_trimmed/load_data_pipeline{p}_revised.csv"
    gen_file = f"load_data_pipeline{p}.csv"

    try:
        ref_df = pd.read_csv(ref_file)
        gen_df = pd.read_csv(gen_file)

        # Filter reference to only include wells that exist in generated
        if "Metadata_Well" in ref_df.columns and "Metadata_Well" in gen_df.columns:
            wells_in_gen = gen_df["Metadata_Well"].unique()
            ref_df = ref_df[ref_df["Metadata_Well"].isin(wells_in_gen)]

        # Normalize paths
        ref_df = normalize_paths_in_df(ref_df)
        gen_df = normalize_paths_in_df(gen_df)

        # Sort columns and rows for comparison
        ref_df = (
            ref_df.sort_index(axis=1)
            .sort_values(by=list(ref_df.columns))
            .reset_index(drop=True)
        )
        gen_df = (
            gen_df.sort_index(axis=1)
            .sort_values(by=list(gen_df.columns))
            .reset_index(drop=True)
        )

        # Compare
        pd.testing.assert_frame_equal(ref_df, gen_df, check_like=True)
        print(f"Pipeline {p}: ✓ MATCH")
    except AssertionError as e:
        print(f"Pipeline {p}: ✗ DIFFER")
        error_msg = str(e)
        # Show brief error message
        if "shape mismatch" in error_msg:
            print(f"  Shape: ref={ref_df.shape}, gen={gen_df.shape}")
        else:
            print(f"  {error_msg[:150]}...")
    except FileNotFoundError:
        print(f"Pipeline {p}: File not found")
