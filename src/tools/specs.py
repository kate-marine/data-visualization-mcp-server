from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from difflib import get_close_matches

from data_viz_mcp.models import PlotType, VizSpec
from data_viz_mcp.server import err, log_err, log_ok, mcp, store

# Convert a VizSpec model instance to a dictionary for JSON serialization.
def _spec_to_dict(spec: VizSpec) -> dict:
    """Helper to serialize a VizSpec to JSON-safe dict."""
    return {
        "id": spec.id,
        "dataset_id": spec.dataset_id,
        "plot_type": spec.plot_type.value,
        "x_column": spec.x_column,
        "y_column": spec.y_column,
        "title": spec.title,
        "x_label": spec.x_label,
        "y_label": spec.y_label,
        "color": spec.color,
        "color_by": spec.color_by,
        "created_at": spec.created_at.isoformat(),
        "updated_at": spec.updated_at.isoformat(),
    }


# Plot types that don't require x_column
_NO_X_REQUIRED = {PlotType.HEATMAP}
# don't require y_column
_NO_Y_REQUIRED = {PlotType.HISTOGRAM, PlotType.HEATMAP}
# x_column is optional 
_X_OPTIONAL = {PlotType.BOX, PlotType.VIOLIN}


# Create a new visualization specification for a dataset.
# Validates that all referenced columns exist and required columns are provided.
@mcp.tool()
def create_vizspec(
    dataset_id: str,
    plot_type: str,
    x_column: str | None = None,
    y_column: str | None = None,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    color: str | None = None,
    color_by: str | None = None,
) -> str:
    """Create a visualization spec. x_column is optional for heatmap and box/violin.
    y_column is required for all types except histogram and heatmap.
    color_by splits the data into multiple series by a categorical column (ie for multi-series line charts)."""
    op = "create_vizspec"

     # Validate dataset exists
    ds_result = store.get_dataset(dataset_id)
    if ds_result is None:
        log_err(op, [dataset_id], f"Dataset '{dataset_id}' not found")
        return json.dumps(err(op, dataset_id, f"Dataset '{dataset_id}' not found"))

    #make sure plot type is valid
    try:
        pt = PlotType(plot_type)
    except ValueError:
        supported = ", ".join(v.value for v in PlotType)
        log_err(op, [dataset_id], f"Unsupported plot type '{plot_type}'")
        return json.dumps(err(op, dataset_id, f"Unsupported plot type '{plot_type}'. Supported: {supported}"))

    ds, _ = ds_result
    col_names = {c.name for c in ds.columns}

    # Validate x and y column requirements
    if pt not in _NO_X_REQUIRED and pt not in _X_OPTIONAL and x_column is None:
        return json.dumps(err(op, dataset_id, f"x_column is required for plot type '{plot_type}'"))
    if x_column is not None and x_column not in col_names:
        log_err(op, [dataset_id], f"Column '{x_column}' not found")
        return json.dumps(err(op, dataset_id, f"Column '{x_column}' not found in dataset '{dataset_id}'"))

    if pt not in _NO_Y_REQUIRED:
        if y_column is None:
            log_err(op, [dataset_id], f"y_column required for {plot_type}")
            return json.dumps(err(op, dataset_id, f"y_column is required for plot type '{plot_type}'"))
        if y_column not in col_names:
            log_err(op, [dataset_id], f"Column '{y_column}' not found")
            return json.dumps(err(op, dataset_id, f"Column '{y_column}' not found in dataset '{dataset_id}'"))

    if color_by is not None and color_by not in col_names:
        log_err(op, [dataset_id], f"Column '{color_by}' not found")
        return json.dumps(err(op, dataset_id, f"Column '{color_by}' not found in dataset '{dataset_id}'"))

    # Store the spec
    now = datetime.now(timezone.utc)
    spec_id = store.new_id("vs")
    spec = VizSpec(
        id=spec_id,
        dataset_id=dataset_id,
        plot_type=pt,
        x_column=x_column,
        y_column=y_column,
        title=title,
        x_label=x_label,
        y_label=y_label,
        color=color,
        color_by=color_by,
        created_at=now,
        updated_at=now,
    )
    store.add_vizspec(spec)
    log_ok(op, [dataset_id, spec_id])
    return json.dumps(_spec_to_dict(spec))

# Retrieve a stored visualization spec by ID.
@mcp.tool()
def get_vizspec(id: str) -> str:
    op = "get_vizspec"
    spec = store.get_vizspec(id)
    if spec is None:
        log_err(op, [id], f"VizSpec '{id}' not found")
        return json.dumps(err(op, id, f"VizSpec '{id}' not found"))
    log_ok(op, [id])
    return json.dumps(_spec_to_dict(spec))

# Update an existing visualization spec.
@mcp.tool()
def update_vizspec(
    id: str,
    plot_type: str | None = None,
    x_column: str | None = None,
    y_column: str | None = None,
    title: str | None = None,
    x_label: str | None = None,
    y_label: str | None = None,
    color: str | None = None,
    color_by: str | None = None,
) -> str:
    op = "update_vizspec"

    spec = store.get_vizspec(id)
    if spec is None:
        log_err(op, [id], f"VizSpec '{id}' not found")
        return json.dumps(err(op, id, f"VizSpec '{id}' not found"))

    fields: dict[str, object] = {}

    if plot_type is not None:
        try:
            fields["plot_type"] = PlotType(plot_type)
        except ValueError:
            supported = ", ".join(v.value for v in PlotType)
            return json.dumps(err(op, id, f"Unsupported plot type '{plot_type}'. Supported: {supported}"))

    ds_result = store.get_dataset(spec.dataset_id)
    if ds_result is None:
        return json.dumps(err(op, id, f"Referenced dataset '{spec.dataset_id}' no longer available"))
    ds, _ = ds_result
    col_names = {c.name for c in ds.columns}

    if x_column is not None:
        if x_column not in col_names:
            return json.dumps(err(op, id, f"Column '{x_column}' not found in dataset '{spec.dataset_id}'"))
        fields["x_column"] = x_column

    if y_column is not None:
        if y_column not in col_names:
            return json.dumps(err(op, id, f"Column '{y_column}' not found in dataset '{spec.dataset_id}'"))
        fields["y_column"] = y_column

    if color_by is not None:
        if color_by not in col_names:
            return json.dumps(err(op, id, f"Column '{color_by}' not found in dataset '{spec.dataset_id}'"))
        fields["color_by"] = color_by

    for key, val in [("title", title), ("x_label", x_label), ("y_label", y_label), ("color", color)]:
        if val is not None:
            fields[key] = val

    if not fields:
        return json.dumps(err(op, id, "At least one field must be provided for update"))

    fields["updated_at"] = datetime.now(timezone.utc)
    updated = store.update_vizspec(id, **fields)
    log_ok(op, [id])
    return json.dumps(_spec_to_dict(updated))  # type: ignore[arg-type]

# List all stored visualization specs
@mcp.tool()
def list_vizspecs() -> str:
    op = "list_vizspecs"
    specs = store.list_vizspecs()
    log_ok(op, [s.id for s in specs])
    return json.dumps(
        [{"id": s.id, "dataset_id": s.dataset_id, "plot_type": s.plot_type.value, "created_at": s.created_at.isoformat()}
         for s in specs]
    )


# 
# suggest_vizspec helpers

# Mapping from plot type to keywords for natural-language detection
# ordered most-specific first so a keyword like "scatter" beats "compare"
_PLOT_KEYWORDS: list[tuple[PlotType, list[str]]] = [
    (PlotType.HEATMAP,   ["heatmap", "correlation matrix", "correlations"]),
    (PlotType.PIE,       ["pie", "proportion", "percentage", "share", "breakdown", "composition"]),
    (PlotType.VIOLIN,    ["violin"]),
    (PlotType.BOX,       ["box plot", "boxplot", "box chart", "quartile", "quartiles", "outlier", "outliers"]),
    (PlotType.HISTOGRAM, ["histogram", "distribution", "frequency", "how many", "how often"]),
    (PlotType.AREA,      ["area chart", "area plot", "filled line"]),
    (PlotType.LINE,      ["line chart", "line plot", "trend", "over time", "time series", "timeline", "progression"]),
    (PlotType.SCATTER,   ["scatter", "scatter plot", "relationship between", "correlation between",
                          " vs ", " vs.", "versus", " against "]),
    (PlotType.BAR,       ["bar chart", "bar plot", "bar graph", "column chart", "compare", "comparison"]),
]

_COLOR_NAMES = {"red", "blue", "green", "orange", "purple", "teal", "pink",
                "yellow", "gray", "grey", "black", "navy", "coral", "salmon"}

# Detect plot type from keywords in the description
def _detect_plot_type(desc: str) -> PlotType | None:
    low = desc.lower()
    for pt, keywords in _PLOT_KEYWORDS:
        if any(kw in low for kw in keywords):
            return pt
    return None


def _is_numeric(dtype: str) -> bool:
    return any(t in dtype for t in ("int", "float", "complex", "number"))


def _resolve_col(hint: str, col_lows: dict[str, str]) -> str | None:
    """Exact then fuzzy match a single hint word/phrase against column names."""
    hint = hint.strip()
    if hint in col_lows:
        return col_lows[hint]
    matches = get_close_matches(hint, col_lows.keys(), n=1, cutoff=0.75)
    return col_lows[matches[0]] if matches else None


def _find_columns(desc: str, col_names: list[str]) -> list[str]:
    """Return column names mentioned ordered by first appearance."""
    low = desc.lower()
    found: list[tuple[int, str]] = []
    seen: set[str] = set()

    for col in col_names:
        # try both the raw name and underscore→space variant
        for variant in {col.lower(), col.lower().replace("_", " ")}:
            idx = low.find(variant)
            if idx != -1 and col not in seen:
                found.append((idx, col))
                seen.add(col)
                break

    # difflib fallback on individual words
    col_lows = {c.lower(): c for c in col_names}
    col_lows.update({c.lower().replace("_", " "): c for c in col_names})
    for word in re.findall(r"\b\w+\b", low):
        matches = get_close_matches(word, col_lows.keys(), n=1, cutoff=0.82)
        if matches:
            col = col_lows[matches[0]]
            if col not in seen:
                found.append((low.find(word), col))
                seen.add(col)

    found.sort(key=lambda t: t[0])
    return [c for _, c in found]


def _parse_xy_pattern(desc: str, col_names: list[str]) -> tuple[str | None, str | None]:
    """Extract (x_col, y_col) hints from patterns like 'A by B' or 'A vs B'.

    Splits the description at the keyword and searches each side for column
    names, avoiding the greedy-capture problem of a single regex.
    """
    low = desc.lower()

    # "Y by/per/over X" — y is left of keyword, x is right
    m = re.search(r"\b(by|per|over)\b|for each", low)
    if m:
        before_cols = _find_columns(low[:m.start()], col_names)
        after_cols = _find_columns(low[m.end():], col_names)
        y_col = before_cols[-1] if before_cols else None
        x_col = after_cols[0] if after_cols else None
        if y_col or x_col:
            return x_col, y_col

    # "A vs/versus/against B"
    m = re.search(r"\b(vs\.?|versus|against)\b", low)
    if m:
        before_cols = _find_columns(low[:m.start()], col_names)
        after_cols = _find_columns(low[m.end():], col_names)
        a_col = before_cols[-1] if before_cols else None
        b_col = after_cols[0] if after_cols else None
        if a_col or b_col:
            return a_col, b_col

    return None, None

# Infer x and y columns for the plot
def _infer_xy(
    mentioned: list[str],
    pat_x: str | None,
    pat_y: str | None,
    plot_type: PlotType,
    col_dtypes: dict[str, str],
) -> tuple[str | None, str | None]:
    if plot_type == PlotType.HEATMAP:
        return None, None
    if plot_type == PlotType.HISTOGRAM:
        return pat_x or (mentioned[0] if mentioned else None), None

    if pat_x and pat_y:
        return pat_x, pat_y

    # Build candidate pool: pattern hints first, then mentioned, deduped
    pool: list[str] = []
    for c in [pat_x, pat_y] + mentioned:
        if c and c not in pool:
            pool.append(c)

    if not pool:
        return None, None

    numerics = [c for c in pool if _is_numeric(col_dtypes.get(c, ""))]
    cats = [c for c in pool if not _is_numeric(col_dtypes.get(c, ""))]

    if plot_type == PlotType.SCATTER:
        if len(numerics) >= 2:
            return numerics[0], numerics[1]
        return (pool[0], pool[1]) if len(pool) >= 2 else (pool[0], None)

    
    x = pat_x or (cats[0] if cats else None)
    y = pat_y or (numerics[0] if numerics else None)
    if x == y:
        remaining = [c for c in pool if c != x]
        y = remaining[0] if remaining else None
    return x, y

# Infer plot type from column data types when no keyword is found
def _infer_plot_type_from_dtypes(x_col: str | None, y_col: str | None, col_dtypes: dict[str, str]) -> PlotType:
    if x_col and y_col:
        if _is_numeric(col_dtypes.get(x_col, "")) and _is_numeric(col_dtypes.get(y_col, "")):
            return PlotType.SCATTER
        return PlotType.BAR
    return PlotType.HISTOGRAM if x_col else PlotType.BAR

# Assign a confidence level to the suggestion
def _confidence(pat_x: str | None, pat_y: str | None, mentioned: list[str], notes: list[str]) -> str:
    if any("defaulted" in n for n in notes):
        return "low"
    if pat_x or pat_y:
        return "high"
    if mentioned:
        return "medium"
    return "low"



# Suggest a visualization spec from natural-language description
# Infers plot type, column mappings, and optional styling
@mcp.tool()
def suggest_vizspec(
    dataset_id: str,
    description: str,
    title: str | None = None,
    color: str | None = None,
    color_by: str | None = None,
) -> str:
    """Create a VizSpec from a natural-language description.

    The tool resolves column names and plot type from the description text,
    creates the VizSpec, and returns it alongside a 'reasoning' field and a
    'confidence' level (high/medium/low). Review reasoning before calling
    generate_plot — low-confidence specs may need manual correction via
    update_vizspec.

    Limitations callers should know:
    - Aggregate intent ("total sales by region") is NOT handled; call
      aggregate_dataset first, then suggest_vizspec on the result.
    - Conceptual synonyms ("revenue" for a column named "sales") won't match.
    - Multi-metric requests ("sales and cost") pick only one y_column.
    - Temporal columns are not auto-detected as LINE candidates unless the
      description contains keywords like "trend" or "over time".

    Examples:
      "bar chart of sales by region"
      "show the distribution of cost"
      "scatter plot of sales vs cost"
      "sales trend over quarter as a line chart"
      "correlation heatmap"
    """
    op = "suggest_vizspec"

    ds_result = store.get_dataset(dataset_id)
    if ds_result is None:
        log_err(op, [dataset_id], f"Dataset '{dataset_id}' not found")
        return json.dumps(err(op, dataset_id, f"Dataset '{dataset_id}' not found"))

    ds, _ = ds_result
    col_names = [c.name for c in ds.columns]
    col_dtypes = {c.name: c.dtype for c in ds.columns}
    notes: list[str] = []

    # Detect plot type from keywords
    plot_type = _detect_plot_type(description)
    if plot_type:
        notes.append(f"Plot type '{plot_type.value}' detected from description keywords.")
    else:
        notes.append("No plot-type keyword found; will infer from resolved column types.")

    # Structural pattern (ie "sales vs cost")
    pat_x, pat_y = _parse_xy_pattern(description, col_names)
    if pat_x or pat_y:
        notes.append(f"Structural pattern resolved: x='{pat_x}', y='{pat_y}'.")

    # all mentioned columns as fallback pool
    mentioned = _find_columns(description, col_names)
    if mentioned:
        notes.append(f"Columns matched in description: {mentioned}.")

    # Resolve x/y
    effective_pt = plot_type or PlotType.BAR
    x_col, y_col = _infer_xy(mentioned, pat_x, pat_y, effective_pt, col_dtypes)

    # infer plot type from dtypes if still unknown
    if plot_type is None:
        plot_type = _infer_plot_type_from_dtypes(x_col, y_col, col_dtypes)
        notes.append(f"Inferred plot type '{plot_type.value}' from column dtypes.")

    # fill in missing columns with dataset defaults so the spec is always valid
    if plot_type not in _NO_X_REQUIRED and plot_type not in _X_OPTIONAL and x_col is None:
        fallback = next((c for c in col_names if not _is_numeric(col_dtypes[c])), col_names[0] if col_names else None)
        x_col = fallback
        notes.append(f"x_column not found in description; defaulted to '{x_col}'.")

    if plot_type not in _NO_Y_REQUIRED and y_col is None:
        fallback = next((c for c in col_names if _is_numeric(col_dtypes[c]) and c != x_col), None)
        if fallback is None:
            fallback = next((c for c in col_names if c != x_col), None)
        y_col = fallback
        notes.append(f"y_column not found in description; defaulted to '{y_col}'.")

    if plot_type not in _NO_Y_REQUIRED and y_col is None:
        log_err(op, [dataset_id], "Could not resolve y_column")
        return json.dumps(err(
            op, dataset_id,
            "Could not resolve a y_column from the description. "
            "Try being more explicit, e.g. 'bar chart of sales by region'.",
        ))

    # Detect color_by from description if not passed explicitly
    col_lows = {c.lower(): c for c in col_names}
    col_lows.update({c.lower().replace("_", " "): c for c in col_names})
    if color_by is None:
        m = re.search(r"(?:grouped|colored|split|broken down|separated)\s+by\s+([\w ]+?)(?:\s+(?:as|in|chart|plot)|$)", description.lower())
        if m:
            hint = m.group(1).strip()
            color_by = _resolve_col(hint, col_lows)
            if color_by:
                notes.append(f"color_by='{color_by}' detected from 'grouped/colored/split by' pattern.")
                # If color_by was misidentified as x_col, clear x_col so it can be reassigned
                if x_col == color_by:
                    x_col = None
                    notes.append(f"x_column cleared (was same as color_by); will re-apply defaults.")
                    if plot_type not in _NO_X_REQUIRED and plot_type not in _X_OPTIONAL:
                        fallback = next((c for c in col_names if not _is_numeric(col_dtypes[c]) and c != color_by), None)
                        x_col = fallback
                        notes.append(f"x_column re-defaulted to '{x_col}'.")

    # extract color from description if not passed explicitly
    if color is None:
        m = re.search(r"\b(" + "|".join(_COLOR_NAMES) + r")\b", description.lower())
        if m:
            color = m.group(1)
            notes.append(f"Color '{color}' extracted from description.")

    # check for aggregate intent and warn (ex we can't act on it here)
    agg_words = {"total", "sum", "average", "mean", "count", "aggregate"}
    if any(w in description.lower() for w in agg_words):
        notes.append(
            "WARNING: description implies aggregation (e.g. 'total', 'sum', 'average'). "
            "This spec plots raw data. Call aggregate_dataset first for aggregated results."
        )

    # Create and store the VizSpec
    now = datetime.now(timezone.utc)
    spec_id = store.new_id("vs")
    spec = VizSpec(
        id=spec_id,
        dataset_id=dataset_id,
        plot_type=plot_type,
        x_column=x_col,
        y_column=y_col,
        title=title,
        color=color,
        color_by=color_by,
        created_at=now,
        updated_at=now,
    )
    store.add_vizspec(spec)
    log_ok(op, [dataset_id, spec_id])

    result = _spec_to_dict(spec)
    result["reasoning"] = " ".join(notes)
    result["confidence"] = _confidence(pat_x, pat_y, mentioned, notes)
    return json.dumps(result)
