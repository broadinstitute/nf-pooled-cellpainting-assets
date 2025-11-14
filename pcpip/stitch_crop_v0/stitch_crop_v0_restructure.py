#!/usr/bin/env python3
"""
Restructure legacy stitch_crop_v0 output to match production format.

Legacy:  output/{track}_{type}/{Plate}-{Well}/{Channel}/{Channel}_Site_{N}.tiff
Production: images_corrected_{type}/{track}/{Plate}/{Plate}-{Well}/Plate_{Plate}_Well_{Well}_Site_{N}_{Channel}.tiff

Usage:
    python stitch_crop_v0_restructure.py --source output/ --dest ./ --dry-run
    python stitch_crop_v0_restructure.py --source output/ --dest ./ --execute
"""

import argparse
import re
from pathlib import Path
import shutil


def parse_legacy_path(file_path, source_dir):
    """Extract metadata from legacy file path."""
    rel_path = file_path.relative_to(source_dir)
    parts = rel_path.parts

    # Parse: {track}_{type}/{Plate}-{Well}/...
    dir_name = parts[0]
    match = re.match(r'(\w+)_(cropped|stitched|stitched_10X)$', dir_name)
    if not match:
        return None

    track, output_type = match.groups()
    plate_well = parts[1]

    # Extract plate and well from "Plate1-A1"
    match = re.match(r'(.+?)-([A-Z]\d+)$', plate_well)
    if not match:
        return None

    plate, well = match.groups()

    return {
        'track': track,
        'type': output_type,
        'plate': plate,
        'well': well,
        'plate_well': plate_well,
    }


def transform_stitched_filename(filename, plate, well):
    """Transform stitched filename: StitchedPlate_Plate1_Well_A1_Site__CorrDNA.tiff -> Plate1-A1-CorrDNA-Stitched.tiff"""
    match = re.match(r'StitchedPlate_.+?_Well_.+?_Site__(.+)\.tiff$', filename)
    if not match:
        return None

    channel = match.group(1)
    return f"{plate}-{well}-{channel}-Stitched.tiff"


def transform_cropped_filename(filename, plate, well):
    """Transform cropped filename: CorrDNA/CorrDNA_Site_1.tiff -> Plate_Plate1_Well_A1_Site_1_CorrDNA.tiff"""
    match = re.match(r'(.+?)_Site_(\d+)\.tiff$', filename)
    if not match:
        return None

    channel, site = match.groups()
    return f"Plate_{plate}_Well_{well}_Site_{site}_{channel}.tiff"


def get_destination_path(file_path, source_dir, dest_dir, metadata):
    """Generate production-format destination path."""
    track = metadata['track']
    output_type = metadata['type']
    plate = metadata['plate']
    well = metadata['well']
    plate_well = metadata['plate_well']

    rel_path = file_path.relative_to(source_dir)
    parts = rel_path.parts
    filename = parts[-1]

    # Determine new filename based on type
    if output_type in ('stitched', 'stitched_10X'):
        new_filename = transform_stitched_filename(filename, plate, well)
    else:  # cropped
        new_filename = transform_cropped_filename(filename, plate, well)

    if not new_filename:
        return None

    # Build destination path: images_corrected_{type}/{track}/{plate}/{plate}-{well}/
    dest_path = dest_dir / f"images_corrected_{output_type}" / track / plate / plate_well / new_filename

    return dest_path


def restructure(source_dir, dest_dir, dry_run=True):
    """Restructure legacy output to production format."""
    source_dir = Path(source_dir)
    dest_dir = Path(dest_dir)

    if not source_dir.exists():
        print(f"Error: Source directory '{source_dir}' does not exist")
        return

    # Find all TIFF files
    tiff_files = list(source_dir.rglob('*.tiff'))

    if not tiff_files:
        print(f"No TIFF files found in '{source_dir}'")
        return

    print(f"Found {len(tiff_files)} TIFF files")
    print(f"Mode: {'DRY RUN (no changes)' if dry_run else 'EXECUTE (moving files)'}")
    print()

    stats = {'success': 0, 'skipped': 0, 'error': 0}

    for file_path in sorted(tiff_files):
        # Parse legacy path
        metadata = parse_legacy_path(file_path, source_dir)
        if not metadata:
            print(f"⚠ Skip (unknown format): {file_path.relative_to(source_dir)}")
            stats['skipped'] += 1
            continue

        # Generate destination path
        dest_path = get_destination_path(file_path, source_dir, dest_dir, metadata)
        if not dest_path:
            print(f"⚠ Skip (can't transform): {file_path.relative_to(source_dir)}")
            stats['skipped'] += 1
            continue

        # Check if already exists
        if dest_path.exists():
            print(f"⚠ Skip (exists): {dest_path.relative_to(dest_dir)}")
            stats['skipped'] += 1
            continue

        # Show transformation
        print(f"✓ {file_path.relative_to(source_dir)}")
        print(f"  → {dest_path.relative_to(dest_dir)}")

        # Execute if not dry run
        if not dry_run:
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(file_path, dest_path)
                stats['success'] += 1
            except Exception as e:
                print(f"  ✗ Error: {e}")
                stats['error'] += 1
        else:
            stats['success'] += 1

    # Summary
    print()
    print("=" * 60)
    print("Summary:")
    print(f"  Total files: {len(tiff_files)}")
    print(f"  {'Would move' if dry_run else 'Moved'}: {stats['success']}")
    print(f"  Skipped: {stats['skipped']}")
    print(f"  Errors: {stats['error']}")

    if dry_run and stats['success'] > 0:
        print()
        print("Run with --execute to actually move files")


def main():
    parser = argparse.ArgumentParser(
        description='Restructure legacy stitch_crop_v0 output to production format',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--source', required=True, help='Source directory (e.g., output/)')
    parser.add_argument('--dest', required=True, help='Destination base directory (e.g., ./)')

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true', help='Preview changes without copying')
    mode.add_argument('--execute', action='store_true', help='Actually copy files')

    args = parser.parse_args()

    restructure(
        source_dir=args.source,
        dest_dir=args.dest,
        dry_run=args.dry_run
    )


if __name__ == '__main__':
    main()
