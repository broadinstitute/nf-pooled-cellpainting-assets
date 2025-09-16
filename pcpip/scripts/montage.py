#!/usr/bin/env python
"""
montage.py - Create visual montage of images

Purpose: Generate quality control montages for illumination correction functions,
         segmentation outputs, and other pipeline images.

Environment Requirements:
========================
Docker: Runs directly with pre-installed dependencies
Local:  Use pixi for dependency management:
        pixi exec --spec python>=3.11 --spec loguru --spec typer --spec numpy --spec matplotlib -- python montage.py [args]
        OR create a pixi task in pyproject.toml for convenience

Workflow Logic:
===============
1. INPUT PARSING: User specifies mode (illum_painting/illum_barcoding/generic),
   directory, output file, and optional filters (channels, cycles, patterns)

2. MODE ROUTING: Three distinct modes handle different data structures:

   a) illum_painting: Cell Painting illumination correction
      - Expects files: {Plate}_Illum{Channel}.npy
      - Default channels: DNA, Phalloidin, CHN2
      - Output: Single row montage

   b) illum_barcoding: Barcoding illumination with cycle organization
      - Expects files: {Plate}_Cycle{N}_Illum{Channel}.npy
      - Default channels: DNA, A, C, G, T
      - Default cycles: 1, 2, 3
      - Output: Grid montage (cycles x channels)

   c) generic: Flexible pattern-based file discovery
      - Accepts any file pattern (*.png, *.npy, etc.)
      - Extracts labels from filenames dynamically
      - Output: Single row montage

3. FILE LOADING:
   - Structured modes (illum_*) use specific naming conventions
   - Generic mode uses glob patterns and regex extraction
   - Supports both .npy (numpy arrays) and .png/.jpg (images)

4. IMAGE PROCESSING:
   - Grayscale images: Apply optional sqrt transform for illumination
   - Color images: Preserve as-is, only normalize if needed
   - All images normalized to 0-1 range for display

5. MONTAGE CREATION:
   - Simple montage: Single row of images (illum_painting, generic)
   - Grid montage: Organized by cycles and channels (illum_barcoding)
   - Automatic subplot sizing based on number of images

6. OUTPUT: Saves high-quality PNG (150 DPI) with descriptive title

Key Design Decisions:
- Modes are separate to handle different data organizations
- Generic mode sacrifices structure for flexibility
- No colorbars to maximize image space
- Automatic label extraction from filenames
- Defaults provided for common use cases

Usage:
    # Docker environment (dependencies pre-installed):
    ./montage.py /path/to/illum/Plate1 montage.png illum_painting
    python montage.py /path/to/images/Plate1-A1 montage.png generic --pattern "*.png"

    # Local development with pixi:
    pixi exec --spec python>=3.11 --spec loguru --spec typer --spec numpy --spec matplotlib -- python montage.py /path/to/illum/Plate1 montage.png illum_painting

    # Help:
    ./montage.py --help
"""

import re
import sys
from pathlib import Path
from typing import Dict, Tuple, Optional, List

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import typer
from loguru import logger
from typing_extensions import Annotated

# Use default loguru configuration

app = typer.Typer(help="Create QC montage of illumination correction functions")


def load_file(file_path: Path) -> np.ndarray:
    """
    Load an image file (.npy or .png)

    Args:
        file_path: Path to the file

    Returns:
        numpy array of the image
    """
    if file_path.suffix == ".npy":
        return np.load(file_path)
    elif file_path.suffix in [".png", ".jpg", ".jpeg"]:
        img = plt.imread(file_path)
        # Keep color images as-is, just handle RGBA
        if img.ndim == 3 and img.shape[2] == 4:
            img = img[:, :, :3]
        return img
    else:
        raise ValueError(f"Unsupported file type: {file_path.suffix}")


def load_image_files(
    input_dir: Path,
    identifier: str,
    pipeline_type: str,
    channels: Optional[List[str]] = None,
    cycles: Optional[List[int]] = None,
    file_pattern: str = "*.npy",
) -> Dict:
    """
    Load image files based on pipeline type

    Args:
        input_dir: Directory containing image files
        identifier: Identifier for file matching (e.g., 'Plate1' for illumination, 'Plate1-A1' for wells)
        pipeline_type: 'illum_painting', 'illum_barcoding', or 'generic'
        channels: List of channels to process (defaults based on pipeline type)
        cycles: List of cycles to process (for barcoding only)
        file_pattern: Pattern to match files (e.g., "*.npy", "*.png")

    Returns:
        Dictionary with structure:
            - For illum_painting/generic: {channel: array}
            - For illum_barcoding: {(cycle, channel): array}
    """
    image_data = {}

    if pipeline_type == "illum_painting":
        # Cell Painting pattern: {Plate}_Illum{Channel}.npy
        if channels:
            logger.info(f"Processing channels: {', '.join(channels)}")
        else:
            logger.info("No channels specified for painting mode")
            return image_data

        for channel in channels:
            file_pattern = f"{identifier}_Illum{channel}.npy"
            file_path = input_dir / file_pattern

            if file_path.exists():
                try:
                    image_data[channel] = load_file(file_path)
                    logger.success(f"Loaded: {file_path.name}")
                except Exception as e:
                    logger.warning(f"Could not load {file_path.name}: {e}")
            else:
                logger.debug(f"File not found: {file_path.name}")

    elif pipeline_type == "generic":
        # Generic image loading - just find all files matching pattern
        logger.info(f"Loading images with pattern: {file_pattern}")

        for file_path in sorted(input_dir.glob(file_pattern)):
            # Use full stem as the key to avoid duplicates
            # But try to extract a nice display name
            name = file_path.stem

            # Try to extract meaningful label from filename
            # Priority: Site info > Channel info > Full name
            display_name = name

            # Check for site information
            site_match = re.search(r"Site_(\d+)", name)
            if site_match:
                site_num = site_match.group(1)
                display_name = f"Site{site_num}"

                # Try to extract channel from common patterns
                # Look for CorrDNA, OrigDNA, or similar patterns
                channel_patterns = [
                    r"Corr([A-Za-z0-9]+)_",  # CorrDNA_
                    r"Orig([A-Za-z0-9]+)",  # OrigDNA
                    r"_([A-Za-z0-9]+)Mask",  # _CellMask
                    r"_Illum([A-Za-z0-9]+)",  # _IllumDNA
                ]
                for pattern in channel_patterns:
                    channel_match = re.search(pattern, name)
                    if channel_match:
                        display_name = f"Site{site_num}_{channel_match.group(1)}"
                        break
            else:
                # No site info, use filename or extract key part
                # Try to find the most meaningful part
                parts = name.split("_")
                # Use the last meaningful part that's not a common suffix
                for part in reversed(parts):
                    if part and part not in ["SegmentCheck", "Mask", "Overlay"]:
                        display_name = part
                        break

            # Filter by requested channels if specified
            if channels:
                # Check if any requested channel is in the filename
                if not any(ch in name for ch in channels):
                    continue

            try:
                # Use display name as key
                image_data[display_name] = load_file(file_path)
                logger.success(f"Loaded: {file_path.name} as {display_name}")
            except Exception as e:
                logger.warning(f"Could not load {file_path.name}: {e}")

    elif pipeline_type == "illum_barcoding":
        # Barcoding pattern: {Plate}_Cycle{N}_Illum{Channel}.npy
        # Apply defaults for cycles if not specified
        if cycles is None:
            cycles = [1, 2, 3]  # Default cycles

        logger.info(f"Processing cycles: {cycles}")
        if channels:
            logger.info(f"Processing channels: {', '.join(channels)}")
        else:
            logger.info("No channels specified for barcoding mode")
            return image_data

        for cycle in cycles:
            for channel in channels:
                file_pattern = f"{identifier}_Cycle{cycle}_Illum{channel}.npy"
                file_path = input_dir / file_pattern

                if file_path.exists():
                    try:
                        image_data[(cycle, channel)] = load_file(file_path)
                        logger.success(f"Loaded: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"Could not load {file_path.name}: {e}")
                else:
                    logger.debug(f"File not found: {file_path.name}")

    return image_data


def apply_visualization_transform(
    array: np.ndarray, apply_sqrt: bool = True
) -> np.ndarray:
    """
    Apply transformations to make patterns more visible

    Args:
        array: 2D numpy array of values
        apply_sqrt: Whether to apply sqrt transform (for illumination)

    Returns:
        Transformed array suitable for visualization
    """
    # Handle potential negative values or zeros
    array_positive = np.clip(array, 0, None)

    if apply_sqrt:
        # Apply square root transformation for illumination
        transformed = np.sqrt(array_positive)
    else:
        # For regular images, just use as-is
        transformed = array_positive

    # Normalize to 0-1 range for display
    if transformed.max() > transformed.min():
        transformed = (transformed - transformed.min()) / (
            transformed.max() - transformed.min()
        )

    return transformed


def prepare_image_for_display(array: np.ndarray, apply_sqrt: bool = False):
    """
    Prepare an image for display, detecting if it's color or grayscale

    Args:
        array: Image array
        apply_sqrt: Whether to apply sqrt transform

    Returns:
        Tuple of (processed_array, is_color)
    """
    is_color = array.ndim == 3 and array.shape[2] == 3

    if is_color:
        # For color images, just normalize to 0-1 if needed
        if array.max() > 1.0:
            processed = array / 255.0
        else:
            processed = array
    else:
        # For grayscale, apply transform
        processed = apply_visualization_transform(array, apply_sqrt=apply_sqrt)

    return processed, is_color


def create_simple_montage(
    image_data: Dict[str, np.ndarray],
    output_file: Path,
    identifier: str,
    apply_sqrt: bool = True,
    title_suffix: str = "Illumination Correction Functions",
) -> None:
    """
    Create a simple single-row montage of images

    Args:
        image_data: Dictionary {channel: array}
        output_file: Path to save montage
        identifier: Identifier for title (e.g., 'Plate1' or 'Plate1-A1')
        apply_sqrt: Whether to apply sqrt transform
        title_suffix: Suffix for the title (e.g., "Illumination Correction Functions" or "Segmentation Check")
    """
    n_channels = len(image_data)
    if n_channels == 0:
        logger.error("No image data to visualize")
        return

    logger.info(f"Creating montage with {n_channels} channel(s)")

    # Create figure with subplots
    fig, axes = plt.subplots(1, n_channels, figsize=(5 * n_channels, 5))

    # Handle single channel case
    if n_channels == 1:
        axes = [axes]

    # Sort channels for consistent ordering
    channels = sorted(image_data.keys())

    for idx, channel in enumerate(channels):
        array = image_data[channel]
        processed, is_color = prepare_image_for_display(array, apply_sqrt=apply_sqrt)

        if is_color:
            axes[idx].imshow(processed, interpolation="nearest")
        else:
            axes[idx].imshow(processed, cmap="gray", interpolation="nearest")
            # No colorbar - not needed for QC montages

        axes[idx].set_title(f"{channel}", fontsize=12)
        axes[idx].axis("off")

        logger.debug(f"Added {channel} to montage (shape: {array.shape})")

    # Add overall title
    fig.suptitle(
        f"{title_suffix} - {identifier}",
        fontsize=14,
        fontweight="bold",
    )

    # Save figure
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    logger.success(f"Saved montage to: {output_file}")
    plt.close()


def create_barcoding_montage(
    image_data: Dict[Tuple[int, str], np.ndarray],
    output_file: Path,
    identifier: str,
    apply_sqrt: bool = True,
    title_suffix: str = "Illumination Correction Functions (Barcoding)",
) -> None:
    """
    Create montage for Barcoding images (cycles x channels grid)

    Args:
        image_data: Dictionary {(cycle, channel): array}
        output_file: Path to save montage
        identifier: Identifier for title (e.g., 'Plate1')
        apply_sqrt: Whether to apply sqrt transform
        title_suffix: Suffix for the title
    """
    if len(image_data) == 0:
        logger.error("No image data to visualize")
        return

    # Extract unique cycles and channels
    cycles = sorted(set(key[0] for key in image_data.keys()))
    channels = sorted(set(key[1] for key in image_data.keys()))

    n_cycles = len(cycles)
    n_channels = len(channels)

    logger.info(f"Creating montage grid: {n_cycles} cycles x {n_channels} channels")

    # Create grid layout
    fig = plt.figure(figsize=(4 * n_channels, 4 * n_cycles))
    gs = gridspec.GridSpec(n_cycles, n_channels, figure=fig)

    for cycle_idx, cycle in enumerate(cycles):
        for channel_idx, channel in enumerate(channels):
            key = (cycle, channel)

            if key in image_data:
                ax = fig.add_subplot(gs[cycle_idx, channel_idx])

                array = image_data[key]
                processed, is_color = prepare_image_for_display(
                    array, apply_sqrt=apply_sqrt
                )

                if is_color:
                    ax.imshow(processed, interpolation="nearest")
                else:
                    ax.imshow(processed, cmap="gray", interpolation="nearest")
                ax.set_title(f"Cycle {cycle} - {channel}", fontsize=10)
                ax.axis("off")

                logger.debug(f"Added Cycle {cycle} - {channel} (shape: {array.shape})")
            else:
                # Empty subplot if data missing
                ax = fig.add_subplot(gs[cycle_idx, channel_idx])
                ax.text(
                    0.5,
                    0.5,
                    "No data",
                    ha="center",
                    va="center",
                    transform=ax.transAxes,
                    fontsize=10,
                )
                ax.axis("off")
                logger.debug(f"No data for Cycle {cycle} - {channel}")

    # Add overall title
    fig.suptitle(
        f"{title_suffix} - {identifier}",
        fontsize=14,
        fontweight="bold",
    )

    # Save figure
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    logger.success(f"Saved montage to: {output_file}")
    plt.close()


def parse_channels(value: str) -> List[str]:
    """Parse comma-separated channel names."""
    return [ch.strip() for ch in value.split(",")]


def parse_cycles(value: str) -> List[int]:
    """Parse comma-separated cycle numbers or ranges."""
    cycles = []
    for part in value.split(","):
        part = part.strip()
        if "-" in part:
            # Handle range like "1-3"
            start, end = part.split("-")
            cycles.extend(range(int(start), int(end) + 1))
        else:
            cycles.append(int(part))
    return sorted(set(cycles))  # Remove duplicates and sort


@app.command()
def main(
    input_dir: Annotated[Path, typer.Argument(help="Directory containing image files")],
    output_file: Annotated[
        Path, typer.Argument(help="Output file path for montage (PNG or PDF)")
    ],
    pipeline_type: Annotated[
        str,
        typer.Argument(
            help="Pipeline type: 'illum_painting', 'illum_barcoding', or 'generic'"
        ),
    ],
    channels: Annotated[
        Optional[str],
        typer.Option(
            "--channels",
            "-c",
            help="Comma-separated list of channels. Defaults: illum_painting='DNA,Phalloidin,CHN2', illum_barcoding='DNA,A,C,G,T'",
        ),
    ] = None,
    cycles: Annotated[
        Optional[str],
        typer.Option(
            "--cycles",
            help="Comma-separated list of cycles or ranges for barcoding (e.g., '1,2,3' or '1-3,5')",
        ),
    ] = None,
    pattern: Annotated[
        Optional[str],
        typer.Option(
            "--pattern",
            "-p",
            help="File pattern to match (e.g., '*.png', '*Orig*.png', '*.npy'). Defaults to '*.npy' for illumination, '*.png' for images",
        ),
    ] = None,
    no_sqrt: Annotated[
        bool,
        typer.Option("--no-sqrt", help="Disable sqrt transform (for regular images)"),
    ] = False,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose logging")
    ] = False,
) -> None:
    """
    Create montage of images for quality control purposes.

    Supports illumination correction functions (.npy files) and regular images (.png).
    For illumination functions, applies sqrt transform for better visibility.

    Examples:
        # Illumination functions for Cell Painting (identifier extracted from path: 'Plate1')
        ./montage.py data/illum/Plate1 output.png illum_painting

        # Generic images for segmentation (identifier extracted from path: 'Plate1-A1')
        ./montage.py data/segmentation/Plate1-A1 output.png generic --pattern "*.png"

        # Custom channels for illumination
        ./montage.py data/illum/Plate1 output.png illum_painting --channels DNA,Phalloidin

        # Barcoding illumination with custom cycles
        ./montage.py data/illum/Plate1 output.png illum_barcoding --cycles 1-3 --channels DNA,A,C
    """

    # Enable debug logging if verbose
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    # Validate pipeline type
    if pipeline_type not in ["illum_painting", "illum_barcoding", "generic"]:
        logger.error(
            f"Invalid pipeline type: {pipeline_type}. Must be 'illum_painting', 'illum_barcoding', or 'generic'"
        )
        raise typer.Exit(code=1)

    # Validate input directory
    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        raise typer.Exit(code=1)

    # Extract identifier from input directory name
    identifier = input_dir.name

    # Parse channel and cycle options with mode-specific defaults
    if channels:
        channel_list = parse_channels(channels)
    elif pipeline_type == "illum_painting":
        channel_list = ["DNA", "Phalloidin", "CHN2"]  # Default for illum_painting
    elif pipeline_type == "illum_barcoding":
        channel_list = ["DNA", "A", "C", "G", "T"]  # Default for illum_barcoding
    else:
        channel_list = None  # No defaults for generic mode

    # Parse cycles with defaults for illum_barcoding
    if cycles:
        cycle_list = parse_cycles(cycles)
    elif pipeline_type == "illum_barcoding":
        cycle_list = [1, 2, 3]  # Default cycles for illum_barcoding
    else:
        cycle_list = None

    # Warn if cycles specified for non-barcoding pipeline
    if pipeline_type in ["illum_painting", "generic"] and cycles:
        logger.warning(f"Cycles option is ignored for {pipeline_type} pipeline type")
        cycle_list = None

    # Set default pattern based on pipeline type if not specified
    if pattern is None:
        if pipeline_type in ["illum_painting", "illum_barcoding"]:
            pattern = "*.npy"
        else:  # generic
            pattern = "*.png"

    # Determine whether to apply sqrt transform
    apply_sqrt = not no_sqrt and pipeline_type != "generic"

    # Create output directory if needed
    output_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Processing in {pipeline_type} mode")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Identifier: {identifier}")

    # Load image data
    image_data = load_image_files(
        input_dir,
        identifier,
        pipeline_type,
        channel_list,
        cycle_list,
        file_pattern=pattern,
    )

    if not image_data:
        logger.error(f"No image files found for {identifier} in {input_dir}")
        raise typer.Exit(code=1)

    logger.info(f"Found {len(image_data)} image(s)")

    # Create appropriate montage
    if pipeline_type == "illum_painting":
        create_simple_montage(
            image_data,
            output_file,
            identifier,
            apply_sqrt=apply_sqrt,
            title_suffix="Illumination Correction Functions (Cell Painting)",
        )
    elif pipeline_type == "generic":
        create_simple_montage(
            image_data,
            output_file,
            identifier,
            apply_sqrt=apply_sqrt,
            title_suffix="Image Montage",
        )
    else:  # illum_barcoding
        create_barcoding_montage(
            image_data, output_file, identifier, apply_sqrt=apply_sqrt
        )

    logger.success("QC montage generation complete")


if __name__ == "__main__":
    app()
