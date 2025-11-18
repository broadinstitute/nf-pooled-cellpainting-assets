#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "pandas",
# ]
# ///
"""
Samplesheet generator for PCPIP pipelines.

Scans image directories (local or S3) and generates samplesheet CSV by parsing
filenames with regex patterns. Eliminates manual samplesheet creation.

The script uses a dataset-centric approach where specifying a dataset (e.g., fix_s1)
automatically processes both painting and barcoding arms with their respective patterns
and channel mappings.

Usage:
  # Local directory - all wells
  uv run scripts/samplesheet_generate.py data/Source1/images/Batch1/images \
    --dataset fix_s1 \
    --output data/Source1/workspace/samplesheets/samplesheet1.csv \
    --batch Batch1

  # Local directory - specific wells (recommended - filters at source)
  uv run scripts/samplesheet_generate.py data/Source1/images/Batch1/images \
    --dataset fix_s1 \
    --output data/Source1/workspace/samplesheets/samplesheet1.csv \
    --batch Batch1 \
    --wells "A1"

  # S3 URI - generates samplesheet without downloading images
  uv run scripts/samplesheet_generate.py \
    s3://nf-pooled-cellpainting-sandbox/data/test-data/fix-s1/Source1/images/Batch1/images/ \
    --dataset fix_s1 \
    --output samplesheet.csv \
    --batch Batch1 \
    --wells "A1,A2" \
    --no-sign-request

  # S3 with AWS profile (cpg0032 dataset)
  uv run scripts/samplesheet_generate.py \
    s3://cellpainting-gallery/cpg0032-pooled-rare/broad/images/2025_06_23_Batch3/images/Plate_A/ \
    --dataset cpg0032 \
    --output samplesheet.csv \
    --batch Batch3 \
    --aws-profile my-profile

Available Datasets:
  - fix_s1: .ome.tiff files with 20X_CP_* (painting) and 20X_c*_SBS-* (barcoding) directories
  - cpg0032: .nd2 files with 20X_CP_Plate_* (painting) and 10X-SBS-* (barcoding) directories

Dataset-Specific Patterns:
  Each dataset defines both arms (painting + barcoding) with:
  - Filename regex patterns with named groups: plate, well, site, channels, cycle
  - Track-specific channel mappings (same hardware channel can mean different biology)

  fix_s1 (.ome.tiff):
    Painting:  {plate}/20X_CP_*/{filename}
    Barcoding: {plate}/20X_c{cycle}_SBS-{cycle}/{filename}
    Example: Plate1/20X_CP_*/WellA1_PointA1_0000_Channel*_Seq0000.ome.tiff

  cpg0032 (.nd2):
    Painting:  {plate}/20X_CP_Plate_{plate}/{filename}
    Barcoding: {plate}/10X-SBS-{cycle}/{filename}
    Example: Plate_A/20X_CP_Plate_A/WellA1_PointA1_0000_Channel*_Seq0000.nd2

  All filenames follow:
    Well{W}_Point{W}_{SITE:04d}_Channel{CHANNELS}_Seq{SEQ:04d}.[ome.tiff|nd2]

Adding New Datasets:
  Add a new entry to the DATASETS dict with both arms:

  DATASETS['dataset_x'] = {
      'painting': {
          'pattern': re.compile(r'...'),  # Regex with named groups
          'channel_map': {...},           # Raw → normalized channel names
          'default_cycle': 1,             # Always 1 for painting
      },
      'barcoding': {
          'pattern': re.compile(r'...'),  # Must include (?P<cycle>\\d+) group
          'channel_map': {...},           # Different mapping than painting!
          'default_cycle': None,          # Extracted from directory name
      },
  }

  Update file extensions in list_local_files() if needed (e.g., .tif, .tiff, etc.)

Channel Name Normalization:
  Channel names from filenames are normalized using dataset and track-specific channel maps.
  Each dataset has separate maps for painting and barcoding tracks because the same
  hardware channel (e.g., A594) can measure different biological targets in different assays.

  Examples:
    fix_s1 Painting:   PhalloAF750 → Phalloidin, DAPI → DNA
    fix_s1 Barcoding:  C → C, A → A, T → T, G → G, DAPI → DNA
    cpg0032 Painting:  GFP_long → Flag_long, A594 → Mito, Cy5 → ER
    cpg0032 Barcoding: Cy3 → G, A594 → T, Cy5 → A, Cy7 → C (same channel, different meaning!)

Output:
  Samplesheet CSV with columns: path, arm, batch, plate, well, channels, site, cycle, n_frames
  - For local paths: relative paths like "pcpip/data/..."
  - For S3: full S3 URIs like "s3://bucket/path/..."
  - Contains rows for BOTH painting and barcoding arms automatically
  This samplesheet is used by load_data_generate.py to create LoadData CSVs for CellProfiler.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
import pandas as pd


# Dataset registry - add new datasets here
# Each dataset has both painting and barcoding arms with their own patterns and channel maps
# Format: {
#   'dataset_name': {
#     'painting': {
#       'pattern': compiled regex with named groups (plate, well, site, channels),
#       'channel_map': dict mapping raw channel names to normalized names,
#       'default_cycle': cycle number (always 1 for painting)
#     },
#     'barcoding': {
#       'pattern': compiled regex with named groups (plate, well, site, channels, cycle),
#       'channel_map': dict mapping raw channel names to normalized names,
#       'default_cycle': None (extracted from directory name in match)
#     }
#   }
# }

DATASETS = {
    'fix_s1': {
        'painting': {
            'pattern': re.compile(
                r'(?P<plate>Plate\d+)/20X_CP_.*?/'
                r'Well(?P<well>[A-Z]\d+)_Point[A-Z]\d+_(?P<site>\d{4})_'
                r'Channel(?P<channels>.*?)_Seq\d+\.ome\.tiff$'
            ),
            'channel_map': {
                'PhalloAF750': 'Phalloidin',
                'CHN2-AF488': 'CHN2',
                'DAPI': 'DNA',
            },
            'default_cycle': 1,
        },
        'barcoding': {
            'pattern': re.compile(
                r'(?P<plate>Plate\d+)/20X_c(?P<cycle>\d+)_SBS-\d+/'
                r'Well(?P<well>[A-Z]\d+)_Point[A-Z]\d+_(?P<site>\d{4})_'
                r'Channel(?P<channels>.*?)_Seq\d+\.ome\.tiff$'
            ),
            'channel_map': {
                'C': 'C',
                'A': 'A',
                'T': 'T',
                'G': 'G',
                'DAPI': 'DNA',
            },
            'default_cycle': None,
        },
    },
    'cpg0032': {
        'painting': {
            'pattern': re.compile(
                r'(?P<plate>Plate_[A-Z])/20X_CP_Plate_[A-Z]/'
                r'Well(?P<well>[A-Z]\d+)_Point[A-Z]\d+_(?P<site>\d{4})_'
                r'Channel(?P<channels>.*?)_Seq\d+\.nd2$'
            ),
            'channel_map': {
                'DAPI': 'DNA',
                'GFP_long': 'Flag_long',
                'GFP': 'Flag',
                'A594': 'Mito',
                'Cy5': 'ER',
                '750': 'WGA',
            },
            'default_cycle': 1,
        },
        'barcoding': {
            'pattern': re.compile(
                r'(?P<plate>Plate_[A-Z])/10X-SBS-(?P<cycle>\d+)/'
                r'Well(?P<well>[A-Z]\d+)_Point[A-Z]\d+_(?P<site>\d{4})_'
                r'Channel(?P<channels>.*?)_Seq\d+\.nd2$'
            ),
            'channel_map': {
                'DAPI': 'DNA',
                'Cy3': 'G',
                'A594': 'T',
                'Cy5': 'A',
                'Cy7': 'C',
            },
            'default_cycle': None,
        },
    },
}


def is_s3_uri(path):
    """Check if path is an S3 URI."""
    return str(path).startswith('s3://')


def list_s3_files(s3_uri, aws_profile=None, no_sign_request=False):
    """
    List files from S3 using aws s3 ls.

    Args:
        s3_uri: S3 URI (e.g., s3://bucket/prefix/)
        aws_profile: AWS profile name (optional)
        no_sign_request: Use anonymous access (optional)

    Returns:
        List of full S3 URIs to files
    """
    cmd = ['aws', 's3', 'ls', s3_uri, '--recursive']

    if no_sign_request:
        cmd.append('--no-sign-request')
    elif aws_profile:
        cmd.extend(['--profile', aws_profile])

    try:
        print(f"Listing files from S3: {s3_uri}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        # Parse output: "2025-10-17 13:48:08  168241 path/to/file"
        # Extract the S3 key (path after size) and reconstruct full S3 URI
        files = []
        bucket = s3_uri.replace('s3://', '').split('/')[0]

        for line in result.stdout.strip().split('\n'):
            if not line.strip():
                continue
            # Split: date, time, size, s3_key
            parts = line.split(None, 3)
            if len(parts) >= 4:
                s3_key = parts[3]
                files.append(f"s3://{bucket}/{s3_key}")

        return files
    except subprocess.CalledProcessError as e:
        print(f"Error listing S3 files: {e.stderr}", file=sys.stderr)
        raise
    except FileNotFoundError:
        print("Error: 'aws' command not found. Please install AWS CLI.", file=sys.stderr)
        raise


def list_local_files(local_dir):
    """
    List files from local directory using glob.

    Args:
        local_dir: Local directory path

    Returns:
        List of Path objects
    """
    input_path = Path(local_dir)

    if not input_path.exists():
        raise FileNotFoundError(f"Input directory not found: {local_dir}")

    # Find all image files - add new extensions here as needed
    files_ometiff = list(input_path.glob("**/*.ome.tiff"))
    files_nd2 = list(input_path.glob("**/*.nd2"))
    # Add more: files_ext = list(input_path.glob("**/*.ext"))
    files = sorted(files_ometiff + files_nd2)

    if not files:
        raise ValueError(f"No .ome.tiff or .nd2 files found in {local_dir}")

    return files


def normalize_channels(channels_str, channel_map):
    """Normalize channel names from filename to standard names using dataset-specific map."""
    channels = channels_str.split(',')
    normalized = [channel_map.get(ch, ch) for ch in channels]
    return ','.join(normalized)


def parse_image_file(file_path, batch, dataset, is_s3=False):
    """
    Parse image file path and extract metadata using dataset-specific patterns.

    Args:
        file_path: Path to image file (str for S3, Path for local)
        batch: Batch name
        dataset: Dataset name (e.g., 'fix_s1', 'cpg0032')
        is_s3: Whether this is an S3 URI

    Returns:
        dict with samplesheet columns or None if no match
    """
    path_str = str(file_path)

    # Try both arms (painting and barcoding) for the specified dataset
    for arm in ['painting', 'barcoding']:
        arm_config = DATASETS[dataset][arm]
        pattern = arm_config['pattern']
        channel_map = arm_config['channel_map']
        default_cycle = arm_config['default_cycle']

        match = pattern.search(path_str)
        if match:
            data = match.groupdict()
            data['arm'] = arm
            data['cycle'] = int(data['cycle']) if 'cycle' in data and data['cycle'] else default_cycle
            data['batch'] = batch
            # Store full S3 URI or local relative path
            data['path'] = path_str if is_s3 else f"pcpip/{file_path}"
            data['site'] = int(data['site'])
            data['channels'] = normalize_channels(data['channels'], channel_map)
            data['n_frames'] = len(data['channels'].split(','))
            return data

    # No match for either arm
    return None


def generate_samplesheet(input_dir, dataset, batch='Batch1', aws_profile=None, no_sign_request=False):
    """
    Generate samplesheet by scanning image directory (local or S3).

    Args:
        input_dir: Path to images directory or S3 URI
                  (e.g., data/Source1/images/Batch1/images or s3://bucket/prefix/)
        dataset: Dataset name (e.g., 'fix_s1', 'cpg0032')
        batch: Batch name (default: Batch1)
        aws_profile: AWS profile name for S3 access (optional)
        no_sign_request: Use anonymous S3 access (optional)

    Returns:
        pandas DataFrame with samplesheet data
    """
    # Validate dataset
    if dataset not in DATASETS:
        available = ', '.join(DATASETS.keys())
        raise ValueError(f"Unknown dataset '{dataset}'. Available datasets: {available}")

    # Detect source type and list files
    is_s3 = is_s3_uri(input_dir)

    if is_s3:
        image_files = list_s3_files(input_dir, aws_profile, no_sign_request)
    else:
        image_files = list_local_files(input_dir)

    if not image_files:
        raise ValueError(f"No image files (.ome.tiff or .nd2) found in {input_dir}")

    print(f"Found {len(image_files)} image files")
    print(f"Using dataset: {dataset}")

    # Parse each file
    rows = []
    skipped = []

    for file_path in image_files:
        data = parse_image_file(file_path, batch, dataset, is_s3=is_s3)
        if data:
            rows.append(data)
        else:
            skipped.append(file_path)

    if skipped:
        print(f"Warning: Skipped {len(skipped)} files that didn't match {dataset} patterns:")
        for path in skipped[:5]:  # Show first 5
            print(f"  {path}")
        if len(skipped) > 5:
            print(f"  ... and {len(skipped) - 5} more")

    if not rows:
        raise ValueError(f"No files matched the expected {dataset} patterns")

    # Create DataFrame with correct column order
    df = pd.DataFrame(rows)
    column_order = ['path', 'arm', 'batch', 'plate', 'well', 'channels', 'site', 'cycle', 'n_frames']
    df = df[column_order]

    # Sort by arm, cycle, well, site for consistent output
    df = df.sort_values(['arm', 'cycle', 'well', 'site']).reset_index(drop=True)

    print(f"Generated samplesheet with {len(df)} rows")
    print(f"  Painting rows: {len(df[df['arm'] == 'painting'])}")
    print(f"  Barcoding rows: {len(df[df['arm'] == 'barcoding'])}")

    return df


def main():
    parser = argparse.ArgumentParser(
        description="Generate samplesheet CSV from image directory (local or S3)"
    )
    parser.add_argument(
        'input_dir',
        help='Path to images directory or S3 URI (e.g., data/Source1/images/Batch1/images or s3://bucket/prefix/)'
    )
    parser.add_argument(
        '--dataset',
        required=True,
        choices=list(DATASETS.keys()),
        help='Dataset type - determines filename patterns and channel mappings for both painting and barcoding arms'
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
    parser.add_argument(
        '--aws-profile',
        default=None,
        help='AWS profile name for S3 access (optional)'
    )
    parser.add_argument(
        '--no-sign-request',
        action='store_true',
        help='Use anonymous S3 access (no AWS credentials required)'
    )

    args = parser.parse_args()

    # Generate samplesheet
    df = generate_samplesheet(
        args.input_dir,
        args.dataset,
        args.batch,
        aws_profile=args.aws_profile,
        no_sign_request=args.no_sign_request
    )

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
