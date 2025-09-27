#!/usr/bin/env python3
# /// script
# requires-python = ">=3.8"
# dependencies = [
#   "pydantic>=2.0",
# ]
# ///
"""Pydantic models for LoadData generation specification."""

from typing import Dict, List, Optional, Union, Literal, Any
from pydantic import BaseModel, Field, field_validator


class ColumnDefinition(BaseModel):
    """Definition for a single column in LoadData CSV."""

    name: str = Field(
        ...,
        description="Column name (may contain {channel}, {cycle:02d}, {tile} placeholders)",
    )

    # One of these should be specified
    source: Optional[str] = Field(
        None, description="Direct field from samplesheet (e.g., 'plate', 'well')"
    )
    pattern: Optional[str] = Field(
        None,
        description="Template pattern with placeholders (e.g., '{base_path}/images/{plate}/')",
    )
    value: Optional[Union[str, int]] = Field(
        None, description="Fixed value or special value like 'channel_index'"
    )
    expression: Optional[str] = Field(
        None,
        description="Python expression to evaluate (e.g., 'ord(well[0]) * 1000 + int(well[1:])')",
    )

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v):
        if not v:
            raise ValueError("Column name cannot be empty")
        return v

    def model_post_init(self, __context):
        """Validate that at least one source type is specified."""
        sources = [self.source, self.pattern, self.value, self.expression]
        if all(s is None for s in sources):
            raise ValueError(
                "Must specify at least one of: source, pattern, value, expression"
            )


class PerChannelColumns(BaseModel):
    """Column definitions that repeat for each channel."""

    channels: str = Field(
        ..., description="Channel set name (e.g., 'painting', 'barcoding')"
    )
    columns: List[ColumnDefinition] = Field(
        ..., description="Column definitions with {channel} placeholder"
    )


class PerCyclePerChannelColumns(BaseModel):
    """Column definitions for multi-cycle data (pipelines 6, 7)."""

    channels: str = Field(..., description="Channel set name")
    columns: List[ColumnDefinition] = Field(
        ...,
        description="Column definitions with {cycle:02d} and {channel} placeholders",
    )
    special_rules: Optional[Dict[str, Dict[str, Any]]] = Field(
        None, description="Special rules like DNA only from cycle 1"
    )


class BarcodingChannels(BaseModel):
    """Barcoding channel definitions for pipeline 9."""

    cycles: List[int] = Field(..., description="List of cycle numbers")
    channels: List[str] = Field(..., description="List of channel names")
    columns: List[ColumnDefinition]


class BarcodingDNA(BaseModel):
    """Barcoding DNA channel definitions for pipeline 9."""

    cycles: List[int] = Field(..., description="List of cycle numbers")
    columns: List[ColumnDefinition]


class PaintingChannels(BaseModel):
    """Painting channel definitions for pipeline 9."""

    channels: List[str] = Field(..., description="List of channel names")
    columns: List[ColumnDefinition]


class PipelineColumns(BaseModel):
    """Column definitions for a pipeline."""

    metadata: List[ColumnDefinition] = Field(..., description="Metadata columns")

    # Different column types depending on pipeline
    per_channel: Optional[PerChannelColumns] = None
    per_channel_orig: Optional[PerChannelColumns] = None
    per_channel_illum: Optional[PerChannelColumns] = None
    per_cycle_per_channel: Optional[PerCyclePerChannelColumns] = None
    per_cycle_per_channel_orig: Optional[PerCyclePerChannelColumns] = None
    per_cycle_per_channel_illum: Optional[PerCyclePerChannelColumns] = None

    # Pipeline 9 specific
    barcoding_channels: Optional[BarcodingChannels] = None
    barcoding_dna: Optional[BarcodingDNA] = None
    painting_channels: Optional[PaintingChannels] = None


class PipelineDefinition(BaseModel):
    """Complete definition for a single pipeline."""

    name: str = Field(..., description="Human-readable pipeline name")
    filter: str = Field(
        ..., description="Pandas query string to filter samplesheet rows"
    )
    grouping: List[str] = Field(..., description="Fields to group by")
    columns: PipelineColumns = Field(..., description="Column definitions")

    # Optional fields
    wide_format: Optional[bool] = Field(
        False, description="Whether to create wide format (all cycles in one row)"
    )
    cycles: Optional[Union[Literal["all"], List[int]]] = Field(
        None, description="Which cycles to include"
    )
    tiles_per_well: Optional[int] = Field(
        None, description="Number of tiles per well (for synthetic tile generation)"
    )
    synthetic_tiles: Optional[bool] = Field(
        False, description="Whether to generate synthetic tile entries"
    )


class Metadata(BaseModel):
    """Metadata about the specification."""

    description: str
    version: str
    base_path: str = Field(..., description="Default base path for all pipelines")


class LoadDataSpec(BaseModel):
    """Complete LoadData generation specification."""

    metadata: Metadata
    channel_definitions: Dict[str, List[str]] = Field(
        ..., description="Channel sets by name"
    )
    pipelines: Dict[str, PipelineDefinition] = Field(
        ..., description="Pipeline definitions by ID"
    )
    special_values: Dict[str, str] = Field(
        ..., description="Documentation for special values"
    )

    def get_channels(self, channel_set_name: str) -> List[str]:
        """Get channel list by name."""
        if channel_set_name not in self.channel_definitions:
            raise ValueError(f"Unknown channel set: {channel_set_name}")
        return self.channel_definitions[channel_set_name]

    def get_pipeline(self, pipeline_id: str) -> PipelineDefinition:
        """Get pipeline definition by ID."""
        if pipeline_id not in self.pipelines:
            raise ValueError(f"Unknown pipeline: {pipeline_id}")
        return self.pipelines[pipeline_id]


def load_spec(json_path: str) -> LoadDataSpec:
    """Load and validate a LoadData specification from JSON."""
    import json

    with open(json_path, "r") as f:
        data = json.load(f)

    return LoadDataSpec(**data)


def validate_spec(spec_path: str) -> None:
    """Validate a LoadData specification file."""
    try:
        spec = load_spec(spec_path)
        print("✓ Specification is valid")
        print(f"  Version: {spec.metadata.version}")
        print(f"  Pipelines: {', '.join(spec.pipelines.keys())}")
        print(f"  Channel sets: {', '.join(spec.channel_definitions.keys())}")
    except Exception as e:
        print(f"✗ Specification is invalid: {e}")
        raise


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        validate_spec(sys.argv[1])
    else:
        print("Usage: python load_data_models.py <spec.json>")
