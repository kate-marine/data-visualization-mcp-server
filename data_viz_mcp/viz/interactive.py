from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.figure_factory as ff

from data_viz_mcp.models import PlotType, VizSpec


def render_to_html(df: pd.DataFrame, spec: VizSpec) -> str:
    for col in ([spec.x_column] + ([spec.y_column] if spec.y_column else [])):
        if col and col not in df.columns:
            raise ValueError(f"Column '{col}' not found in dataset data")

    color_seq = [spec.color] if spec.color else None
    base: dict[str, object] = {"title": spec.title or ""}
    if color_seq:
        base["color_discrete_sequence"] = color_seq
    if spec.color_by:
        base["color"] = spec.color_by

    if spec.plot_type == PlotType.LINE:
        fig = px.line(df, x=spec.x_column, y=spec.y_column, **base)  # type: ignore[arg-type]

    elif spec.plot_type == PlotType.AREA:
        fig = px.area(df, x=spec.x_column, y=spec.y_column, **base)  # type: ignore[arg-type]

    elif spec.plot_type == PlotType.BAR:
        fig = px.bar(df, x=spec.x_column, y=spec.y_column, barmode="group", **base)  # type: ignore[arg-type]

    elif spec.plot_type == PlotType.SCATTER:
        fig = px.scatter(df, x=spec.x_column, y=spec.y_column, **base)  # type: ignore[arg-type]

    elif spec.plot_type == PlotType.HISTOGRAM:
        fig = px.histogram(df, x=spec.x_column, **base)  # type: ignore[arg-type]

    elif spec.plot_type == PlotType.BOX:
        fig = px.box(df, x=spec.x_column, y=spec.y_column, **base)  # type: ignore[arg-type]

    elif spec.plot_type == PlotType.VIOLIN:
        fig = px.violin(df, x=spec.x_column, y=spec.y_column, box=True, **base)  # type: ignore[arg-type]

    elif spec.plot_type == PlotType.PIE:
        fig = px.pie(df, names=spec.x_column, values=spec.y_column, title=spec.title or "")

    elif spec.plot_type == PlotType.HEATMAP:
        numeric_df = df.select_dtypes(include="number")
        if numeric_df.empty:
            raise ValueError("No numeric columns available for heatmap correlation matrix")
        corr = numeric_df.corr().round(2)
        fig = px.imshow(
            corr,
            text_auto=True,
            color_continuous_scale="RdBu_r",
            zmin=-1,
            zmax=1,
            title=spec.title or "Correlation Matrix",
        )

    else:
        raise ValueError(f"Unsupported plot type: {spec.plot_type}")

    if spec.x_label and spec.plot_type not in (PlotType.PIE, PlotType.HEATMAP):
        fig.update_xaxes(title_text=spec.x_label)
    if spec.y_label and spec.plot_type not in (PlotType.PIE, PlotType.HEATMAP):
        fig.update_yaxes(title_text=spec.y_label)

    return fig.to_html(full_html=True, include_plotlyjs=True)
