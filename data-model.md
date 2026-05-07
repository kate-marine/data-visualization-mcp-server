# Data Model: MCP Data Visualization Server

Python classes that define every piece of data the server works with

---

## Entities

### Dataset

Represents an uploaded tabular dataset, held in memory for the server process lifetime.

| Field | Type |  |
|---|---|---|
| `id` | `str` | `ds_` assigned at upload, immutable |
| `name` | `str` |  provided by client |
| `columns` | `list[ColumnInfo]` | Ordered list of column descriptors; non-empty |
| `row_count` | `int` | Number of data rows, must be ≥ 0 |
| `data` | `pd.DataFrame` | actual in-memory tabular data |
| `created_at` | `datetime` | timestamp at upload |

**Rules**:
- Upload shoule fail if CSV cannot be parsed into a valid DataFrame.
- Upload should fail if CSV has zero columns.
- Empty dataset (zero rows) is allowed.
- `name` should be non-empty string.

Datasets are immutable once created. No update or delete.

---

### VizSpec

To describe how to create dataset into a visualization.

| Field | Type |  |
|---|---|---|
| `id` | `str` | `vs_`; also assigned at creation and immutable |
| `dataset_id` | `str` | References an existing Dataset `id`|
| `plot_type` | `PlotType` | One of the supported plot types (see below) |
| `x_column` | `str` | Column name for x-axis,  MUST exist in dataset |
| `y_column` | `str \| None` | Column name for y-axis, required for line/scatter/bar, not for histogram |
| `title` | `str \| None` | Optional chart title |
| `x_label` | `str \| None` | Optional x-axis label (defaults to `x_column` if none) |
| `y_label` | `str \| None` | Optional y-axis label (defaults to `y_column` if none) |
| `color` | `str \| None` | Optional hex or color for the primary series |
| `created_at` | `datetime` | timestamp at creation |
| `updated_at` | `datetime` | timestamp of last update; equals `created_at` if never updated |

**Rules**:
- `dataset_id` must reference an existing Dataset; error if not found.
- `x_column` must exist as a column in the Dataset.
- `y_column` must exist in the Dataset if provided and must be provided for `line`, `bar`, `scatter`.
- `y_column` must be None or omitted for `histogram`.
- `plot_type` must be a valid `PlotType` value.


#### PlotType 

| Value | Description |
|---|---|
| `line` | Line chart — x vs y, connected series |
| `bar` | Bar chart — categorical x, numeric y |
| `scatter` | Scatter plot — x vs y, individual points |
| `histogram` | Histogram — distribution of x column; y_column unused |

---

### Plot

Generated visualization output.

| Field | Type | Rules |
|---|---|---|
| `id` | `str` | `pl_`; assigned at generation, immutable |
| `spec_id` | `str` | The VizSpec used, immutable |
| `png_data` | `bytes` | Raw PNG image bytes |
| `html_data` | `str \| None` | Self-contained Plotly HTML, only when requested |
| `created_at` | `datetime` | timestamp at generation |

**Validation rules**:
- `spec_id` must be an existing VizSpec.
- `png_data` must be non-empty after successful generation.
- Multiple Plots may reference the same VizSpec; each has a distinct `id`.

---

## Resource storing

A single `ResourceStore` instance holds three dicts:

```python
datasets: dict[str, Dataset]   # keyed by Dataset.id
vizspecs: dict[str, VizSpec]   # keyed by VizSpec.id
plots:    dict[str, Plot]      # keyed by Plot.id
```

All mutations (insert, update) are synchronous and in-place. 

---

- One Dataset = zero or more VizSpecs
- One VizSpec = zero or more Plots (each generation produces a new Plot)
