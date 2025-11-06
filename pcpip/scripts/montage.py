#!/usr/bin/env python
"""
Simple montage creator for image folders.

Design philosophy:
- Detect image patterns in a folder and arrange them automatically
- Support both numpy arrays (.npy) and regular images (.png, .jpg)
- Use PIL for proper image handling
- Keep the interface minimal and intuitive

IMPORTANT - Naming Convention Dependencies:
This script relies on specific file and directory naming patterns from the PCPIP pipeline.
If the pipeline's naming conventions change, update the PATTERN_* constants below.

Current patterns (as of Nov 2025):
- Stitched images: {Plate}-{Well}-Corr{Channel}-Stitched.tiff (Cell Painting)
                   {Plate}-{Well}-Cycle##_{Channel}-Stitched.tiff (Barcoding)
- Cropped tiles:   Plate_{Plate}_Well_{Well}_Site_{Site}_Corr{Channel}.tiff (Cell Painting)
                   Plate_{Plate}_Well_{Well}_Site_{Site}_Cycle##_{Channel}.tiff (Barcoding)
- Illumination:    Plate#_Illum{Channel}.npy or Plate#_IllumCycle##_{Channel}.npy
- Segmentation:    Plate_{Plate}_Well_{Well}_Site_{Site}_{Channel}_SegmentCheck.png

Usage:
    # Direct execution (requires numpy and pillow installed):
    ./montage.py input_dir output.png --pattern ".*\\.npy$"

    # Using pixi for dependency management (recommended):
    pixi exec -c conda-forge --spec python=3.13 --spec numpy=2.3.3 --spec pillow=11.3.0 -- python montage.py input_dir output.png --pattern '.*.npy$'

    # Cell Painting illumination only (exclude Cycle):
    pixi exec -c conda-forge --spec python=3.13 --spec numpy=2.3.3 --spec pillow=11.3.0 -- python scripts/montage.py data/Source1/images/Batch1/illum/Plate1 illum_montage.png --pattern '^(?!.*Cycle).*.npy$'

    # Barcoding illumination only (must contain Cycle):
    pixi exec -c conda-forge --spec python=3.13 --spec numpy=2.3.3 --spec pillow=11.3.0 -- python scripts/montage.py data/Source1/images/Batch1/illum/Plate1 illum_montage.png --pattern '.*Cycle.*.npy$'

    # Segmentation check images:
    pixi exec -c conda-forge --spec python=3.13 --spec numpy=2.3.3 --spec pillow=11.3.0 -- python scripts/montage.py data/Source1/images/Batch1/images_segmentation/painting/Plate1 seg_montage.png --pattern '.*SegmentCheck.png$'

    # Stitched Cell Painting images (single channel):
    pixi exec -c conda-forge --spec python=3.13 --spec numpy=2.3.3 --spec pillow=11.3.0 -- python scripts/montage.py data/Source1/images/Batch1/images_corrected_stitched_10X/painting/Plate1 stitch_cp_montage.png --pattern '.*-CorrDNA-Stitched.tiff$'

    # Stitched Barcoding images (single channel, single cycle):
    pixi exec -c conda-forge --spec python=3.13 --spec numpy=2.3.3 --spec pillow=11.3.0 -- python scripts/montage.py data/Source1/images/Batch1/images_corrected_stitched_10X/barcoding/Plate1 stitch_bc_montage.png --pattern '.*-Cycle01_DNA-Stitched.tiff$'
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import numpy as np
from PIL import Image, ImageDraw, ImageFont


# =============================================================================
# NAMING PATTERN CONSTANTS
# =============================================================================
# These regex patterns are tied to PCPIP pipeline naming conventions.
# If file/directory naming changes, update these constants.

# Well identification (from filename - explicit format)
# Matches: "Well_A1" -> extracts "A1"
PATTERN_WELL_FILENAME = r"Well_([A-Z]\d+)"

# Stitched image patterns (compact format with hyphens, Nov 2025)
# Cell Painting: Matches "Plate1-A1-CorrDNA-Stitched.tiff" -> extracts well "A1" and channel "DNA"
PATTERN_STITCH_CP = r"([A-Za-z0-9]+)-([A-Z]\d+)-Corr([A-Za-z0-9]+)-Stitched"

# Barcoding: Matches "Plate1-A1-Cycle01_DNA-Stitched.tiff" -> extracts well "A1" and cycle-channel "Cycle01_DNA"
PATTERN_STITCH_BC = r"([A-Za-z0-9]+)-([A-Z]\d+)-(Cycle\d+_[A-Za-z0-9]+)-Stitched"

# Cycle identification in barcoding files
# Matches: "Cycle01" -> extracts "01"
PATTERN_CYCLE = r"Cycle(\d+)"

# Channel extraction from illumination correction files
# Matches: "Plate1_IllumDNA.npy" -> extracts "DNA"
PATTERN_ILLUM_CHANNEL = r"Illum([A-Za-z0-9]+)"

# Site identification in filenames
# Matches: "Site_1" or "Site1" -> extracts "1"
PATTERN_SITE = r"Site[_\s]?(\d+)"

# Label patterns (used for parsing derived labels, not raw filenames)
# Cycle-channel label format: "Cycle01_DNA" -> extracts cycle and channel
PATTERN_LABEL_CYCLE_CHANNEL = r"Cycle(\d+)_(.+)"
# Cycle number from label: "Cycle01" -> extracts "01"
PATTERN_LABEL_CYCLE = r"Cycle(\d+)"


def natural_sort_key(s: str) -> List:
    """Natural sorting key that handles numbers properly."""
    return [
        int(text) if text.isdigit() else text.lower()
        for text in re.split("([0-9]+)", s)
    ]


def normalize_array(arr: np.ndarray, percentile_clip: bool = True) -> np.ndarray:
    """
    Normalize array to 0-255 range.

    Args:
        arr: Input array
        percentile_clip: If True, clip to 1st-99th percentile before normalizing
                        (helps with dim images that have few bright pixels)
    """
    if percentile_clip:
        # Use percentile clipping for better contrast on dim images
        vmin = np.percentile(arr, 1)
        vmax = np.percentile(arr, 99)
        arr = np.clip(arr, vmin, vmax)

    if arr.max() > arr.min():
        arr = (arr - arr.min()) / (arr.max() - arr.min())
    return (arr * 255).astype(np.uint8)


def load_image(file_path: Path, apply_sqrt: bool = False, normalize: bool = True) -> Image.Image:
    """
    Load an image file and convert to PIL Image.

    Args:
        file_path: Path to the file
        apply_sqrt: Apply sqrt transform (for illumination functions)
        normalize: Apply intensity normalization (auto-stretch contrast)

    Returns:
        PIL Image object
    """
    if file_path.suffix == ".npy":
        # Load numpy array
        arr = np.load(file_path)
    else:
        # Load regular image file and convert to array
        img = Image.open(file_path)
        arr = np.array(img)

    # Apply sqrt transform if requested
    if apply_sqrt:
        arr = np.sqrt(np.maximum(arr, 0))

    # Apply normalization if requested
    if normalize:
        if len(arr.shape) == 3:
            # Multi-channel: normalize each channel separately
            normalized = np.zeros_like(arr)
            for i in range(arr.shape[2]):
                normalized[:, :, i] = normalize_array(arr[:, :, i])
            arr = normalized
        else:
            # Grayscale: normalize directly
            arr = normalize_array(arr)

    # Convert to PIL Image
    return Image.fromarray(arr)


def extract_pattern_groups(files: List[Path]) -> Dict[str, List[Tuple[str, Path]]]:
    """
    Analyze filenames to extract natural groupings.

    Returns dict of pattern_type -> [(label, path), ...]
    """
    patterns = {}

    for file_path in files:
        name = file_path.stem

        # Check for site-based patterns FIRST (segmentation images & cropped tiles)
        # These have site info in filename
        site_match = re.search(PATTERN_SITE, name)
        if site_match:
            site_num = site_match.group(1)

            # Also check for well info in filename
            well_match = re.search(PATTERN_WELL_FILENAME, name)
            if well_match:
                well = well_match.group(1)
                label = f"{well} - Site{site_num}"
            else:
                label = f"Site{site_num}"

            patterns.setdefault("site", []).append((label, file_path))
            continue

        # Check for stitched Cell Painting images (compact format: Plate1-A1-CorrDNA-Stitched.tiff)
        stitch_cp_match = re.search(PATTERN_STITCH_CP, name)
        if stitch_cp_match:
            # group(1) is plate (unused here), group(2) is well, group(3) is channel
            well = stitch_cp_match.group(2)
            channel = stitch_cp_match.group(3)
            label = f"{well} - {channel}"
            patterns.setdefault("stitched", []).append((label, file_path))
            continue

        # Check for stitched Barcoding images (compact format: Plate1-A1-Cycle01_DNA-Stitched.tiff)
        stitch_bc_match = re.search(PATTERN_STITCH_BC, name)
        if stitch_bc_match:
            # group(1) is plate (unused here), group(2) is well, group(3) is cycle_channel
            well = stitch_bc_match.group(2)
            cycle_channel = stitch_bc_match.group(3)
            label = f"{well} - {cycle_channel}"
            patterns.setdefault("stitched", []).append((label, file_path))
            continue

        # Check for cycle-based patterns (for barcoding)
        cycle_match = re.search(PATTERN_CYCLE, name)
        if cycle_match:
            cycle = f"Cycle{cycle_match.group(1)}"
            # Extract channel from the rest
            channel_match = re.search(PATTERN_ILLUM_CHANNEL, name)
            if channel_match:
                channel = channel_match.group(1)
                key = f"{cycle}_{channel}"
                patterns.setdefault("cycle_channel", []).append((key, file_path))
            continue

        # Check for illumination patterns (without cycle)
        illum_match = re.search(PATTERN_ILLUM_CHANNEL, name)
        if illum_match:
            channel = illum_match.group(1)
            patterns.setdefault("channel", []).append((channel, file_path))
            continue

        # Default: use filename stem
        patterns.setdefault("default", []).append((name, file_path))

    return patterns


def determine_grid_layout(n_items: int, aspect_ratio: float = 1.5) -> Tuple[int, int]:
    """
    Determine optimal grid layout for n items.

    Args:
        n_items: Number of items to arrange
        aspect_ratio: Desired width/height ratio

    Returns:
        (n_cols, n_rows)
    """
    if n_items <= 0:
        return 0, 0
    if n_items == 1:
        return 1, 1

    # Try to get close to desired aspect ratio
    n_cols = int(np.ceil(np.sqrt(n_items * aspect_ratio)))
    n_rows = int(np.ceil(n_items / n_cols))

    # Adjust to minimize empty cells
    while n_cols * (n_rows - 1) >= n_items and n_rows > 1:
        n_rows -= 1

    return n_cols, n_rows


def create_montage(
    images: List[Tuple[str, Image.Image]],
    grid: Optional[Tuple[int, int]] = None,
    padding: int = 10,
    background_color: tuple = (255, 255, 255),
    label_height: Optional[int] = None,
) -> Image.Image:
    """
    Create a montage from a list of images.

    Args:
        images: List of (label, PIL.Image) tuples
        grid: Optional (cols, rows) specification
        padding: Space between images
        background_color: Background color (R, G, B)
        label_height: Height reserved for labels (auto-calculated if None)

    Returns:
        Montage as PIL Image
    """
    if not images:
        raise ValueError("No images to create montage")

    # Determine grid layout
    n_images = len(images)
    if grid is None:
        n_cols, n_rows = determine_grid_layout(n_images)
    else:
        n_cols, n_rows = grid

    # Get maximum dimensions
    max_width = max(img.width for _, img in images)
    max_height = max(img.height for _, img in images)

    # Auto-calculate label height based on image size (10-15% of image height)
    if label_height is None:
        label_height = max(20, min(40, int(max_height * 0.15)))

    # Calculate montage dimensions
    cell_width = max_width + padding * 2
    cell_height = max_height + label_height + padding * 2
    montage_width = n_cols * cell_width
    montage_height = n_rows * cell_height

    # Create montage image
    montage = Image.new("RGB", (montage_width, montage_height), background_color)
    draw = ImageDraw.Draw(montage)

    # Try to load a font for labels (size proportional to label_height)
    font_size = int(label_height * 0.6)  # 60% of label height
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except:
        try:
            # Try a common Linux font path
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size
            )
        except:
            font = ImageFont.load_default()

    # Place images
    for idx, (label, img) in enumerate(images):
        row = idx // n_cols
        col = idx % n_cols

        # Calculate position (center image in cell)
        x = col * cell_width + padding + (max_width - img.width) // 2
        y = row * cell_height + padding + label_height + (max_height - img.height) // 2

        # Convert grayscale to RGB if needed
        if img.mode == "L":
            img = img.convert("RGB")
        elif img.mode == "RGBA":
            # Handle RGBA by compositing on white background
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3] if len(img.split()) > 3 else None)
            img = bg

        # Paste image
        montage.paste(img, (x, y))

        # Add label
        label_x = col * cell_width + cell_width // 2
        label_y = row * cell_height + padding + label_height // 2

        # Get text bounding box for centering
        bbox = draw.textbbox((0, 0), label, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        draw.text(
            (label_x - text_width // 2, label_y - text_height // 2),
            label,
            fill=(0, 0, 0),
            font=font,
        )

    return montage


def organize_cycle_channel_layout(
    items: List[Tuple[str, Path]],
) -> List[Tuple[str, Path]]:
    """
    Organize cycle-channel data into a grid layout.
    Returns items sorted for row-major grid placement.
    """
    # Parse cycle and channel from each item
    parsed = []
    for label, path in items:
        match = re.match(PATTERN_LABEL_CYCLE_CHANNEL, label)
        if match:
            cycle = int(match.group(1))
            channel = match.group(2)
            parsed.append((cycle, channel, label, path))

    if not parsed:
        return items

    # Get unique cycles and channels
    cycles = sorted(set(p[0] for p in parsed))
    channels = sorted(set(p[1] for p in parsed))

    # Create lookup
    lookup = {(p[0], p[1]): (p[2], p[3]) for p in parsed}

    # Arrange in grid order (cycles as rows, channels as columns)
    result = []
    for cycle in cycles:
        for channel in channels:
            if (cycle, channel) in lookup:
                result.append(lookup[(cycle, channel)])

    return result


def main(
    input_dir: Path,
    output_file: Path,
    pattern: str = ".*",
    apply_sqrt: bool = None,
    grid: Optional[Tuple[int, int]] = None,
):
    """
    Create a montage from images in a directory.

    Args:
        input_dir: Directory containing images
        output_file: Output file path
        pattern: Regex pattern to match filenames (e.g., ".*\\.npy$", "^(?!.*Cycle).*\\.npy$")
        apply_sqrt: Apply sqrt transform (auto-detect if None)
        grid: Optional (cols, rows) grid specification
    """
    # Find matching files using regex
    import re

    regex = re.compile(pattern)
    all_files = input_dir.rglob("*")  # Recursive search
    files = sorted(
        [f for f in all_files if f.is_file() and regex.match(f.name)],
        key=lambda p: natural_sort_key(p.name),
    )

    if not files:
        print(f"No files matching '{pattern}' found in {input_dir}")
        return

    print(f"Found {len(files)} files")

    # Auto-detect if we should apply sqrt (for .npy illumination files)
    if apply_sqrt is None:
        apply_sqrt = all(f.suffix == ".npy" and "Illum" in f.name for f in files)
        if apply_sqrt:
            print("Detected illumination functions - applying sqrt transform")

    # Analyze patterns
    pattern_groups = extract_pattern_groups(files)

    # Determine organization strategy
    if "cycle_channel" in pattern_groups:
        # Barcoding-style cycle x channel grid
        items = organize_cycle_channel_layout(pattern_groups["cycle_channel"])

        # Calculate grid dimensions
        cycles = len(
            set(
                re.match(PATTERN_LABEL_CYCLE, label).group(1)
                for label, _ in items
                if re.match(PATTERN_LABEL_CYCLE, label)
            )
        )
        channels = len(items) // cycles if cycles > 0 else len(items)

        if grid is None:
            grid = (channels, cycles)

        print(f"Organizing as {cycles} cycles x {channels} channels")

    elif "channel" in pattern_groups:
        # Simple channel layout (single row)
        items = sorted(pattern_groups["channel"], key=lambda x: natural_sort_key(x[0]))
        if grid is None:
            grid = (len(items), 1)
        print(f"Organizing {len(items)} channels in a row")

    elif "stitched" in pattern_groups:
        # Stitched image layout (well + channel combinations)
        items = sorted(pattern_groups["stitched"], key=lambda x: natural_sort_key(x[0]))
        print(f"Organizing {len(items)} stitched images")

    elif "site" in pattern_groups:
        # Site-based layout
        items = sorted(pattern_groups["site"], key=lambda x: natural_sort_key(x[0]))
        print(f"Organizing {len(items)} sites")

    else:
        # Default layout
        items = [(f.stem, f) for f in files]
        print(f"Using default layout for {len(items)} files")

    # Load images
    images = []
    for label, file_path in items:
        try:
            img = load_image(file_path, apply_sqrt=apply_sqrt)
            images.append((label, img))
            print(f"  Loaded: {file_path.name} -> {label}")
        except Exception as e:
            print(f"  Error loading {file_path.name}: {e}")

    if not images:
        print("No images could be loaded")
        return

    # Create montage
    print(f"\nCreating montage with grid {grid if grid else 'auto'}...")
    montage = create_montage(images, grid=grid)

    # Save
    output_file.parent.mkdir(parents=True, exist_ok=True)
    montage.save(output_file, quality=95)
    print(f"Saved montage to: {output_file}")
    print(f"Dimensions: {montage.width}x{montage.height}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Create image montage from a directory"
    )
    parser.add_argument("input_dir", type=Path, help="Directory containing images")
    parser.add_argument("output_file", type=Path, help="Output montage file")
    parser.add_argument(
        "-p",
        "--pattern",
        default=".*",
        help="Regex pattern for filenames (default: .* matches all)",
    )
    parser.add_argument("--sqrt", action="store_true", help="Apply sqrt transform")
    parser.add_argument(
        "--no-sqrt", action="store_true", help="Don't apply sqrt transform"
    )
    parser.add_argument(
        "-g", "--grid", type=str, help="Grid layout as 'COLSxROWS' (e.g., '3x2')"
    )

    args = parser.parse_args()

    # Parse grid
    grid = None
    if args.grid:
        try:
            cols, rows = map(int, args.grid.lower().split("x"))
            grid = (cols, rows)
        except:
            print(f"Invalid grid format: {args.grid}. Use format like '3x2'")
            sys.exit(1)

    # Determine sqrt application
    apply_sqrt = None
    if args.sqrt:
        apply_sqrt = True
    elif args.no_sqrt:
        apply_sqrt = False

    main(
        args.input_dir,
        args.output_file,
        pattern=args.pattern,
        apply_sqrt=apply_sqrt,
        grid=grid,
    )
