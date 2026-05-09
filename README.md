# Data Visualization MCP Server

An MCP server that lets clients such as LLMs upload data, define visualizations, and retrieve resutlts as part of a contextual workflow. Built in Python using FastMCP, pandas, matplotlib, and Plotly.

---

## What it does

A client (ie Claude Desktop) can:

1. Upload a CSV dataset by file path or raw string
2. Inspect it by exploring column types, stats, value distributions
3. Transform it with tools to filter rows, aggregate, sort, select columns
4. Define a visualization (plot type, axes, grouping, styling)
5. Render it and get a static PNG inline or an interactive HTML file

State persists across server restarts via SQLite and CSV files on disk.

---

## Design choices and assumptions

### Object IDs

Every object the server creates such as datasets, vizspecs, plots all gets a unique ID. Tools return IDs, and subsequent calls pass those IDs in. The server never infers what dataset a client wants so if they want something created earlier, have to tell the server its ID.

I mainly chose to do this so things were easier to debug in beginning since you can see pretty clearly what happened just looking at the sequence of IDs that flowed through a conversation.

### VizSpec vs rendering

Creating a VizSpec doesn't actually produce a chart it just records what chart the client wants. I made the rendering part its own seperate step so that the  spec can be inspected and updated without having to starting over, and also the same spec can produce both a PNG and an HTML output from one stored definition.

### Immutable datasets

Transform operations (filter, aggregate, sort, select) always return a new dataset with a new ID. The original is never modified. This allows workflows where you can branch off in multiple directions from the same source data without worrying about corrupting it.

### Two rendering backends

Matplotlib handles static PNG and then plotly handles interactive HTML. Matplotlib has no JavaScript dependencies and produces images that embed naturally in Claude's chat UI. Plotly I added later to produce interactive charts for web use but requires bundling ~3MB of JavaScript. Had Claude help with this and still doesn't work that well.

---

## Simplification and Tradeoffs 

**Single-user.** The server assumes only one trusted client. There is no concept of users, or access control. Any client that can reach the server can read and modify all data.

**Only tested with Claude desktop as client** Have not attempted testing with other non LLM clients.

**CSV-only input.** Datasets must be CSV. Have not extended to support for JSON, Excel, APIs, etc. Chose CSV for simplicity and because requires no additional dependencies (Parquet needs pyarrow). Trradeoff is file size and read speed for large datasets. 

**In-memory at runtime.** All datasets load into RAM on startup and stay there. There is no lazy loading or eviction. This is fine for demonstration-scale datasets but would not work for very large files or many concurrent datasets. I also only had time to test on a handful of datasets that were very small.

**Plotly HTML size.** Self-contained Plotly HTML bundles the entire plotting library. MCP has a 1MB limit on tool results, so returning HTML inline was never going to work. The server just writes it to a temp file and returns the path. As result though the file is only accessible locally so you can't easily share it without copying the file. An alternative would be to serve the HTML via a local HTTP endpoint, but didn't try attempting that. 

---

## Biggest issues 

**suggest_vizspec redundant for LLM clients.** I was originally trying to build suggest_vizspec to let clients describe visualizations in plain English. But once I decided to use an LLM as my client it already does natural language understanding better than any regex. So the tool would only be helpful for non-LLM clients which I never ended up testing. So I kind of ending up abandoning developing this function but figured might has well just leave it in.

**No validation of chart quality.** The server will try to execute what it is asked without any sense of whether the result will be meaningful. A smarter server would warn when a requested chart type is ill-suited to the data.

**Data stays in memory forever.** Once a dataset is loaded, it stays in `_dataset_frames` until the server process exits. There is no way to delete a dataset or free memory so for a long-running server processing a bunch of large files this would not be good.

**Limited plot types and very simple ones** Didn't have time to make visualizations more appealing or supportive for more complex data. Same with HTML piece I was more just focused on seeing if could get something working first!