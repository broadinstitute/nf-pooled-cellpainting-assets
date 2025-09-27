#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "pandas",
#   "pydantic>=2.0",
# ]
# ///
"""
LoadData CSV generator v2 - Specification-driven generation.

This version uses a JSON specification to define how LoadData CSVs are generated,
making the process more maintainable and extensible.

Usage:
  uv run scripts/load_data_generate_v2.py <samplesheet.csv> <spec.json> [options]

Example:
  uv run scripts/load_data_generate_v2.py \\
    data/Source1/workspace/samplesheets/samplesheet1.csv \\
    pcpip-loaddata-spec.json \\
    --output-dir data/Source1/workspace/load_data_csv
"""

import argparse
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from load_data_models import LoadDataSpec, ColumnDefinition


class LoadDataGenerator:
    """Generate LoadData CSVs from specification."""

    def __init__(self, spec: LoadDataSpec):
        self.spec = spec

    def generate_column_value(
        self, col_def: ColumnDefinition, row: pd.Series, template_vars: Dict[str, Any]
    ) -> Any:
        """Generate value for a single column based on its definition."""
        if col_def.source:
            # Direct field from samplesheet or template vars
            # First check row, then template_vars
            if col_def.source in row:
                return row[col_def.source]
            elif col_def.source in template_vars:
                return template_vars[col_def.source]
            else:
                return ""

        elif col_def.pattern:
            # Template pattern - substitute variables
            value = col_def.pattern
            for key, val in template_vars.items():
                # Handle formatted placeholders first
                formatted_placeholder = f"{{{key}:02d}}"
                if formatted_placeholder in value:
                    value = value.replace(formatted_placeholder, f"{int(val):02d}")
                # Then handle simple placeholders
                simple_placeholder = f"{{{key}}}"
                if simple_placeholder in value:
                    value = value.replace(simple_placeholder, str(val))
            return value

        elif col_def.value is not None:
            # Special value or fixed value
            if col_def.value == "channel_index":
                return template_vars.get("channel_index", 0)
            elif col_def.value == "tile":
                return template_vars.get("tile", 1)
            else:
                return col_def.value

        elif col_def.expression:
            # Python expression - evaluate with available variables
            local_vars = {**row.to_dict(), **template_vars}
            try:
                return eval(col_def.expression, {"ord": ord, "int": int}, local_vars)
            except Exception as e:
                print(f"Error evaluating expression '{col_def.expression}': {e}")
                return ""

        return ""

    def expand_column_name(self, name: str, template_vars: Dict[str, Any]) -> str:
        """Expand template variables in column name."""
        result = name
        for key, val in template_vars.items():
            # Handle formatted placeholders first
            formatted_placeholder = f"{{{key}:02d}}"
            if formatted_placeholder in result:
                result = result.replace(formatted_placeholder, f"{int(val):02d}")
            # Then handle simple placeholders
            simple_placeholder = f"{{{key}}}"
            if simple_placeholder in result:
                result = result.replace(simple_placeholder, str(val))
        return result

    def generate_pipeline(
        self,
        pipeline_id: str,
        samplesheet_df: pd.DataFrame,
        base_path: Optional[str] = None,
    ) -> pd.DataFrame:
        """Generate LoadData CSV for a specific pipeline."""
        pipeline = self.spec.get_pipeline(pipeline_id)
        base_path = base_path or self.spec.metadata.base_path

        # Filter samplesheet
        filtered_df = (
            samplesheet_df.query(pipeline.filter) if pipeline.filter else samplesheet_df
        )

        # Prepare for generation
        rows = []

        if pipeline.wide_format and pipeline_id in ["6", "7"]:
            # Special handling for wide format pipelines (6, 7)
            self._generate_wide_format(pipeline, filtered_df, base_path, rows)
        elif pipeline_id == "9":
            # Special handling for pipeline 9 with synthetic tiles
            self._generate_pipeline_9(pipeline, filtered_df, base_path, rows)
        else:
            # Standard pipeline generation
            self._generate_standard(pipeline, filtered_df, base_path, rows)

        return pd.DataFrame(rows)

    def _generate_standard(self, pipeline, filtered_df, base_path, rows):
        """Generate standard (non-wide) format LoadData."""
        for _, row in filtered_df.iterrows():
            # Extract acquisition folder and filename from path
            if "path" in row and row["path"]:
                # Handle paths that might have prefixes like "pcpip/data/Source1/..."
                path_obj = Path(row["path"])
                # Find the actual image file name and its parent
                filename = path_obj.name
                # Get parent folder name (acquisition folder)
                acquisition_folder = path_obj.parent.name
            else:
                filename = ""
                acquisition_folder = ""

            template_vars = {
                "base_path": base_path,
                "plate": row.get("plate", ""),
                "well": row.get("well", ""),
                "site": row.get("site", ""),
                "cycle": row.get("cycle", ""),
                "acquisition_folder": acquisition_folder,
                "filename": filename,
            }

            # Generate metadata columns
            data = {}
            for col_def in pipeline.columns.metadata:
                col_name = self.expand_column_name(col_def.name, template_vars)
                data[col_name] = self.generate_column_value(col_def, row, template_vars)

            # Generate per-channel columns (handle separated or combined)
            if pipeline.columns.per_channel_orig and pipeline.columns.per_channel_illum:
                # Separated Orig and Illum columns
                channels = self.spec.get_channels(
                    pipeline.columns.per_channel_orig.channels
                )
                # Get the actual channel order from the samplesheet row
                if "channels" in row:
                    samplesheet_channels = row["channels"].split(",")
                else:
                    samplesheet_channels = channels

                # Generate Orig columns first
                for channel in channels:
                    # Find index in the original samplesheet channel list
                    try:
                        channel_index = samplesheet_channels.index(channel)
                    except ValueError:
                        channel_index = channels.index(channel)

                    channel_vars = {
                        **template_vars,
                        "channel": channel,
                        "channel_index": channel_index,
                    }
                    for col_def in pipeline.columns.per_channel_orig.columns:
                        col_name = self.expand_column_name(col_def.name, channel_vars)
                        data[col_name] = self.generate_column_value(
                            col_def, row, channel_vars
                        )

                # Generate Illum columns
                for channel in channels:
                    channel_vars = {
                        **template_vars,
                        "channel": channel,
                        "channel_index": 0,
                    }
                    for col_def in pipeline.columns.per_channel_illum.columns:
                        col_name = self.expand_column_name(col_def.name, channel_vars)
                        data[col_name] = self.generate_column_value(
                            col_def, row, channel_vars
                        )

            elif pipeline.columns.per_channel:
                # Combined columns (old style)
                channels = self.spec.get_channels(pipeline.columns.per_channel.channels)
                # Get the actual channel order from the samplesheet row
                if "channels" in row:
                    samplesheet_channels = row["channels"].split(",")
                else:
                    samplesheet_channels = channels

                for channel in channels:
                    # Find index in the original samplesheet channel list
                    try:
                        channel_index = samplesheet_channels.index(channel)
                    except ValueError:
                        channel_index = channels.index(channel)

                    channel_vars = {
                        **template_vars,
                        "channel": channel,
                        "channel_index": channel_index,
                    }
                    for col_def in pipeline.columns.per_channel.columns:
                        col_name = self.expand_column_name(col_def.name, channel_vars)
                        data[col_name] = self.generate_column_value(
                            col_def, row, channel_vars
                        )

            rows.append(data)

    def _generate_wide_format(self, pipeline, filtered_df, base_path, rows):
        """Generate wide format LoadData for pipelines 6 and 7."""
        # Group by well and site
        for (well, site), group in filtered_df.groupby(["well", "site"]):
            plate = group.iloc[0]["plate"]
            cycles = sorted(group["cycle"].unique())

            template_vars = {
                "base_path": base_path,
                "plate": plate,
                "well": well,
                "site": site,
            }

            # Generate metadata columns
            data = {}
            for col_def in pipeline.columns.metadata:
                col_name = self.expand_column_name(col_def.name, template_vars)
                data[col_name] = self.generate_column_value(
                    col_def, group.iloc[0], template_vars
                )

            # Handle separated Orig and Illum columns for pipeline 6
            if (
                pipeline.columns.per_cycle_per_channel_orig
                and pipeline.columns.per_cycle_per_channel_illum
            ):
                # First generate all Orig columns
                channels = self.spec.get_channels(
                    pipeline.columns.per_cycle_per_channel_orig.channels
                )

                for cycle in cycles:
                    cycle_row = group[group["cycle"] == cycle].iloc[0]
                    cycle_vars = {
                        **template_vars,
                        "cycle": cycle,
                        "acquisition_folder": Path(cycle_row["path"]).parent.name,
                        "filename": Path(cycle_row["path"]).name,
                    }

                    # Get the actual channel order from the samplesheet row
                    if "channels" in cycle_row:
                        samplesheet_channels = cycle_row["channels"].split(",")
                    else:
                        samplesheet_channels = channels

                    for channel in channels:
                        # Find index in the original samplesheet channel list
                        try:
                            channel_index = samplesheet_channels.index(channel)
                        except ValueError:
                            channel_index = channels.index(channel)

                        channel_vars = {
                            **cycle_vars,
                            "channel": channel,
                            "channel_index": channel_index,
                        }

                        for (
                            col_def
                        ) in pipeline.columns.per_cycle_per_channel_orig.columns:
                            col_name = self.expand_column_name(
                                col_def.name, channel_vars
                            )
                            data[col_name] = self.generate_column_value(
                                col_def, cycle_row, channel_vars
                            )

                # Then generate all Illum columns
                for cycle in cycles:
                    cycle_row = group[group["cycle"] == cycle].iloc[0]
                    cycle_vars = {
                        **template_vars,
                        "cycle": cycle,
                        "acquisition_folder": Path(cycle_row["path"]).parent.name,
                        "filename": Path(cycle_row["path"]).name,
                    }

                    for channel in channels:
                        channel_vars = {
                            **cycle_vars,
                            "channel": channel,
                            "channel_index": 0,  # Illum files don't use frame index
                        }

                        for (
                            col_def
                        ) in pipeline.columns.per_cycle_per_channel_illum.columns:
                            col_name = self.expand_column_name(
                                col_def.name, channel_vars
                            )
                            data[col_name] = self.generate_column_value(
                                col_def, cycle_row, channel_vars
                            )

            # Handle old-style interleaved columns (if still used)
            elif pipeline.columns.per_cycle_per_channel:
                channels = self.spec.get_channels(
                    pipeline.columns.per_cycle_per_channel.channels
                )

                for cycle in cycles:
                    cycle_row = group[group["cycle"] == cycle].iloc[0]
                    cycle_vars = {
                        **template_vars,
                        "cycle": cycle,
                        "acquisition_folder": Path(cycle_row["path"]).parent.name,
                        "filename": Path(cycle_row["path"]).name,
                    }

                    # Get the actual channel order from the samplesheet row
                    if "channels" in cycle_row:
                        samplesheet_channels = cycle_row["channels"].split(",")
                    else:
                        samplesheet_channels = channels

                    for channel in channels:
                        # Check special rules
                        special_rules = (
                            pipeline.columns.per_cycle_per_channel.special_rules or {}
                        )
                        if channel in special_rules:
                            rule = special_rules[channel]
                            if "only_cycle" in rule and cycle != rule["only_cycle"]:
                                continue

                        # Find index in the original samplesheet channel list
                        try:
                            channel_index = samplesheet_channels.index(channel)
                        except ValueError:
                            channel_index = channels.index(channel)

                        channel_vars = {
                            **cycle_vars,
                            "channel": channel,
                            "channel_index": channel_index,
                        }

                        for col_def in pipeline.columns.per_cycle_per_channel.columns:
                            col_name = self.expand_column_name(
                                col_def.name, channel_vars
                            )
                            data[col_name] = self.generate_column_value(
                                col_def, cycle_row, channel_vars
                            )

            rows.append(data)

    def _generate_pipeline_9(self, pipeline, filtered_df, base_path, rows):
        """Generate LoadData for pipeline 9 with synthetic tiles."""
        tiles_per_well = pipeline.tiles_per_well or 4

        for well in filtered_df["well"].unique():
            plate = filtered_df.iloc[0]["plate"]

            for tile in range(1, tiles_per_well + 1):
                template_vars = {
                    "base_path": base_path,
                    "plate": plate,
                    "well": well,
                    "tile": tile,
                }

                # Generate metadata columns
                data = {}
                for col_def in pipeline.columns.metadata:
                    col_name = self.expand_column_name(col_def.name, template_vars)
                    # Handle tile as site for pipeline 9
                    if col_def.source == "tile":
                        data[col_name] = tile
                    else:
                        data[col_name] = self.generate_column_value(
                            col_def, filtered_df.iloc[0], template_vars
                        )

                # Generate barcoding channels
                if pipeline.columns.barcoding_channels:
                    for cycle in pipeline.columns.barcoding_channels.cycles:
                        for channel in pipeline.columns.barcoding_channels.channels:
                            channel_vars = {
                                **template_vars,
                                "cycle": cycle,
                                "channel": channel,
                            }
                            for col_def in pipeline.columns.barcoding_channels.columns:
                                col_name = self.expand_column_name(
                                    col_def.name, channel_vars
                                )
                                data[col_name] = self.generate_column_value(
                                    col_def, filtered_df.iloc[0], channel_vars
                                )

                # Generate barcoding DNA
                if pipeline.columns.barcoding_dna:
                    for cycle in pipeline.columns.barcoding_dna.cycles:
                        channel_vars = {
                            **template_vars,
                            "cycle": cycle,
                            "channel": "DNA",
                        }
                        for col_def in pipeline.columns.barcoding_dna.columns:
                            col_name = self.expand_column_name(
                                col_def.name, channel_vars
                            )
                            data[col_name] = self.generate_column_value(
                                col_def, filtered_df.iloc[0], channel_vars
                            )

                # Generate painting channels
                if pipeline.columns.painting_channels:
                    for channel in pipeline.columns.painting_channels.channels:
                        channel_vars = {**template_vars, "channel": channel}
                        for col_def in pipeline.columns.painting_channels.columns:
                            col_name = self.expand_column_name(
                                col_def.name, channel_vars
                            )
                            data[col_name] = self.generate_column_value(
                                col_def, filtered_df.iloc[0], channel_vars
                            )

                rows.append(data)


def main():
    parser = argparse.ArgumentParser(
        description="Generate LoadData CSVs from specification"
    )
    parser.add_argument("samplesheet", help="Path to samplesheet CSV")
    parser.add_argument("spec", help="Path to JSON specification")
    parser.add_argument("--output-dir", help="Output directory for LoadData CSVs")
    parser.add_argument("--pipeline", help="Generate only specific pipeline (1-9)")
    parser.add_argument("--base-path", help="Override base path from spec")
    parser.add_argument(
        "--validate", action="store_true", help="Validate against reference CSVs"
    )

    args = parser.parse_args()

    # Load specification
    from load_data_models import load_spec

    spec = load_spec(args.spec)

    # Load samplesheet
    samplesheet_df = pd.read_csv(args.samplesheet)

    # Initialize generator
    generator = LoadDataGenerator(spec)

    # Determine which pipelines to generate
    if args.pipeline:
        pipeline_ids = [args.pipeline]
    else:
        # Skip pipelines 4 and 8 (FIJI)
        pipeline_ids = [p for p in spec.pipelines.keys() if p not in ["4", "8"]]

    # Generate LoadData CSVs
    for pipeline_id in pipeline_ids:
        print(f"Generating pipeline {pipeline_id}...")

        try:
            df = generator.generate_pipeline(
                pipeline_id, samplesheet_df, args.base_path
            )

            if args.output_dir:
                # Determine output path
                batch = (
                    samplesheet_df.iloc[0]["batch"]
                    if "batch" in samplesheet_df.columns
                    else "Batch1"
                )
                plate = (
                    samplesheet_df.iloc[0]["plate"]
                    if "plate" in samplesheet_df.columns
                    else "Plate1"
                )
                output_path = (
                    Path(args.output_dir)
                    / batch
                    / f"{plate}_trimmed"
                    / f"load_data_pipeline{pipeline_id}_generated.csv"
                )
                output_path.parent.mkdir(parents=True, exist_ok=True)

                # Reorder columns to match expected order
                # Group by prefix but maintain order within each group
                cols = list(df.columns)
                metadata_cols = [c for c in cols if c.startswith("Metadata_")]

                # Group other columns by type, preserving order
                pathname_cols = [c for c in cols if c.startswith("PathName_")]
                filename_cols = [c for c in cols if c.startswith("FileName_")]
                frame_cols = [c for c in cols if c.startswith("Frame_")]
                other_cols = [
                    c
                    for c in cols
                    if c
                    not in metadata_cols + pathname_cols + filename_cols + frame_cols
                ]

                # For pipelines with cycles, we need to sort within each group
                if pipeline_id in ["6", "7"]:
                    # Sort by cycle then channel within each group
                    def sort_key(col):
                        # Extract cycle number if present
                        import re

                        match = re.search(r"Cycle(\d+)", col)
                        cycle = int(match.group(1)) if match else 0
                        # Put Orig before Illum
                        orig_first = 0 if "Orig" in col else 1
                        return (cycle, orig_first, col)

                    pathname_cols = sorted(pathname_cols, key=sort_key)
                    filename_cols = sorted(filename_cols, key=sort_key)
                    frame_cols = sorted(frame_cols, key=sort_key)

                # Order: Metadata, PathName, FileName, Frame, Others
                df = df[
                    metadata_cols
                    + pathname_cols
                    + filename_cols
                    + frame_cols
                    + other_cols
                ]

                # Write CSV
                df.to_csv(output_path, index=False)
                print(f"  Wrote {len(df)} rows to {output_path}")

                # Validate if requested
                if args.validate:
                    ref_path = (
                        output_path.parent
                        / f"load_data_pipeline{pipeline_id}_revised.csv"
                    )
                    if ref_path.exists():
                        ref_df = pd.read_csv(ref_path)
                        if df.equals(ref_df):
                            print("  ✓ Matches reference")
                        else:
                            print("  ✗ Differs from reference")
                            # Show differences
                            if len(df) != len(ref_df):
                                print(f"    Row count: {len(df)} vs {len(ref_df)}")
                            if set(df.columns) != set(ref_df.columns):
                                print(
                                    f"    Column diff: {set(df.columns) ^ set(ref_df.columns)}"
                                )
            else:
                # Just print summary
                print(f"  Generated {len(df)} rows with {len(df.columns)} columns")

        except Exception as e:
            print(f"  Error: {e}")
            import traceback

            traceback.print_exc()


if __name__ == "__main__":
    main()
