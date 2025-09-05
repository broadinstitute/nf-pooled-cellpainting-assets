#!/usr/bin/env -S pixi exec --spec python>=3.11 --spec loguru --spec typer --spec numpy --spec matplotlib --spec scikit-image -- python
"""
qc_stitch_visual.py - Visualize stitched images for quality control

Purpose: Create visual montages of stitched image quadrants to verify
         proper stitching and alignment between Cell Painting and barcoding images.

Usage:
    ./qc_stitch_visual.py /path/to/stitched_10X output.png painting Plate1
    ./qc_stitch_visual.py /path/to/stitched_10X output_dir barcoding Plate1 --well A1
    ./qc_stitch_visual.py --help
"""

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import matplotlib.pyplot as plt
import skimage.io
import typer
from loguru import logger
from typing_extensions import Annotated

# Configure logger
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}</cyan> - <level>{message}</level>",
)

app = typer.Typer(help="Create QC visualization of stitched images")


def load_stitched_images(
    well_dir: Path, pipeline_type: str, channel: Optional[str] = None
) -> dict:
    """
    Load stitched images from a well directory (single image or quadrants)

    Args:
        well_dir: Directory containing stitched images
        pipeline_type: 'painting' or 'barcoding'
        channel: Specific channel to load (for barcoding, e.g., 'Cycle01_DAPI')

    Returns:
        Dictionary mapping image/quadrant names to image arrays
    """
    images = {}
    quadrant_names = ["TopLeft", "TopRight", "BottomLeft", "BottomRight"]

    # List all image files in the directory
    image_files = list(well_dir.glob("*.tif*"))

    # Check if we have quadrant files or single stitched file
    has_quadrants = any(
        any(qname in f.name for qname in quadrant_names) for f in image_files
    )

    if has_quadrants:
        # Load actual quadrant files
        logger.info("Found quadrant files")

        if pipeline_type == "painting":
            # Pattern: StitchedTopLeft_CorrDNA.tiff
            for qname in quadrant_names:
                for img_file in image_files:
                    fname = img_file.name
                    if qname in fname and ("DNA" in fname or "DAPI" in fname):
                        try:
                            images[qname] = skimage.io.imread(img_file)
                            logger.debug(f"Loaded {qname} from {fname}")
                            break
                        except Exception as e:
                            logger.warning(f"Could not load {img_file}: {e}")

        elif pipeline_type == "barcoding":
            # Pattern: StitchedTopLeft_Cycle01_DAPI.tiff
            target_channel = channel or "Cycle01_DAPI"

            for qname in quadrant_names:
                for img_file in image_files:
                    fname = img_file.name
                    if qname in fname and target_channel in fname:
                        try:
                            images[qname] = skimage.io.imread(img_file)
                            logger.debug(f"Loaded {qname} from {fname}")
                            break
                        except Exception as e:
                            logger.warning(f"Could not load {img_file}: {e}")

    else:
        # Handle single stitched file - create synthetic quadrants
        logger.info("No quadrant files found, looking for single stitched file")

        if pipeline_type == "painting":
            # Look for DNA/DAPI channel in single stitched file
            # Pattern: Stitched_CorrDNA.tiff
            for img_file in image_files:
                fname = img_file.name
                if "Stitched" in fname and ("DNA" in fname or "DAPI" in fname):
                    try:
                        full_image = skimage.io.imread(img_file)
                        logger.info(
                            f"Loaded full stitched image from {fname}, shape: {full_image.shape}"
                        )

                        # Split into quadrants
                        h, w = full_image.shape
                        mid_h, mid_w = h // 2, w // 2

                        images["TopLeft"] = full_image[:mid_h, :mid_w]
                        images["TopRight"] = full_image[:mid_h, mid_w:]
                        images["BottomLeft"] = full_image[mid_h:, :mid_w]
                        images["BottomRight"] = full_image[mid_h:, mid_w:]

                        logger.debug("Created synthetic quadrants from full image")
                        break
                    except Exception as e:
                        logger.warning(f"Could not load {img_file}: {e}")

        elif pipeline_type == "barcoding":
            # Look for specific cycle/channel in single stitched file
            target_channel = channel or "Cycle01_DAPI"

            for img_file in image_files:
                fname = img_file.name
                if "Stitched" in fname and target_channel in fname:
                    try:
                        full_image = skimage.io.imread(img_file)
                        logger.info(
                            f"Loaded full stitched image from {fname}, shape: {full_image.shape}"
                        )

                        # Split into quadrants
                        h, w = full_image.shape
                        mid_h, mid_w = h // 2, w // 2

                        images["TopLeft"] = full_image[:mid_h, :mid_w]
                        images["TopRight"] = full_image[:mid_h, mid_w:]
                        images["BottomLeft"] = full_image[mid_h:, :mid_w]
                        images["BottomRight"] = full_image[mid_h:, mid_w:]

                        logger.debug("Created synthetic quadrants from full image")
                        break
                    except Exception as e:
                        logger.warning(f"Could not load {img_file}: {e}")

    return images


def create_quadrant_visualization(
    quadrants: dict, well_name: str, pipeline_type: str
) -> plt.Figure:
    """
    Create 2x2 grid visualization of stitched quadrants

    Args:
        quadrants: Dictionary mapping quadrant names to image arrays
        well_name: Name of the well for title
        pipeline_type: Type of pipeline for title

    Returns:
        Matplotlib figure object
    """
    fig, axs = plt.subplots(nrows=2, ncols=2, figsize=(10, 10))

    # Position mapping for quadrants
    position_map = {
        "TopLeft": (0, 0),
        "TopRight": (0, 1),
        "BottomLeft": (1, 0),
        "BottomRight": (1, 1),
    }

    for qname, (row, col) in position_map.items():
        ax = axs[row, col]

        if qname in quadrants:
            # Apply sqrt transformation for better contrast
            img = quadrants[qname]
            img_transformed = np.sqrt(np.clip(img, 0, None))

            # Display image
            ax.imshow(img_transformed, cmap="gray", interpolation="nearest")
            ax.set_title(qname, fontsize=10)
            logger.debug(f"Added {qname} to visualization (shape: {img.shape})")
        else:
            # Show placeholder for missing quadrant
            ax.text(
                0.5,
                0.5,
                f"No {qname} data",
                ha="center",
                va="center",
                transform=ax.transAxes,
                fontsize=12,
            )
            ax.set_title(qname, fontsize=10)

        # Remove axis ticks for cleaner look
        ax.set_xticks([])
        ax.set_yticks([])

    # Add overall title
    pipeline_label = "Cell Painting" if pipeline_type == "painting" else "Barcoding"
    fig.suptitle(
        f"Stitched Image QC - {well_name} ({pipeline_label})",
        fontsize=14,
        fontweight="bold",
    )

    plt.tight_layout()
    return fig


def process_single_well(
    well_dir: Path, output_file: Path, pipeline_type: str, channel: Optional[str] = None
) -> None:
    """
    Process and visualize a single well's stitched images
    """
    well_name = well_dir.name
    logger.info(f"Processing well: {well_name}")

    # Load stitched images (quadrants or single image split into quadrants)
    quadrants = load_stitched_images(well_dir, pipeline_type, channel)

    if not quadrants:
        logger.error(f"No quadrant images found for {well_name}")
        return

    logger.info(f"Loaded {len(quadrants)} quadrants for {well_name}")

    # Create visualization
    fig = create_quadrant_visualization(quadrants, well_name, pipeline_type)

    # Save figure
    fig.savefig(output_file, dpi=150, bbox_inches="tight")
    logger.success(f"Saved visualization to: {output_file}")
    plt.close(fig)


def process_multiple_wells(
    input_dir: Path,
    output_dir: Path,
    pipeline_type: str,
    plate: str,
    channel: Optional[str] = None,
    max_wells: int = 10,
) -> None:
    """
    Process multiple wells and create individual visualizations
    """
    # Find well directories
    well_dirs = [d for d in input_dir.iterdir() if d.is_dir()]

    if not well_dirs:
        logger.error(f"No well directories found in {input_dir}")
        return

    # Limit number of wells to process
    if len(well_dirs) > max_wells:
        logger.warning(f"Found {len(well_dirs)} wells, processing first {max_wells}")
        well_dirs = well_dirs[:max_wells]

    logger.info(f"Processing {len(well_dirs)} wells from {plate}")

    for well_dir in well_dirs:
        well_name = well_dir.name
        output_file = output_dir / f"{well_name}_stitch_qc.png"

        try:
            process_single_well(well_dir, output_file, pipeline_type, channel)
        except Exception as e:
            logger.error(f"Failed to process {well_name}: {e}")
            continue


@app.command()
def main(
    input_dir: Annotated[
        Path, typer.Argument(help="Directory containing stitched 10X images")
    ],
    output_path: Annotated[
        Path, typer.Argument(help="Output file (PNG) or directory for multiple files")
    ],
    pipeline_type: Annotated[
        str, typer.Argument(help="Pipeline type: 'painting' or 'barcoding'")
    ],
    plate: Annotated[str, typer.Argument(help="Plate identifier (e.g., Plate1)")],
    well: Annotated[
        Optional[str],
        typer.Option("--well", "-w", help="Specific well to process (e.g., A1)"),
    ] = None,
    channel: Annotated[
        Optional[str],
        typer.Option(
            "--channel", "-c", help="Channel for barcoding (e.g., 'Cycle01_DAPI')"
        ),
    ] = None,
    max_wells: Annotated[
        int, typer.Option("--max-wells", help="Maximum number of wells to process")
    ] = 10,
    verbose: Annotated[
        bool, typer.Option("--verbose", "-v", help="Enable verbose logging")
    ] = False,
) -> None:
    """
    Create QC visualization of stitched images to verify proper alignment.

    This tool creates 2x2 grid visualizations showing the four quadrants
    of stitched whole-well images, helping identify stitching artifacts
    or misalignments.

    Examples:
        # Visualize single well for Cell Painting
        ./qc_stitch_visual.py data/stitched_10X/Plate1-A1 output.png painting Plate1

        # Process multiple wells for barcoding
        ./qc_stitch_visual.py data/stitched_10X output_dir barcoding Plate1

        # Specific cycle for barcoding
        ./qc_stitch_visual.py data/stitched_10X output.png barcoding Plate1 --channel Cycle02_DAPI
    """

    # Adjust logging level based on verbose flag
    if verbose:
        logger.remove()
        logger.add(
            sys.stderr,
            level="DEBUG",
            format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{function}</cyan> - <level>{message}</level>",
        )

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

    logger.info(f"Processing {pipeline_type} stitched images")
    logger.info(f"Input directory: {input_dir}")
    logger.info(f"Plate: {plate}")

    # Determine if processing single well or multiple
    if well:
        # Process single well
        well_dir = input_dir / f"{plate}-{well}"
        if not well_dir.exists():
            # Try alternative naming convention
            well_dir = input_dir / f"{plate}_{well}"
            if not well_dir.exists():
                logger.error(
                    f"Well directory not found: {plate}-{well} or {plate}_{well}"
                )
                raise typer.Exit(code=1)

        # Ensure output is a file
        if output_path.suffix not in [".png", ".pdf", ".jpg"]:
            output_file = output_path / f"{plate}_{well}_stitch_qc.png"
        else:
            output_file = output_path

        output_file.parent.mkdir(parents=True, exist_ok=True)
        process_single_well(well_dir, output_file, pipeline_type, channel)

    else:
        # Process multiple wells
        if output_path.suffix in [".png", ".pdf", ".jpg"]:
            # If output looks like a file, use its parent as output directory
            output_dir = output_path.parent
            logger.warning(
                f"Output appears to be a file, using directory: {output_dir}"
            )
        else:
            output_dir = output_path

        output_dir.mkdir(parents=True, exist_ok=True)
        process_multiple_wells(
            input_dir, output_dir, pipeline_type, plate, channel, max_wells
        )

    logger.success("Stitching QC visualization complete")


if __name__ == "__main__":
    app()
