#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "pandas",
# ]
# ///
"""
Samplesheet generator for PCPIP pipelines.

Scans image directories and generates samplesheet CSV by parsing filenames
with regex patterns. Eliminates manual samplesheet creation.

Usage:
  # Generate samplesheet for all wells
  uv run scripts/samplesheet_generate.py data/Source1/images/Batch1/images \
    --output data/Source1/workspace/samplesheets/samplesheet1.csv \
    --batch Batch1

  # Generate samplesheet for specific wells (recommended - filters at source)
  uv run scripts/samplesheet_generate.py data/Source1/images/Batch1/images \
    --output data/Source1/workspace/samplesheets/samplesheet1.csv \
    --batch Batch1 \
    --wells "A1"

Filename Pattern Matching:
  This script uses hardcoded regex patterns (PAINTING_PATTERN and BARCODING_PATTERN
  defined at lines 27-37) to extract metadata from image filenames.

  Current patterns expect:
    Cell Painting: Well{W}_Point{W}_{SITE:04d}_Channel{CHANNELS}_Seq{SEQ:04d}.ome.tiff
    Barcoding:     Well{W}_Point{W}_{SITE:04d}_Channel{CHANNELS}_Seq{SEQ:04d}.ome.tiff

  Directory structure:
    Cell Painting: {plate}/20X_CP_*/{filename}
    Barcoding:     {plate}/20X_c{cycle}_SBS-{cycle}/{filename}

  To support different filename conventions, modify the regex patterns at lines 27-37.
  Future enhancement: make patterns configurable via CLI arguments.

Channel Name Normalization:
  Channel names from filenames are normalized using CHANNEL_MAP (line 40):
    PhalloAF750 → Phalloidin
    CHN2-AF488  → CHN2
    DAPI        → DNA
  To add/modify mappings, edit CHANNEL_MAP dictionary.

Output:
  Samplesheet CSV with columns: path, arm, batch, plate, well, channels, site, cycle, n_frames
  This samplesheet is used by load_data_generate.py to create LoadData CSVs for CellProfiler.
"""

import argparse
import re
from pathlib import Path
import pandas as pd


# Regex patterns with named capture groups
PAINTING_PATTERN = re.compile(
    r'(?P<plate>Plate\d+)/20X_CP_.*?/'
    r'Well(?P<well>[A-Z]\d+)_Point[A-Z]\d+_(?P<site>\d{4})_'
    r'Channel(?P<channels>.*?)_Seq\d+\.ome\.tiff$'
)

BARCODING_PATTERN = re.compile(
    r'(?P<plate>Plate\d+)/20X_c(?P<cycle>\d+)_SBS-\d+/'
    r'Well(?P<well>[A-Z]\d+)_Point[A-Z]\d+_(?P<site>\d{4})_'
    r'Channel(?P<channels>.*?)_Seq\d+\.ome\.tiff$'
)

# Channel name normalization
CHANNEL_MAP = {
    'PhalloAF750': 'Phalloidin',
    'CHN2-AF488': 'CHN2',
    'DAPI': 'DNA',
}


def normalize_channels(channels_str):
    """Normalize channel names from filename to standard names."""
    channels = channels_str.split(',')
    normalized = [CHANNEL_MAP.get(ch, ch) for ch in channels]
    return ','.join(normalized)


def parse_image_file(file_path, batch):
    """
    Parse image file path and extract metadata.

    Returns dict with samplesheet columns or None if no match.
    """
    path_str = str(file_path)

    # Try painting pattern
    match = PAINTING_PATTERN.search(path_str)
    if match:
        data = match.groupdict()
        data['arm'] = 'painting'
        data['cycle'] = 1
        data['batch'] = batch
        data['path'] = f"pcpip/{file_path}"
        data['site'] = int(data['site'])
        data['channels'] = normalize_channels(data['channels'])
        data['n_frames'] = len(data['channels'].split(','))
        return data

    # Try barcoding pattern
    match = BARCODING_PATTERN.search(path_str)
    if match:
        data = match.groupdict()
        data['arm'] = 'barcoding'
        data['cycle'] = int(data['cycle'])
        data['batch'] = batch
        data['path'] = f"pcpip/{file_path}"
        data['site'] = int(data['site'])
        data['channels'] = normalize_channels(data['channels'])
        data['n_frames'] = len(data['channels'].split(','))
        return data

    # No match
    return None


def generate_samplesheet(input_dir, batch='Batch1'):
    """
    Generate samplesheet by scanning image directory.

    Args:
        input_dir: Path to images directory (e.g., data/Source1/images/Batch1/images)
        batch: Batch name (default: Batch1)

    Returns:
        pandas DataFrame with samplesheet data
    """
    input_path = Path(input_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {input_dir}")

    # Find all .ome.tiff files
    image_files = sorted(input_path.glob("**/*.ome.tiff"))

    if not image_files:
        raise ValueError(f"No .ome.tiff files found in {input_dir}")

    print(f"Found {len(image_files)} image files")

    # Parse each file
    rows = []
    skipped = []

    for file_path in image_files:
        data = parse_image_file(file_path, batch)
        if data:
            rows.append(data)
        else:
            skipped.append(file_path)

    if skipped:
        print(f"Warning: Skipped {len(skipped)} files that didn't match patterns:")
        for path in skipped[:5]:  # Show first 5
            print(f"  {path}")
        if len(skipped) > 5:
            print(f"  ... and {len(skipped) - 5} more")

    if not rows:
        raise ValueError("No files matched the expected patterns")

    # Create DataFrame with correct column order
    df = pd.DataFrame(rows)
    column_order = ['path', 'arm', 'batch', 'plate', 'well', 'channels', 'site', 'cycle', 'n_frames']
    df = df[column_order]

    # Sort by arm, cycle, well, site for consistent output
    df = df.sort_values(['arm', 'cycle', 'well', 'site']).reset_index(drop=True)

    print(f"Generated samplesheet with {len(df)} rows")

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Generate samplesheet CSV from image directory"
    )
    parser.add_argument(
        'input_dir',
        help='Path to images directory (e.g., data/Source1/images/Batch1/images)'
    )
    parser.add_argument(
        '--output',
        default='samplesheet.csv',
        help='Output CSV file path (default: samplesheet.csv)'
    )
    parser.add_argument(
        '--batch',
        default='Batch1',
        help='Batch name (default: Batch1)'
    )
    parser.add_argument(
        '--wells',
        default=None,
        help='Comma-separated list of wells to include (e.g., "A1" or "A1,A2,B1"). If not specified, all wells are included.'
    )

    args = parser.parse_args()

    # Generate samplesheet
    df = generate_samplesheet(args.input_dir, args.batch)

    # Filter by wells if specified
    if args.wells:
        wells_list = [w.strip() for w in args.wells.split(',')]
        total_before = len(df)
        df = df[df['well'].isin(wells_list)].reset_index(drop=True)
        total_after = len(df)
        print(f"Filtered to wells {wells_list}: {total_before} → {total_after} rows")

        if total_after == 0:
            raise ValueError(f"No rows remaining after filtering to wells {wells_list}")

    # Save to CSV
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)

    print(f"Saved samplesheet to {output_path}")

    # Show summary
    print("\nSummary:")
    print(f"  Total rows: {len(df)}")
    print(f"  Painting rows: {len(df[df.arm == 'painting'])}")
    print(f"  Barcoding rows: {len(df[df.arm == 'barcoding'])}")
    print(f"  Wells: {sorted(df.well.unique())}")
    print(f"  Sites per well: {df.groupby('well')['site'].nunique().to_dict()}")


if __name__ == '__main__':
    main()
