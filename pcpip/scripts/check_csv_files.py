#!/usr/bin/env python3
"""Check if files referenced in a CellProfiler CSV exist."""

# /// script
# dependencies = ["pandas"]
# ///

import pandas as pd
import sys
import os


def main():
    if len(sys.argv) != 2:
        print("Usage: python check_csv_files.py input.csv")
        sys.exit(1)

    csv_file = sys.argv[1]
    df = pd.read_csv(csv_file)

    total, found, missing = 0, 0, 0

    for _, row in df.iterrows():
        for col in df.columns:
            if col.startswith("PathName_"):
                channel = col.replace("PathName_", "")
                file_col = f"FileName_{channel}"

                if (
                    file_col in df.columns
                    and not pd.isna(row[col])
                    and not pd.isna(row[file_col])
                ):
                    path = os.path.join(row[col], row[file_col])

                    # Try container path, then host path
                    exists = os.path.exists(path)
                    if not exists and path.startswith("/app/data/"):
                        exists = os.path.exists(path.replace("/app/data/", "data/"))

                    total += 1
                    if exists:
                        found += 1
                    else:
                        missing += 1
                        print(f"Missing: {path}")

    print(f"Total: {total}, Found: {found}, Missing: {missing}")
    sys.exit(0 if missing == 0 else 1)


if __name__ == "__main__":
    main()
