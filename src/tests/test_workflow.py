"""
TESTING FILE WRITTEN BY CLAUDE

Tests the full end-to-end workflow 
"""
import json
import tempfile
from pathlib import Path

from data_viz_mcp.tools.datasets import get_dataset, list_datasets, upload_dataset, upload_dataset_from_path
from data_viz_mcp.tools.plots import generate_plot, get_plot, list_plots
from data_viz_mcp.tools.specs import create_vizspec, get_vizspec
from data_viz_mcp.server import store


CSV = "month,revenue\nJan,100\nFeb,150\nMar,120"


def _fresh_store():
    from data_viz_mcp.server import store
    store._datasets.clear()
    store._dataset_frames.clear()
    store._vizspecs.clear()
    store._plots.clear()
    store._plot_png.clear()
    store._plot_html.clear()


def test_full_workflow():
    _fresh_store()

    # US1: upload
    raw = upload_dataset(name="sales", csv_data=CSV)
    ds_result = json.loads(raw)
    assert not ds_result.get("error"), ds_result
    ds_id = ds_result["id"]
    assert ds_id.startswith("ds_")
    assert ds_result["row_count"] == 3
    assert len(ds_result["columns"]) == 2

    # US1: list
    raw = list_datasets()
    datasets = json.loads(raw)
    assert any(d["id"] == ds_id for d in datasets)

    # US1: get
    raw = get_dataset(id=ds_id)
    detail = json.loads(raw)
    assert detail["id"] == ds_id
    assert "preview" in detail

    # US2: create spec
    raw = create_vizspec(dataset_id=ds_id, plot_type="line", x_column="month", y_column="revenue", title="Monthly Revenue")
    spec_result = json.loads(raw)
    assert not spec_result.get("error"), spec_result
    spec_id = spec_result["id"]
    assert spec_id.startswith("vs_")

    # US2: get spec
    raw = get_vizspec(id=spec_id)
    spec_detail = json.loads(raw)
    assert spec_detail["id"] == spec_id
    assert spec_detail["plot_type"] == "line"

    # US3: generate plot
    contents = generate_plot(spec_id=spec_id)
    assert len(contents) == 2
    meta = json.loads(contents[0].text)
    assert not meta.get("error"), meta
    plot_id = meta["id"]
    assert plot_id.startswith("pl_")
    assert contents[1].type == "image"
    assert len(contents[1].data) > 0

    # US3: get plot
    retrieved = get_plot(id=plot_id)
    assert retrieved[0].type == "image"
    assert retrieved[0].data == contents[1].data

    # US3: generate again → new ID (immutability)
    contents2 = generate_plot(spec_id=spec_id)
    meta2 = json.loads(contents2[0].text)
    assert meta2["id"] != plot_id

    # US3: list plots → two entries
    raw = list_plots()
    plots = json.loads(raw)
    assert len(plots) == 2


def test_upload_dataset_from_path():
    _fresh_store()
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        f.write("x,y\n1,2\n3,4\n")
        tmp_path = f.name

    # name defaults to file stem
    result = json.loads(upload_dataset_from_path(path=tmp_path))
    assert not result.get("error"), result
    assert result["id"].startswith("ds_")
    assert result["row_count"] == 2
    assert result["name"] == Path(tmp_path).stem

    # explicit name overrides stem
    result2 = json.loads(upload_dataset_from_path(path=tmp_path, name="my dataset"))
    assert result2["name"] == "my dataset"

    # missing file
    result3 = json.loads(upload_dataset_from_path(path="/nonexistent/file.csv"))
    assert result3["error"] is True
    assert "not found" in result3["reason"]

    # non-csv extension
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f2:
        f2.write(b"x,y\n1,2\n")
        txt_path = f2.name
    result4 = json.loads(upload_dataset_from_path(path=txt_path))
    assert result4["error"] is True
    assert "CSV" in result4["reason"]
