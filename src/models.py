from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class PlotType(str, Enum):
    LINE = "line"
    BAR = "bar"
    SCATTER = "scatter"
    HISTOGRAM = "histogram"
    AREA = "area"
    BOX = "box"
    VIOLIN = "violin"
    PIE = "pie"
    HEATMAP = "heatmap"


class ColumnInfo(BaseModel):
    name: str
    dtype: str


class Dataset(BaseModel):
    id: str
    name: str
    columns: list[ColumnInfo]
    row_count: int
    created_at: datetime


class VizSpec(BaseModel):
    id: str
    dataset_id: str
    plot_type: PlotType
    x_column: str | None = None  # None only for heatmap (correlation matrix)
    y_column: str | None = None
    title: str | None = None
    x_label: str | None = None
    y_label: str | None = None
    color: str | None = None
    color_by: str | None = None  # column to split into series (multi-series plots)
    created_at: datetime
    updated_at: datetime


class Plot(BaseModel):
    id: str
    spec_id: str
    has_html: bool
    created_at: datetime
