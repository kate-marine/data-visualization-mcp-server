from __future__ import annotations
import json
import pandas as pd
from data_viz_mcp.server import err, log_err, log_ok, mcp, store
from data_viz_mcp.tools.datasets import _store_dataframe

_FILTER_OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "contains", "startswith", "endswith"}
_AGG_FUNCS = {"sum", "mean", "count", "min", "max", "median"}


@mcp.tool()
def filter_dataset(
    dataset_id: str,
    column: str,
    operator: str,
    value: str,
    name: str | None = None,
) -> str:
    """Filter rows from a dataset and return a new dataset.

    operator must be one of: eq, ne, gt, gte, lt, lte, contains, startswith, endswith.
    value is always passed as a string and cast to the column's dtype for numeric comparisons.
    Returns a new dataset ID with only the matching rows.
    """
    op = "filter_dataset"
    result = store.get_dataset(dataset_id)
    if result is None:
        log_err(op, [dataset_id], f"Dataset '{dataset_id}' not found")
        return json.dumps(err(op, dataset_id, f"Dataset '{dataset_id}' not found"))
    ds, df = result

    if column not in df.columns:
        log_err(op, [dataset_id], f"Column '{column}' not found")
        return json.dumps(err(op, dataset_id, f"Column '{column}' not found in dataset '{dataset_id}'"))

    if operator not in _FILTER_OPS:
        return json.dumps(err(op, dataset_id, f"Unsupported operator '{operator}'. Supported: {', '.join(sorted(_FILTER_OPS))}"))

    series = df[column]
    try:
        if pd.api.types.is_numeric_dtype(series):
            cast_value: object = float(value)
        else:
            cast_value = value

        if operator == "eq":
            mask = series == cast_value
        elif operator == "ne":
            mask = series != cast_value
        elif operator == "gt":
            mask = series > cast_value  # type: ignore[operator]
        elif operator == "gte":
            mask = series >= cast_value  # type: ignore[operator]
        elif operator == "lt":
            mask = series < cast_value  # type: ignore[operator]
        elif operator == "lte":
            mask = series <= cast_value  # type: ignore[operator]
        elif operator == "contains":
            mask = series.astype(str).str.contains(str(value), na=False)
        elif operator == "startswith":
            mask = series.astype(str).str.startswith(str(value), na=False)
        elif operator == "endswith":
            mask = series.astype(str).str.endswith(str(value), na=False)
        else:
            mask = pd.Series([False] * len(df))
    except Exception as exc:
        log_err(op, [dataset_id], str(exc))
        return json.dumps(err(op, dataset_id, f"Filter failed: {exc}"))

    filtered = df[mask].reset_index(drop=True)
    dataset_name = name or f"{ds.name}[{column} {operator} {value}]"
    return _store_dataframe(dataset_name, filtered, op)


@mcp.tool()
def aggregate_dataset(
    dataset_id: str,
    group_by: str,
    agg_column: str,
    agg_func: str = "sum",
    name: str | None = None,
) -> str:
    """Group a dataset by a column and aggregate another column.

    agg_func must be one of: sum, mean, count, min, max, median.
    Returns a new dataset with one row per group.
    """
    op = "aggregate_dataset"
    result = store.get_dataset(dataset_id)
    if result is None:
        log_err(op, [dataset_id], f"Dataset '{dataset_id}' not found")
        return json.dumps(err(op, dataset_id, f"Dataset '{dataset_id}' not found"))
    ds, df = result

    for col in (group_by, agg_column):
        if col not in df.columns:
            log_err(op, [dataset_id], f"Column '{col}' not found")
            return json.dumps(err(op, dataset_id, f"Column '{col}' not found in dataset '{dataset_id}'"))

    if agg_func not in _AGG_FUNCS:
        return json.dumps(err(op, dataset_id, f"Unsupported agg_func '{agg_func}'. Supported: {', '.join(sorted(_AGG_FUNCS))}"))

    try:
        grouped = df.groupby(group_by)[agg_column].agg(agg_func).reset_index()
        grouped.columns = [group_by, f"{agg_func}_{agg_column}"]
    except Exception as exc:
        log_err(op, [dataset_id], str(exc))
        return json.dumps(err(op, dataset_id, f"Aggregation failed: {exc}"))

    dataset_name = name or f"{ds.name}[{group_by} → {agg_func}({agg_column})]"
    return _store_dataframe(dataset_name, grouped, op)


@mcp.tool()
def sort_dataset(
    dataset_id: str,
    column: str,
    ascending: bool = True,
    name: str | None = None,
) -> str:
    """Sort a dataset by a column. Returns a new dataset."""
    op = "sort_dataset"
    result = store.get_dataset(dataset_id)
    if result is None:
        log_err(op, [dataset_id], f"Dataset '{dataset_id}' not found")
        return json.dumps(err(op, dataset_id, f"Dataset '{dataset_id}' not found"))
    ds, df = result

    if column not in df.columns:
        log_err(op, [dataset_id], f"Column '{column}' not found")
        return json.dumps(err(op, dataset_id, f"Column '{column}' not found in dataset '{dataset_id}'"))

    sorted_df = df.sort_values(by=column, ascending=ascending).reset_index(drop=True)
    direction = "asc" if ascending else "desc"
    dataset_name = name or f"{ds.name}[sorted by {column} {direction}]"
    return _store_dataframe(dataset_name, sorted_df, op)


@mcp.tool()
def select_columns(
    dataset_id: str,
    columns: list[str],
    name: str | None = None,
) -> str:
    """Return a new dataset containing only the specified columns."""
    op = "select_columns"
    result = store.get_dataset(dataset_id)
    if result is None:
        log_err(op, [dataset_id], f"Dataset '{dataset_id}' not found")
        return json.dumps(err(op, dataset_id, f"Dataset '{dataset_id}' not found"))
    ds, df = result

    missing = [c for c in columns if c not in df.columns]
    if missing:
        log_err(op, [dataset_id], f"Columns not found: {missing}")
        return json.dumps(err(op, dataset_id, f"Columns not found in dataset '{dataset_id}': {missing}"))

    subset = df[columns].copy()
    dataset_name = name or f"{ds.name}[{', '.join(columns)}]"
    return _store_dataframe(dataset_name, subset, op)
