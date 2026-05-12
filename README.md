# Data Visualization MCP Server

An MCP server that lets clients such as LLMs upload data, define visualizations, and retrieve resutlts as part of a contextual workflow. Built in Python using FastMCP, pandas, matplotlib, and Plotly.

VIDEO DEMO LINK: https://youtu.be/6PMSBd1--Wo 

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

Transform operations (filter, aggregate, sort, select) always return a new dataset with a new ID. The original is never modified. This allows you to branch off in multiple directions from the same original data without worrying about corrupting it.

### Matplotlib vs Plotly

Matplotlib handles the regular PNG and then plotly handles interactive HTML. Matplotlib has no JavaScript dependencies and produces images that embed naturally in Claude's chat UI. Plotly  produces interactive charts for web use but requires bundling ~3MB of JavaScript. Had Claude help with this and still doesn't work that well.

---

## Simplifications and Tradeoffs 

**Single-user.** The server assumes only one trusted client. There is no concept of users or access control so any client that can reach the server can read and modify all data.

**Only tested with Claude desktop as client** Have not attempted testing with other non LLM clients.

**CSV-only input.** I only have it working assuming that all datasets are CSVs. Have not extended to support for JSON, Excel, APIs, etc. Chose CSV for simplicity and because requires no additional dependencies. The tradeoff though is file size and read speed for large datasets. 

**In-memory at runtime.** All datasets load into RAM on startup and stay there. This was fine for the small demonstration datasets I was using but would not work for very large files. I also only had time to test on a handful of datasets that were very small.

**Plotly HTML size.** Self-contained Plotly HTML bundles the entire plotting library. MCP has a 1MB limit on tool results, so returning HTML inline was never going to work. The server just writes it to a temp file and returns the path. As result though the file is only accessible locally so you can't easily share it without copying the file. An alternative would be to serve the HTML via a local HTTP endpoint, but didn't try attempting that. 

---

### Biggest issues 

**suggest_vizspec redundant for LLM clients.** I was originally trying to build suggest_vizspec to let clients describe visualizations in plain English. But once I decided to use an LLM as my client it already does natural language understanding better than any regex. So the tool would only be helpful for non-LLM clients which I never ended up testing. So I kind of ending up abandoning developing this tool but figured might has well just leave it in.

**No validation of chart quality.** The server will try to execute what it is asked without any sense of whether the result will be meaningful. A smarter server would warn when a requested chart type is not fit for the data.

**Data stays in memory forever.** Once a dataset is loaded it stays in _dataset_frames until the server process exits. I don't have a way to delete a dataset or free memory so for a long-running server processing a bunch of large files this would not be good.

**Limited plot types and very simple ones** Didn't have time to make visualizations more appealing or supportive for more complex data. Same with HTML piece I was more just focused on seeing if could get something working first!

-----

### Reflection on whether this is something that LLMs are helpful with

Does this tool make it easier to quickly generate visualizations, or is integrating an LLM into this a waste of time? (include details on your solution, i.e. where it struggles, where it is faster than normal, and how you think your design decisions played into that)

I think it definitely depends on what you're asking the system to do and how much more built out it is. For the version I have working right now integrating an LLM definitely speeds the process.
For example, doing something like generating a chart of "total marketing spend per customer by city" requires four steps to aggregate marketing spend by city, aggregate customers by city, join or divide those results, then plot. Without an LLM it would require the user to know and do each step at a time, which was actually how I was originally testing things using MCP Inspector. With Claude Desktop as the client though you just ask the one question and Claude figures out the sequence of which order of tools to call and reasons about the results along the way. I think having the describe_dataset tool was actually important for this since without it Claude would be guessing at column names. 

The decision of separating the vizspec step from actual generation step is also useful for LLM clients. It lets Claude inspect a spec, and then if there's a problem it realizes and calls update_vizspec and re-renders without starting over. In a more stateless design, every correction would require recreating the whole spec from scratch. Also If the server had a single high-level tool, the LLM would just be a natural language wrapper with no ability to adapt or reason about intermediate state. So the step by step design means you can actually take advantage of the LLM's thinking skills.

That said the LLM is still very limited in that it can’t see the produced visualization and so has no way to verify that it matches what was intended (I think). You can see this with the month ordering problem where charts with months on the x-axis appear alphabetically (Apr, Aug, Dec...) instead of chronologically unless the data happens to be pre-sorted. A human using matplotlib would see this immediately and fix it where Claude can’t.

Finally if you give it the same prompt twice, Claude might call tools in a different order and ultimately produce a slightly different chart. The server itself is deterministic in that the same tool calls always produce the same result but the LLM layer above it is not so this adds an aspect of unpredictability that could definitely be a problem depending on how you're using it.

-----

### Learning process

Background Research

Explored [What is the Model Context Protocol (MCP)?](https://modelcontextprotocol.io/docs/getting-started/intro) to research what exactly is an MCP, how they work, tools vs resources, etc
- Read through their tutorial on building an mcp server https://modelcontextprotocol.io/docs/develop/build-server 
- Looked at their GitHub - https://github.com/modelcontextprotocol/python-sdk 
- Explored reference test server with prompts, resources, and tools https://github.com/modelcontextprotocol/servers/tree/main/src/everything  
    - Specifically looked at file structure, how the different tools were registered and organized

First steps
- Started by thinking about what resources wanted specifically for the server to expose and the first tools I wanted to implement. Also wanted to think about how a client would refer to a dataset it uploaded earlier.
- Started drafting Design doc (see for better description of setup)
- Some key decisions:
    - Everything gets a unique ID (ex ds_123 or vs_123 for a visualization) so clients can refer to things across turns
    - resources are immutable
    - datasets in a python dictionary while the server is running

Setup 

MCP protocol layer
The server exposes tools (functions client can call) and resources (data client can read).
I used the python library FastMCP so that I could define MCP resources and tooling with intuitive Python decorators, as in https://modelcontextprotocol.io/docs/develop/build-server.

The server runs over stdio. Claude Desktop (using for the client) launches it as a subprocess and talks to it through standard input/output. Restarting Claude Desktop restarts the server.


Data model

I have Python classes that define every piece of data the server works with (see design doc)
Dataset: describes what was uploaded, stores metadata like ID, name, column names and types, row count
VizSpec: visualization instructions, stores which dataset id, what plot type, which columns, optional styling
Plot: records an output, links back to its VizSpec, stores the PNG bytes and optional HTML


Memory Storing

Made a class ResourceStore to hold everything while the server is running. It’s basically a wrapper class around Python dictionaries. Every tool imports the same singleton instance so they all share state. (This works until you restart the server and everything is gone. Later on I tried adding a persistence feature to solve this. Haven’t confirmed it’s working yet)

Also note: There are two separate dataset dictionaries. _datasets holds the Dataset object with metadata like name, column names, row count. _dataset_frames holds the actual pandas DataFrame with the raw rows and values. I originally had just one dictionary but then had to make them separate because Dataset is a Pydantic model and Pydantic can't serialize a DataFrame. So they have to be in parallel and share the same ID as the key. (Claude helped me debug this issue and suggested this approach!). 

see design doc for specifics on the different tools
