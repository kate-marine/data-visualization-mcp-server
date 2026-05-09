"""Unit tests for suggest_vizspec."""

import json
from datetime import datetime, timezone

import pandas as pd
import pytest

from data_viz_mcp.models import ColumnInfo, Dataset
from data_viz_mcp.server import store
from data_viz_mcp.tools.specs import suggest_vizspec


def _load(df: pd.DataFrame, name: str = "test") -> str:
    ds_id = store.new_id("ds")
    cols = [ColumnInfo(name=c, dtype=str(df[c].dtype)) for c in df.columns]
    ds = Dataset(id=ds_id, name=name, columns=cols, row_count=len(df), created_at=datetime.now(timezone.utc))
    store.add_dataset(ds, df)
    return ds_id


DF = pd.DataFrame({
    "region": ["A", "B", "A"],
    "product": ["X", "Y", "X"],
    "sales": [100, 200, 150],
    "cost": [60, 120, 90],
    "quarter": ["Q1", "Q2", "Q3"],
})


def _suggest(desc: str, **kwargs) -> dict:
    ds_id = _load(DF)
    return json.loads(suggest_vizspec(dataset_id=ds_id, description=desc, **kwargs))


# --- plot type detection ---

def test_bar_keyword():
    r = _suggest("bar chart of sales by region")
    assert r["plot_type"] == "bar"

def test_line_keyword():
    r = _suggest("line chart of sales over quarter")
    assert r["plot_type"] == "line"

def test_scatter_vs_keyword():
    r = _suggest("scatter plot of sales vs cost")
    assert r["plot_type"] == "scatter"

def test_histogram_keyword():
    r = _suggest("show the distribution of sales")
    assert r["plot_type"] == "histogram"

def test_heatmap_keyword():
    r = _suggest("correlation heatmap")
    assert r["plot_type"] == "heatmap"
    assert r["x_column"] is None
    assert r["y_column"] is None

def test_pie_keyword():
    r = _suggest("pie chart of sales by region")
    assert r["plot_type"] == "pie"

def test_box_keyword():
    r = _suggest("box plot of sales")
    assert r["plot_type"] == "box"

def test_violin_keyword():
    r = _suggest("violin plot of cost")
    assert r["plot_type"] == "violin"


# --- column resolution ---

def test_by_pattern_resolves_xy():
    r = _suggest("bar chart of sales by region")
    assert r["x_column"] == "region"
    assert r["y_column"] == "sales"

def test_vs_pattern_resolves_xy():
    r = _suggest("scatter of sales vs cost")
    assert r["x_column"] == "sales"
    assert r["y_column"] == "cost"

def test_column_name_in_description():
    r = _suggest("show sales distribution")
    assert r["y_column"] == "sales" or r["x_column"] == "sales"

def test_underscore_variant():
    df = pd.DataFrame({"total_sales": [1, 2, 3], "region": ["A", "B", "C"]})
    ds_id = _load(df)
    r = json.loads(suggest_vizspec(dataset_id=ds_id, description="bar chart of total sales by region"))
    assert r["y_column"] == "total_sales"
    assert r["x_column"] == "region"


# --- fallback behaviour ---

def test_vague_description_still_returns_spec():
    r = _suggest("make a chart")
    assert "plot_type" in r
    assert r["confidence"] == "low"

def test_missing_dataset():
    r = json.loads(suggest_vizspec(dataset_id="ds_nonexistent", description="bar chart"))
    assert r["error"] is True


# --- aggregate warning ---

def test_aggregate_warning_in_reasoning():
    r = _suggest("show total sales by region")
    assert "WARNING" in r["reasoning"]
    assert "aggregate" in r["reasoning"].lower()


# --- color extraction ---

def test_color_from_description():
    r = _suggest("bar chart of sales by region in blue")
    assert r["color"] == "blue"

def test_explicit_color_overrides():
    r = _suggest("bar chart of sales by region in red", color="green")
    assert r["color"] == "green"


# --- confidence ---

def test_high_confidence_with_pattern():
    r = _suggest("bar chart of sales by region")
    assert r["confidence"] == "high"

def test_reasoning_present():
    r = _suggest("line chart of sales over quarter")
    assert isinstance(r["reasoning"], str)
    assert len(r["reasoning"]) > 0
