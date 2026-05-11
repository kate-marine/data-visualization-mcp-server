from __future__ import annotations

import io

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_viz_mcp.models import PlotType, VizSpec


def _check_columns(df: pd.DataFrame, *cols: str | None) -> None:
    for col in cols:
        if col and col not in df.columns:
            raise ValueError(f"Column '{col}' not found in dataset data")


def render_to_png(df: pd.DataFrame, spec: VizSpec) -> bytes:
    _check_columns(df, spec.x_column, spec.y_column)

    color = spec.color or None
    fig, ax = plt.subplots(figsize=(8, 5))

    if spec.plot_type == PlotType.LINE:
        if spec.color_by:
            for grp_val, grp_df in df.groupby(spec.color_by):
                ax.plot(grp_df[spec.x_column], grp_df[spec.y_column], label=str(grp_val))  # type: ignore[index]
            ax.legend(title=spec.color_by)
        else:
            ax.plot(df[spec.x_column], df[spec.y_column], color=color)  # type: ignore[index]

    elif spec.plot_type == PlotType.AREA:
        if spec.color_by:
            for grp_val, grp_df in df.groupby(spec.color_by):
                xs = range(len(grp_df))
                ax.fill_between(xs, grp_df[spec.y_column], alpha=0.4, label=str(grp_val))  # type: ignore[index]
            ax.legend(title=spec.color_by)
        else:
            ax.fill_between(range(len(df)), df[spec.y_column], alpha=0.6, color=color)  # type: ignore[index]
            ax.plot(range(len(df)), df[spec.y_column], color=color)  # type: ignore[index]
            ax.set_xticks(range(len(df)))
            ax.set_xticklabels(df[spec.x_column], rotation=45, ha="right")  # type: ignore[index]

    elif spec.plot_type == PlotType.BAR:
        if spec.color_by:
            pivot = df.pivot_table(
                index=spec.x_column, columns=spec.color_by,
                values=spec.y_column, aggfunc="sum",
            )
            x_pos = np.arange(len(pivot))
            n = len(pivot.columns)
            width = 0.8 / n
            for i, col in enumerate(pivot.columns):
                ax.bar(x_pos + i * width - 0.4 + width / 2, pivot[col], width, label=str(col))
            ax.set_xticks(x_pos)
            ax.set_xticklabels(pivot.index, rotation=45, ha="right")
            ax.legend(title=spec.color_by)
        else:
            ax.bar(df[spec.x_column], df[spec.y_column], color=color)  # type: ignore[index]
            plt.xticks(rotation=45, ha="right")

    elif spec.plot_type == PlotType.SCATTER:
        if spec.color_by:
            for grp_val, grp_df in df.groupby(spec.color_by):
                ax.scatter(grp_df[spec.x_column], grp_df[spec.y_column], label=str(grp_val))  # type: ignore[index]
            ax.legend(title=spec.color_by)
        else:
            ax.scatter(df[spec.x_column], df[spec.y_column], color=color)  # type: ignore[index]

    elif spec.plot_type == PlotType.HISTOGRAM:
        ax.hist(df[spec.x_column], color=color, edgecolor="white")  # type: ignore[index]

    elif spec.plot_type == PlotType.BOX:
        if spec.x_column:
            groups = [grp[spec.y_column].dropna().values for _, grp in df.groupby(spec.x_column)]  # type: ignore[index]
            labels = df[spec.x_column].unique().tolist()  # type: ignore[index]
            ax.boxplot(groups, tick_labels=labels, patch_artist=True,
                       boxprops=dict(facecolor=color or "steelblue", alpha=0.7))
        else:
            ax.boxplot(df[spec.y_column].dropna().values, patch_artist=True,  # type: ignore[index]
                       boxprops=dict(facecolor=color or "steelblue", alpha=0.7))

    elif spec.plot_type == PlotType.VIOLIN:
        if spec.x_column:
            groups = [grp[spec.y_column].dropna().values for _, grp in df.groupby(spec.x_column)]  # type: ignore[index]
            labels = df[spec.x_column].unique().tolist()  # type: ignore[index]
            parts = ax.violinplot(groups, showmedians=True)
            ax.set_xticks(range(1, len(labels) + 1))
            ax.set_xticklabels(labels)
        else:
            parts = ax.violinplot([df[spec.y_column].dropna().values], showmedians=True)  # type: ignore[index]
        if color:
            for pc in parts["bodies"]:  # type: ignore[index]
                pc.set_facecolor(color)

    elif spec.plot_type == PlotType.PIE:
        wedges, texts, autotexts = ax.pie(
            df[spec.y_column],  # type: ignore[index]
            labels=df[spec.x_column],  # type: ignore[index]
            autopct="%1.1f%%",
            colors=[color] if color else None,
        )
        ax.axis("equal")

    elif spec.plot_type == PlotType.HEATMAP:
        numeric_df = df.select_dtypes(include="number")
        if numeric_df.empty:
            raise ValueError("No numeric columns available for heatmap correlation matrix")
        corr = numeric_df.corr()
        im = ax.imshow(corr.values, aspect="auto", vmin=-1, vmax=1, cmap="coolwarm")
        fig.colorbar(im, ax=ax)
        ax.set_xticks(range(len(corr.columns)))
        ax.set_yticks(range(len(corr.columns)))
        ax.set_xticklabels(corr.columns, rotation=45, ha="right")
        ax.set_yticklabels(corr.columns)
        for i in range(len(corr)):
            for j in range(len(corr.columns)):
                ax.text(j, i, f"{corr.iloc[i, j]:.2f}", ha="center", va="center", fontsize=8)

    if spec.title:
        ax.set_title(spec.title)
    if spec.plot_type not in (PlotType.PIE, PlotType.HEATMAP):
        ax.set_xlabel(spec.x_label or (spec.x_column or ""))
        if spec.y_column:
            ax.set_ylabel(spec.y_label or spec.y_column)

    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read()
