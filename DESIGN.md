# Design Document 

## Overview

An MCP server that gives clients (currently testing with Claude Desktop) the ability to work with data. A client can upload a dataset, describe how they want it visualized, and get a chart back with tool calls in a normal conversation.

---

## Motivation

LLMs can reason about data but can't always render charts. This server bridges that gap by handling the data storage and rendering, while leaving the reasoning and interpretation to the LLM.

---

## Workflow


1. Client uploads dataset (CSV)
    
2. Server stores dataset with an id (ex: ds_xxx)

3. Client requests a chart (ex: "bar chart of revenue by city")

4. Server creates a VizSpec with an id (ex: vs_xxx) 

5. Client calls generate_plot

6. Server creates PNG and HTML if asked for, returns image inline


Note: Every object the server creates has a unique ID, and subsequent calls reference that ID. This is what allows a multi-turn conversation to build on earlier steps without re-uploading data.

---

## Architecture

```
Claude Desktop
     │  MCP (stdio)
     ▼
FastMCP server
     │
     ├── tools/datasets.py    — tools to upload, describe, list datasets
     ├── tools/transforms.py  — tools filter, aggregate, sort, and select columns
     ├── tools/specs.py       — tools to create, update, suggest visualization specs
     └── tools/plots.py       — tools to generate, retrieve, and list plots
     │
     ├── viz/renderer.py      — matplotlib → PNG
     └── viz/interactive.py   — Plotly → self-contained HTML
     │
     ├── store.py             — in-memory state (singleton)
     └── models.py            — Dataset, VizSpec, Plot (Pydantic)
```
```


**datasets.py**    — tools to upload, describe, list datasets
**transforms.py**  — tools filter, aggregate, sort, and select columns
**specs.py**       — tools to create, update, suggest visualization specs
**plots.py**       — tools to generate, retrieve, and list plots

**renderer.py**      — matplotlib → PNG
**interactive.py**   — Plotly → self-contained HTML

**store.py**             — in-memory state (singleton)
**models.py**           — Dataset, VizSpec, Plot (Pydantic)
```

Note: All tools share a single `ResourceStore` instance. State is never passed between tools directly it's only through IDs.

---

## Data model

Three objects, each with a unique ID:

| Object | What it represents | Key fields |
|--------|--------------------|------------|
| **Dataset** | Uploaded tabular data | id, name, columns, row_count |
| **VizSpec** | A chart recipe | dataset_id, plot_type, x_column, y_column, color_by |
| **Plot** | A rendered output | spec_id, has_html |

The actual DataFrame is stored separately alongside the Dataset (Pydantic can't serialize it). Relationships between objects are expressed through ID references, not nesting.

---

## Tools 

### Dataset tools
| Tool | Description |
|------|-------------|
| `upload_dataset` | Upload a CSV as a raw string; returns a dataset ID |
| `upload_dataset_from_path` | Load a CSV directly from a file path on disk |
| `describe_dataset` | Per-column stats: mean/min/max/std for numeric, unique count and top values for categorical |
| `list_datasets` | List all datasets currently in the store |
| `get_dataset` | Retrieve metadata for a specific dataset by ID |

### Transform tools
| Tool | Description |
|------|-------------|
| `filter_dataset` | Keep rows matching a condition (eq, gt, lt, contains, etc.); returns a new dataset ID |
| `aggregate_dataset` | Group by a column and apply a function (sum, mean, count, min, max, median); returns a new dataset ID |
| `sort_dataset` | Reorder rows by a column ascending or descending; returns a new dataset ID |
| `select_columns` | Drop unwanted columns; returns a new dataset ID |

### Visualization spec tools
| Tool | Description |
|------|-------------|
| `create_vizspec` | Create a chart recipe: specify dataset, plot type, x/y columns, optional color and grouping |
| `suggest_vizspec` | Create a VizSpec from a plain English description; returns the spec plus `reasoning` and `confidence` fields |
| `update_vizspec` | Modify fields on an existing VizSpec (plot type, columns, labels, color, etc.) |
| `get_vizspec` | Retrieve a VizSpec by ID |
| `list_vizspecs` | List all VizSpecs in the store |

### Plot tools
| Tool | Description |
|------|-------------|
| `generate_plot` | Render a VizSpec into a PNG (returned inline) and optionally store HTML |
| `get_plot` | Retrieve a previously rendered plot; `format="png"` returns the image, `format="html"` writes to a temp file and returns the path |
| `list_plots` | List all rendered plots in the store |
| `list_plot_types` | List all supported plot type names |


---

## Supported plot types

| Type | Use case |
|------|----------|
| line | Trends over time |
| bar | Comparisons across categories |
| scatter | Relationships between two numeric columns |
| histogram | Distribution of a single column |
| area | Cumulative or stacked trends |
| box | Distribution spread and outliers by group |
| violin | Distribution shape by group |
| pie | Part-to-whole proportions |
| heatmap | Correlation matrix across all numeric columns |

---

## Key design decisions

**Immutable datasets.** Transforms (filter, aggregate, sort) always produce a new dataset with a new ID. The source is never modified. This makes exploratory workflows safe — you can branch and try things without destroying your original data.

**VizSpec separates intent from output.** Creating a VizSpec doesn't render anything. This allows a spec to be inspected, updated, and re-rendered without re-specifying everything from scratch.

**Two rendering backends.** Matplotlib produces a static PNG returned inline in the conversation. Plotly produces self-contained interactive HTML written to a temp file. The HTML is ~3MB (Plotly.js is bundled inside), which exceeds MCP's 1MB tool-result limit — so we write to disk and return the file path instead.

**Persistence via SQLite + CSV.** On every write, dataset metadata and vizspec fields are saved to a local SQLite database. The raw DataFrame is saved as a CSV file. On server startup, everything is reloaded. Plots are not persisted — they're derived outputs and are regenerated on demand.

**color_by for multi-series charts.** A single `color_by` field on VizSpec splits any chart into series by a categorical column. In Plotly this is one parameter; in matplotlib it means iterating over groups. This handles the common "show all cities on the same line chart" pattern.
---

## Limitations

- **No authentication.** Any client with access to the server can read all data.
- **In-memory during runtime.** Very large datasets will consume RAM proportionally.
- **No multi-series y-columns.** A VizSpec has one y_column. Plotting two metrics on the same chart requires two separate specs.
- **Aggregate intent in suggest_vizspec.** "Total revenue by city" implies aggregation, but `suggest_vizspec` only creates a VizSpec — the caller must run `aggregate_dataset` first.
- **Fuzzy column matching has a cutoff.** Conceptual synonyms ("revenue" for a column named "sales") won't match.
