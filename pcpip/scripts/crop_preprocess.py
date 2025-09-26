#!/usr/bin/env python3
"""
crop_preprocess.py - Crop images to reduce processing time

Description:
  This script crops all OME-TIFF images to a smaller size to speed up
  the PCPIP pipeline. It overwrites the original images in-place.
  Re-download the data from S3 to restore original images.

Usage:
  CROP_PERCENT=50 python3 /app/scripts/crop_preprocess.py

Environment Variables:
  CROP_PERCENT - Percentage of original size to keep (default: 50)
                 50 = crop to center 50% (reduces by 75% area)
                 25 = crop to center 25% (reduces by 94% area)
"""

import os
import sys
from glob import glob
import tifffile


def crop_image(img_path, crop_percent):
    """Crop a multi-page TIFF image preserving frame structure."""

    with tifffile.TiffFile(img_path) as tif:
        # Get dimensions from first frame
        height, width = tif.pages[0].shape[-2:]

        # Calculate center crop
        new_height = int(height * crop_percent / 100)
        new_width = int(width * crop_percent / 100)
        y_offset = (height - new_height) // 2
        x_offset = (width - new_width) // 2

        print(f"  Original: {width}x{height} -> Cropped: {new_width}x{new_height}")
        print(f"  Frames: {len(tif.pages)}")

        # Crop each frame separately (preserves multi-page structure)
        cropped_frames = []
        for page in tif.pages:
            frame_data = page.asarray()
            # Crop the last two dimensions (works for any shape)
            cropped_frame = frame_data[
                ..., y_offset : y_offset + new_height, x_offset : x_offset + new_width
            ]
            cropped_frames.append(cropped_frame)

    # Save to temporary file first to avoid corruption
    temp_file = img_path + ".cropped.tmp"
    try:
        # Write as multi-page TIFF (each frame as separate page)
        with tifffile.TiffWriter(temp_file) as writer:
            for frame in cropped_frames:
                writer.write(frame, compression="lzw")

        # Replace original with cropped
        os.replace(temp_file, img_path)
        return True
    except Exception as e:
        print(f"  ✗ Failed to crop: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Crop OME-TIFF images to reduce size")
    parser.add_argument(
        "--input_dir",
        default="/app/data/Source1/images/Batch1/images",
        help="Input directory containing images",
    )
    parser.add_argument(
        "--output_dir",
        default=None,
        help="Output directory (if not specified, crops in-place)",
    )
    args = parser.parse_args()

    # Configuration
    crop_percent = int(os.environ.get("CROP_PERCENT", "50"))
    images_base = args.input_dir
    output_base = args.output_dir or images_base

    print("===========================================")
    print("  Image Cropping Preprocessing")
    print(f"  Crop to: {crop_percent}% of original")
    print("===========================================")

    # Find all OME-TIFF files
    print("Finding all OME-TIFF files...")
    image_files = sorted(glob(f"{images_base}/**/*.ome.tiff", recursive=True))
    total_files = len(image_files)

    if total_files == 0:
        print(f"No OME-TIFF files found in {images_base}")
        sys.exit(1)

    print(f"Found {total_files} OME-TIFF files to process")
    print()

    # Process each image
    processed = 0
    failed = 0

    for img_path in image_files:
        processed += 1

        # Get relative path for display
        rel_path = os.path.relpath(img_path, images_base)
        print(f"[{processed}/{total_files}] Processing: {rel_path}")

        # If output_dir specified, copy to new location
        if output_base != images_base:
            import shutil

            out_path = os.path.join(output_base, rel_path)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            shutil.copy2(img_path, out_path)
            img_path = out_path

        if crop_image(img_path, crop_percent):
            print("  ✓ Successfully cropped")
        else:
            failed += 1

    print()
    print("===========================================")
    print("  Cropping Complete")
    print(f"  Processed: {processed} files")
    print(f"  Failed: {failed} files")
    print(f"  Size reduction: ~{100 - crop_percent * crop_percent // 100}%")
    print("===========================================")

    if failed > 0:
        print("WARNING: Some files failed to process")
        sys.exit(1)

    print()
    if output_base != images_base:
        print(f"Images have been cropped and saved to: {output_base}")
    else:
        print("Images have been cropped in-place.")
        print("To restore original images, re-download from S3:")
        print(
            "  aws s3 sync s3://nf-pooled-cellpainting-sandbox/data/test-data/fix-s1/ data/ --no-sign-request"
        )


if __name__ == "__main__":
    main()
