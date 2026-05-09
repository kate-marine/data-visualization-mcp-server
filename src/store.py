from __future__ import annotations

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd

from data_viz_mcp.models import ColumnInfo, Dataset, Plot, PlotType, VizSpec

if TYPE_CHECKING:
    pass

_DEFAULT_DATA_DIR = Path.home() / ".local" / "share" / "data-viz-mcp"

_CREATE_DATASETS = """
CREATE TABLE IF NOT EXISTS datasets (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    columns_json TEXT NOT NULL,
    row_count   INTEGER NOT NULL,
    created_at  TEXT NOT NULL
)
"""

_CREATE_VIZSPECS = """
CREATE TABLE IF NOT EXISTS vizspecs (
    id          TEXT PRIMARY KEY,
    dataset_id  TEXT NOT NULL,
    plot_type   TEXT NOT NULL,
    x_column    TEXT,
    y_column    TEXT,
    title       TEXT,
    x_label     TEXT,
    y_label     TEXT,
    color       TEXT,
    color_by    TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
)
"""


class ResourceStore:
    def __init__(self, data_dir: Path | str | None = None) -> None:
        self._datasets: dict[str, Dataset] = {}
        self._dataset_frames: dict[str, pd.DataFrame] = {}
        self._vizspecs: dict[str, VizSpec] = {}
        self._plots: dict[str, Plot] = {}
        self._plot_png: dict[str, bytes] = {}
        self._plot_html: dict[str, str] = {}

        resolved = data_dir or os.environ.get("DATA_VIZ_MCP_DATA_DIR") or _DEFAULT_DATA_DIR
        self._data_dir = Path(resolved)
        self._frames_dir = self._data_dir / "frames"
        self._db_path = self._data_dir / "metadata.db"
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._frames_dir.mkdir(exist_ok=True)
        self._init_db()
        self._load_all()

    # --- internal persistence helpers ---

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.execute(_CREATE_DATASETS)
            conn.execute(_CREATE_VIZSPECS)
            # Migrate: add color_by if this is an older database that predates it
            cols = {row[1] for row in conn.execute("PRAGMA table_info(vizspecs)")}
            if "color_by" not in cols:
                conn.execute("ALTER TABLE vizspecs ADD COLUMN color_by TEXT")

    def _load_all(self) -> None:
        with self._conn() as conn:
            for row in conn.execute(
                "SELECT id, name, columns_json, row_count, created_at FROM datasets"
            ):
                id_, name, cols_json, row_count, created_at = row
                frame_path = self._frames_dir / f"{id_}.csv"
                if not frame_path.exists():
                    continue
                cols = [ColumnInfo(**c) for c in json.loads(cols_json)]
                ds = Dataset(
                    id=id_, name=name, columns=cols, row_count=row_count,
                    created_at=datetime.fromisoformat(created_at),
                )
                self._datasets[id_] = ds
                self._dataset_frames[id_] = pd.read_csv(frame_path)

            for row in conn.execute(
                "SELECT id, dataset_id, plot_type, x_column, y_column, "
                "title, x_label, y_label, color, color_by, created_at, updated_at FROM vizspecs"
            ):
                (id_, ds_id, plot_type, x_col, y_col,
                 title, x_label, y_label, color, color_by, created_at, updated_at) = row
                if ds_id not in self._datasets:
                    continue
                spec = VizSpec(
                    id=id_, dataset_id=ds_id, plot_type=PlotType(plot_type),
                    x_column=x_col, y_column=y_col, title=title,
                    x_label=x_label, y_label=y_label, color=color, color_by=color_by,
                    created_at=datetime.fromisoformat(created_at),
                    updated_at=datetime.fromisoformat(updated_at),
                )
                self._vizspecs[id_] = spec

    def _persist_dataset(self, ds: Dataset, df: pd.DataFrame) -> None:
        df.to_csv(self._frames_dir / f"{ds.id}.csv", index=False)
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO datasets
                   (id, name, columns_json, row_count, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (ds.id, ds.name,
                 json.dumps([c.model_dump() for c in ds.columns]),
                 ds.row_count, ds.created_at.isoformat()),
            )

    def _persist_vizspec(self, spec: VizSpec) -> None:
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO vizspecs
                   (id, dataset_id, plot_type, x_column, y_column, title,
                    x_label, y_label, color, color_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (spec.id, spec.dataset_id, spec.plot_type.value,
                 spec.x_column, spec.y_column, spec.title,
                 spec.x_label, spec.y_label, spec.color, spec.color_by,
                 spec.created_at.isoformat(), spec.updated_at.isoformat()),
            )

    # --- public ID generation ---

    def new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex}"

    # --- Dataset ---

    def add_dataset(self, dataset: Dataset, df: pd.DataFrame) -> None:
        self._datasets[dataset.id] = dataset
        self._dataset_frames[dataset.id] = df
        self._persist_dataset(dataset, df)

    def get_dataset(self, id: str) -> tuple[Dataset, pd.DataFrame] | None:
        ds = self._datasets.get(id)
        if ds is None:
            return None
        return ds, self._dataset_frames[id]

    def list_datasets(self) -> list[Dataset]:
        return list(self._datasets.values())

    # --- VizSpec ---

    def add_vizspec(self, spec: VizSpec) -> None:
        self._vizspecs[spec.id] = spec
        self._persist_vizspec(spec)

    def get_vizspec(self, id: str) -> VizSpec | None:
        return self._vizspecs.get(id)

    def update_vizspec(self, id: str, **fields: object) -> VizSpec | None:
        spec = self._vizspecs.get(id)
        if spec is None:
            return None
        updated = spec.model_copy(update=fields)
        self._vizspecs[id] = updated
        self._persist_vizspec(updated)
        return updated

    def list_vizspecs(self) -> list[VizSpec]:
        return list(self._vizspecs.values())

    # --- Plot (not persisted — derived from datasets + specs) ---

    def add_plot(self, plot: Plot, png_data: bytes, html_data: str | None) -> None:
        self._plots[plot.id] = plot
        self._plot_png[plot.id] = png_data
        if html_data is not None:
            self._plot_html[plot.id] = html_data

    def get_plot(self, id: str) -> tuple[Plot, bytes, str | None] | None:
        plot = self._plots.get(id)
        if plot is None:
            return None
        return plot, self._plot_png[id], self._plot_html.get(id)

    def list_plots(self) -> list[Plot]:
        return list(self._plots.values())
