#!/usr/bin/env python3
"""
Flatten nested image directories for Fiji stitching.

Transforms:
  images_corrected/painting/Plate1/Plate1-A1-0/file.tiff
  images_corrected/painting/Plate1/Plate1-A1-1/file.tiff

Into:
  images_corrected_flattened/painting/Plate1/file.tiff
  images_corrected_flattened/painting/Plate1/file.tiff
"""

import shutil
from pathlib import Path


def flatten_images(source_base, target_base, track_type="painting"):
    """
    Flatten nested image directories.

    Args:
        source_base: Source directory (e.g., 'data/Source1/images/Batch1/images_corrected')
        target_base: Target directory (e.g., 'data/Source1/images/Batch1/images_corrected_flattened')
        track_type: 'painting' or 'barcoding'
    """
    source_dir = Path(source_base) / track_type
    target_dir = Path(target_base) / track_type

    if not source_dir.exists():
        print(f"Source directory does not exist: {source_dir}")
        return

    # Create target directory
    target_dir.mkdir(parents=True, exist_ok=True)

    # Walk through source directory
    for plate_dir in source_dir.iterdir():
        if not plate_dir.is_dir():
            continue

        print(f"Processing plate: {plate_dir.name}")

        # Create corresponding plate directory in target
        target_plate_dir = target_dir / plate_dir.name
        target_plate_dir.mkdir(parents=True, exist_ok=True)

        # Flatten all nested subdirectories
        for site_dir in plate_dir.iterdir():
            if not site_dir.is_dir():
                # Copy files at plate level (if any)
                shutil.copy2(site_dir, target_plate_dir / site_dir.name)
                continue

            print(f"  Flattening: {site_dir.name}")

            # Copy all files from nested directory to flat plate directory
            for img_file in site_dir.iterdir():
                if img_file.is_file():
                    target_file = target_plate_dir / img_file.name
                    shutil.copy2(img_file, target_file)

        print(
            f"  Copied {len(list(target_plate_dir.glob('*.tif*')))} files to {target_plate_dir}"
        )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Flatten nested image directories for Fiji stitching"
    )
    parser.add_argument(
        "--source",
        default="data/Source1/images/Batch1/images_corrected",
        help="Source directory",
    )
    parser.add_argument(
        "--target",
        default="data/Source1/images/Batch1/images_corrected_flattened",
        help="Target directory",
    )
    parser.add_argument(
        "--track",
        choices=["painting", "barcoding", "both"],
        default="both",
        help="Which track to flatten",
    )

    args = parser.parse_args()

    if args.track in ["painting", "both"]:
        print("Flattening painting images...")
        flatten_images(args.source, args.target, "painting")

    if args.track in ["barcoding", "both"]:
        print("Flattening barcoding images...")
        flatten_images(args.source, args.target, "barcoding")

    print(f"\nDone! Flattened images are in: {args.target}")
