#!/usr/bin/env -S pixi exec --spec python>=3.11 --spec loguru --spec typer --spec numpy --spec matplotlib -- python
"""
qc_illum_montage.py - Create visual montage of illumination correction functions

Purpose: Visualize illumination correction functions from CellProfiler pipelines
         to verify they appear "vaguely circular and vaguely smooth" as expected.

Usage:
    pixi exec --spec python>=3.11 --spec loguru --spec typer --spec numpy --spec matplotlib -- python qc_illum_montage.py /path/to/illum montage.png painting Plate1
    ./qc_illum_montage.py /path/to/illum montage.png painting Plate1
    ./qc_illum_montage.py --help
"""

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


def load_illumination_files(
    input_dir: Path,
    plate: str,
    pipeline_type: str,
    channels: Optional[List[str]] = None,
    cycles: Optional[List[int]] = None,
) -> Dict:
    """
    Load illumination correction .npy files based on pipeline type

    Args:
        input_dir: Directory containing illumination .npy files
        plate: Plate identifier (e.g., 'Plate1')
        pipeline_type: 'painting' or 'barcoding'
        channels: List of channels to process (defaults based on pipeline type)
        cycles: List of cycles to process (for barcoding only)

    Returns:
        Dictionary with structure:
            - For painting: {channel: array}
            - For barcoding: {(cycle, channel): array}
    """
    illum_data = {}

    if pipeline_type == "painting":
        # Cell Painting pattern: {Plate}_Illum{Channel}.npy
        if channels is None:
            channels = ["DNA", "Phalloidin", "CHN2"]  # Default channels

        logger.info(f"Processing channels: {', '.join(channels)}")

        for channel in channels:
            file_pattern = f"{plate}_Illum{channel}.npy"
            file_path = input_dir / file_pattern

            if file_path.exists():
                try:
                    illum_data[channel] = np.load(file_path)
                    logger.success(f"Loaded: {file_path.name}")
                except Exception as e:
                    logger.warning(f"Could not load {file_path.name}: {e}")
            else:
                logger.debug(f"File not found: {file_path.name}")

    elif pipeline_type == "barcoding":
        # Barcoding pattern: {Plate}_Cycle{N}_Illum{Channel}.npy
        if channels is None:
            channels = ["DNA", "A", "C", "G", "T"]  # Default channels
        if cycles is None:
            cycles = [1, 2, 3]  # Default cycles

        logger.info(f"Processing cycles: {cycles}")
        logger.info(f"Processing channels: {', '.join(channels)}")

        for cycle in cycles:
            for channel in channels:
                file_pattern = f"{plate}_Cycle{cycle}_Illum{channel}.npy"
                file_path = input_dir / file_pattern

                if file_path.exists():
                    try:
                        illum_data[(cycle, channel)] = np.load(file_path)
                        logger.success(f"Loaded: {file_path.name}")
                    except Exception as e:
                        logger.warning(f"Could not load {file_path.name}: {e}")
                else:
                    logger.debug(f"File not found: {file_path.name}")

    return illum_data


def apply_visualization_transform(array: np.ndarray) -> np.ndarray:
    """
    Apply transformations to make illumination patterns more visible

    Args:
        array: 2D numpy array of illumination values

    Returns:
        Transformed array suitable for visualization
    """
    # Apply sqrt for better contrast (as mentioned in meeting)
    # Handle potential negative values or zeros
    array_positive = np.clip(array, 0, None)

    # Apply square root transformation
    transformed = np.sqrt(array_positive)

    # Normalize to 0-1 range for display
    if transformed.max() > transformed.min():
        transformed = (transformed - transformed.min()) / (
            transformed.max() - transformed.min()
        )

    return transformed


def create_painting_montage(
    illum_data: Dict[str, np.ndarray], output_file: Path, plate: str
) -> None:
    """
    Create montage for Cell Painting illumination functions

    Args:
        illum_data: Dictionary {channel: array}
        output_file: Path to save montage
        plate: Plate identifier for title
    """
    n_channels = len(illum_data)
    if n_channels == 0:
        logger.error("No illumination data to visualize")
        return

    logger.info(f"Creating montage with {n_channels} channel(s)")

    # Create figure with subplots
    fig, axes = plt.subplots(1, n_channels, figsize=(5 * n_channels, 5))

    # Handle single channel case
    if n_channels == 1:
        axes = [axes]

    # Sort channels for consistent ordering
    channels = sorted(illum_data.keys())

    for idx, channel in enumerate(channels):
        array = illum_data[channel]
        transformed = apply_visualization_transform(array)

        # Display with grayscale colormap
        im = axes[idx].imshow(transformed, cmap="gray", interpolation="nearest")
        axes[idx].set_title(f"{channel}", fontsize=12)
        axes[idx].axis("off")

        # Add colorbar for reference
        plt.colorbar(im, ax=axes[idx], fraction=0.046, pad=0.04)

        logger.debug(f"Added {channel} to montage (shape: {array.shape})")

    # Add overall title
    fig.suptitle(
        f"Illumination Correction Functions - {plate} (Cell Painting)",
        fontsize=14,
        fontweight="bold",
    )

    # Save figure
    plt.tight_layout()
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    logger.success(f"Saved montage to: {output_file}")
    plt.close()


def create_barcoding_montage(
    illum_data: Dict[Tuple[int, str], np.ndarray], output_file: Path, plate: str
) -> None:
    """
    Create montage for Barcoding illumination functions (cycles x channels grid)

    Args:
        illum_data: Dictionary {(cycle, channel): array}
        output_file: Path to save montage
        plate: Plate identifier for title
    """
    if len(illum_data) == 0:
        logger.error("No illumination data to visualize")
        return

    # Extract unique cycles and channels
    cycles = sorted(set(key[0] for key in illum_data.keys()))
    channels = sorted(set(key[1] for key in illum_data.keys()))

    n_cycles = len(cycles)
    n_channels = len(channels)

    logger.info(f"Creating montage grid: {n_cycles} cycles x {n_channels} channels")

    # Create grid layout
    fig = plt.figure(figsize=(4 * n_channels, 4 * n_cycles))
    gs = gridspec.GridSpec(n_cycles, n_channels, figure=fig)

    for cycle_idx, cycle in enumerate(cycles):
        for channel_idx, channel in enumerate(channels):
            key = (cycle, channel)

            if key in illum_data:
                ax = fig.add_subplot(gs[cycle_idx, channel_idx])

                array = illum_data[key]
                transformed = apply_visualization_transform(array)

                # Display with grayscale colormap
                _ = ax.imshow(transformed, cmap="gray", interpolation="nearest")
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
        f"Illumination Correction Functions - {plate} (Barcoding)",
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
    input_dir: Annotated[
        Path, typer.Argument(help="Directory containing illumination .npy files")
    ],
    output_file: Annotated[
        Path, typer.Argument(help="Output file path for montage (PNG or PDF)")
    ],
    pipeline_type: Annotated[
        str, typer.Argument(help="Pipeline type: 'painting' or 'barcoding'")
    ],
    plate: Annotated[str, typer.Argument(help="Plate identifier (e.g., Plate1)")],
    channels: Annotated[
        Optional[str],
        typer.Option(
            "--channels",
            "-c",
            help="Comma-separated list of channels (e.g., 'DNA,Phalloidin,CHN2' for painting or 'DNA,A,C,G,T' for barcoding)",
        ),
    ] = None,
    cycles: Annotated[
        Optional[str],
        typer.Option(
            "--cycles",
            help="Comma-separated list of cycles or ranges for barcoding (e.g., '1,2,3' or '1-3,5')",
        ),
    ] = None,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose logging")
    ] = False,
) -> None:
    """
    Create montage of illumination correction functions for QC purposes.

    The montage helps verify that illumination correction functions appear
    "vaguely circular and vaguely smooth" as expected for proper correction.

    Examples:
        # Default channels for painting
        ./qc_illum_montage.py data/illum output.png painting Plate1

        # Custom channels for painting
        ./qc_illum_montage.py data/illum output.png painting Plate1 --channels DNA,Phalloidin

        # Custom cycles and channels for barcoding
        ./qc_illum_montage.py data/illum output.png barcoding Plate1 --cycles 1-3 --channels DNA,A,C
    """

    # Enable debug logging if verbose
    if verbose:
        logger.remove()
        logger.add(sys.stderr, level="DEBUG")

    # Validate pipeline type
    if pipeline_type not in ["painting", "barcoding"]:
        logger.error(
            f"Invalid pipeline type: {pipeline_type}. Must be 'painting' or 'barcoding'"
        )
        raise typer.Exit(code=1)

    # Validate input directory
    if not input_dir.exists():
        logger.error(f"Input directory does not exist: {input_dir}")
        raise typer.Exit(code=1)

    # Parse channel and cycle options
    channel_list = parse_channels(channels) if channels else None
    cycle_list = parse_cycles(cycles) if cycles else None

    # Warn if cycles specified for painting pipeline
    if pipeline_type == "painting" and cycles:
        logger.warning("Cycles option is ignored for painting pipeline type")
        cycle_list = None

    # Create output directory if needed
    output_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Processing {pipeline_type} illumination files")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Plate: {plate}")

    # Load illumination data
    illum_data = load_illumination_files(
        input_dir, plate, pipeline_type, channel_list, cycle_list
    )

    if not illum_data:
        logger.error(f"No illumination files found for {plate} in {input_dir}")
        raise typer.Exit(code=1)

    logger.info(f"Found {len(illum_data)} illumination function(s)")

    # Create appropriate montage
    if pipeline_type == "painting":
        create_painting_montage(illum_data, output_file, plate)
    else:
        create_barcoding_montage(illum_data, output_file, plate)

    logger.success("QC montage generation complete")


if __name__ == "__main__":
    app()
