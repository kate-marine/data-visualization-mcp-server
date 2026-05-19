# Demo Script — Data Visualization MCP Server

**Dataset:** Brew & Beyond Coffee Co. — 6 cities, 12 months, 72 rows
**File:** `/Users/katemarine/Documents/data-visualization-mcp/demo/coffee_chain.csv`
**Columns:** city, month, quarter, revenue, customers, avg_order, rating, marketing_spend

The data tells a story: Austin is exploding, Portland is a high-margin boutique,
New York is a turnaround in progress, Boston is underperforming.

---

## Step 1 — Load the dataset

**Say:**
> "This uses tool I built `upload_dataset_from_path` that reads a CSV directly from a file path. Instead of pasting raw data into the chat, you cant just give it a path. The server reads it with pandas, figures out the column types, and stores it in memory with a unique ID. Then that ID is how every future tool call refers back to this data."

**Prompt:**
```
Load the CSV at /Users/katemarine/Documents/data-visualization-mcp/demo/coffee_chain.csv
```

---

## Step 2 — Describe the dataset

**Say:**
> "This is calling the `describe_dataset` tool. So for numeric columns you get mean, min, max, and standard deviation. And then for categorical columns you get the number of unique values and the most frequent ones. And obviously an LLM like Claude can do this itself but guessing but if u weren't using an LLM as the client then this tool would be more useful"

**Prompt:**
```
Describe that dataset. What are the key statistics for each column?
```

**Say after:**
> "Notice that avg_order has two clusters — Portland is around $25, everyone else is $20-23. That's already hinting at an interesting story before we've plotted anything. Claude can read these stats and use them to make better decisions about how to visualize the data."

---

## Step 3 — Bar chart: total revenue by city

**Say:**
> "Ok so then for the actual  visualizations. When I ask for total revenue by city, Claude doesn't just call one tool — it actually chains together a couple. So it first calls `aggregate_dataset` to sum revenue grouped by city, and this produces a new derived dataset. Then it calls `create_vizspec` to define the chart — with like which columns go on which axis, what plot type. Then it calls `generate_plot` to actually render it. I never told it to do any of that so that's kind of the beauty of using an LLM client where it can figure out the sequence on its own without me having to do each step manually which is how i was initially testing everything.

**Prompt:**
```
Show me a bar chart of total revenue by city.
```

**Say after:**
> "One of my key design decisions was that doing any kind of transforming always produce a new dataset rather than modifying the original. So the aggregated data is a brand new object with its own ID. That way the original dataset is untouched and still available to refer back to"

---

## Step 4 — Line chart: Austin's growth

**Say:**
> "This is just an example of using the `filter_dataset` tool where it keeps only rows where city equals Austin and returns another new dataset. Then it plots revenue over month. And yea again The filtered Austin dataset exists alongside the full dataset, not instead of it."

**Prompt:**
```
Show me a line chart of Austin's monthly revenue trend.
```

**Say after:**
> "That climb from $28K in January to nearly $65K in December — that's the story. And again, everything is non-destructive. The filtered Austin dataset exists alongside the full dataset, not instead of it."

---

## Step 5 — Multi-series line chart: all cities

**Say:**
> "Ok so this part actually required a decision changes with the server side. Basically I wanted to allow for plotting multiple things on the same chart. So how it works is The VizSpec — which is the object that stores the chart instructions — has a field called `color_by`. And When you set it to a column name, it splits the data into one series per value in that column. In matplotlib it means iterating over groups and plotting each one separately."

**Prompt:**
```
Plot the monthly revenue trend for all cities on a line chart, grouped by city.
```

**Say after:**
> "You can see Austin catching Seattle, New York ramping up from a low base, and Boston nearly flat across the whole year. This would've taken quite a few lines of matplotlib code to produce manually."

---

## Step 6 — Scatter plot: Portland's secret

**Say:**
> "This one I find really interesting. I'm going to ask for a scatter plot of customers versus revenue across all rows. I'm not going to tell it anything about Portland — I want to see if the chart surfaces the story on its own."

**Prompt:**
```
Make a scatter plot of customers vs revenue across all rows.
```

**Say after:**
> "See that cluster of points in the lower left with revenue that's higher than you'd expect for the customer count? That's Portland. They serve fewer people than anyone else but charge $25 per order versus $20 everywhere else. High-margin boutique strategy — visible in one chart without any filtering. That's the kind of thing exploratory visualization is for."

