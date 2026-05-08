from __future__ import annotations
import io
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from data_viz_mcp.models import ColumnInfo, Dataset
from data_viz_mcp.server import err, log_err, log_ok, mcp, store

# defines the MCP tools for dataset handling

def _store_dataframe(name: str, df: pd.DataFrame, op: str) -> str:
    ds_id = store.new_id("ds")
    columns = [ColumnInfo(name=col, dtype=str(df[col].dtype)) for col in df.columns]
    dataset = Dataset(
        id=ds_id,
        name=name.strip(),
        columns=columns,
        row_count=len(df),
        created_at=datetime.now(timezone.utc),
    )
    store.add_dataset(dataset, df)
    log_ok(op, [ds_id])
    return json.dumps(
        {"id": ds_id, "name": dataset.name, "columns": [c.model_dump() for c in columns], "row_count": dataset.row_count}
    )


@mcp.tool()
def upload_dataset(name: str, csv_data: str) -> str:
    op = "upload_dataset"
    if not name or not name.strip():
        log_err(op, [], "Dataset name must be non-empty")
        return json.dumps(err(op, None, "Dataset name must be non-empty"))
    try:
        df = pd.read_csv(io.StringIO(csv_data))
    except Exception as exc:
        log_err(op, [], str(exc))
        return json.dumps(err(op, None, f"CSV parsing failed: {exc}"))
    if df.empty and len(df.columns) == 0:
        log_err(op, [], "CSV must contain at least one column")
        return json.dumps(err(op, None, "CSV must contain at least one column"))
    return _store_dataframe(name, df, op)


@mcp.tool()
def upload_dataset_from_path(path: str, name: str | None = None) -> str:
    """Load a CSV file from the local filesystem and register it as a dataset.

    `name` defaults to the file's stem (filename without extension) if not provided.
    The path must be an absolute path or relative to the server's working directory.
    """
    op = "upload_dataset_from_path"
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists():
        log_err(op, [], f"File not found: {resolved}")
        return json.dumps(err(op, None, f"File not found: {resolved}"))
    if not resolved.is_file():
        log_err(op, [], f"Path is not a file: {resolved}")
        return json.dumps(err(op, None, f"Path is not a file: {resolved}"))
    if resolved.suffix.lower() != ".csv":
        log_err(op, [], f"Only CSV files are supported, got: {resolved.suffix}")
        return json.dumps(err(op, None, f"Only CSV files are supported, got: {resolved.suffix}"))
    try:
        df = pd.read_csv(resolved)
    except Exception as exc:
        log_err(op, [], str(exc))
        return json.dumps(err(op, None, f"CSV parsing failed: {exc}"))
    if len(df.columns) == 0:
        log_err(op, [], "CSV must contain at least one column")
        return json.dumps(err(op, None, "CSV must contain at least one column"))
    dataset_name = name.strip() if name and name.strip() else resolved.stem
    return _store_dataframe(dataset_name, df, op)


@mcp.tool()
def describe_dataset(id: str) -> str:
    """Return summary statistics for every column in a dataset.

    Numeric columns include: count, nulls, mean, std, min, 25/50/75 percentiles, max.
    Categorical columns include: count, nulls, unique count, top 5 most frequent values.
    """
    op = "describe_dataset"
    result = store.get_dataset(id)
    if result is None:
        log_err(op, [id], f"Dataset '{id}' not found")
        return json.dumps(err(op, id, f"Dataset '{id}' not found"))
    ds, df = result

    columns_stats = []
    for col in df.columns:
        series = df[col]
        null_count = int(series.isna().sum())
        base = {"name": col, "dtype": str(series.dtype), "count": len(series), "null_count": null_count}

        if pd.api.types.is_numeric_dtype(series):
            desc = series.describe()
            base.update({
                "kind": "numeric",
                "mean": round(float(desc["mean"]), 4),
                "std": round(float(desc["std"]), 4) if "std" in desc else None,
                "min": round(float(desc["min"]), 4),
                "p25": round(float(desc["25%"]), 4),
                "median": round(float(desc["50%"]), 4),
                "p75": round(float(desc["75%"]), 4),
                "max": round(float(desc["max"]), 4),
            })
        else:
            top = series.value_counts().head(5)
            base.update({
                "kind": "categorical",
                "unique_count": int(series.nunique()),
                "top_values": [{"value": str(k), "count": int(v)} for k, v in top.items()],
            })
        columns_stats.append(base)

    log_ok(op, [id])
    return json.dumps({
        "id": ds.id,
        "name": ds.name,
        "row_count": ds.row_count,
        "column_count": len(df.columns),
        "columns": columns_stats,
    })


@mcp.tool()
def list_datasets() -> str:
    op = "list_datasets"
    datasets = store.list_datasets()
    log_ok(op, [ds.id for ds in datasets])
    return json.dumps(
        [
            {"id": ds.id, "name": ds.name, "columns": [c.model_dump() for c in ds.columns], "row_count": ds.row_count}
            for ds in datasets
        ]
    )


@mcp.tool()
def get_dataset(id: str) -> str:
    op = "get_dataset"
    result = store.get_dataset(id)
    if result is None:
        log_err(op, [id], f"Dataset '{id}' not found")
        return json.dumps(err(op, id, f"Dataset '{id}' not found"))
    ds, df = result
    log_ok(op, [id])
    return json.dumps(
        {
            "id": ds.id,
            "name": ds.name,
            "columns": [c.model_dump() for c in ds.columns],
            "row_count": ds.row_count,
            "preview": df.head(5).to_csv(index=False),
        }
    )
