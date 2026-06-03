"""End-to-end API tests: import a dataset, inspect it, and fit a PCA from it."""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from scorepilot.app import create_app
from scorepilot.config import Settings


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _frame() -> pd.DataFrame:
    rng = np.random.default_rng(1)
    latent = rng.normal(size=(30, 2))
    loadings = rng.normal(size=(2, 4))
    x = latent @ loadings + 0.05 * rng.normal(size=(30, 4))
    frame = pd.DataFrame(x, columns=[f"v{i}" for i in range(4)])
    frame.insert(0, "sample", [f"obs{i}" for i in range(30)])
    return frame


def _csv_bytes() -> bytes:
    return _frame().to_csv(index=False).encode()


def _upload_csv(client: TestClient) -> dict:
    response = client.post(
        "/api/datasets",
        files={"file": ("data.csv", io.BytesIO(_csv_bytes()), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_upload_returns_detail(client: TestClient) -> None:
    body = _upload_csv(client)
    assert body["n_rows"] == 30
    assert body["n_columns"] == 5
    assert [c["name"] for c in body["columns"]] == ["sample", "v0", "v1", "v2", "v3"]
    # The unique text column is auto-detected as the primary identifier.
    assert body["primary_id"] == "sample"
    types = {c["name"]: c["column_type"] for c in body["columns"]}
    assert types["sample"] == "qualitative"
    assert types["v0"] == "quantitative"


def test_excel_upload(client: TestClient) -> None:
    buffer = io.BytesIO()
    _frame().to_excel(buffer, index=False)
    response = client.post(
        "/api/datasets",
        files={
            "file": (
                "data.xlsx",
                io.BytesIO(buffer.getvalue()),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source"] == "excel"
    assert body["n_rows"] == 30


def test_list_and_get_dataset(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    listing = client.get("/api/datasets").json()
    assert any(d["dataset_id"] == dataset_id for d in listing)
    detail = client.get(f"/api/datasets/{dataset_id}").json()
    assert detail["dataset_id"] == dataset_id


def test_patch_column_role_and_type(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    response = client.patch(
        f"/api/datasets/{dataset_id}/columns/v0",
        json={"identifier_role": "secondary"},
    )
    assert response.status_code == 200, response.text
    cols = {c["name"]: c for c in response.json()["columns"]}
    assert cols["v0"]["identifier_role"] == "secondary"


def test_fit_pca_end_to_end(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    response = client.post(
        "/api/models/pca",
        json={"dataset_id": dataset_id, "n_components": 2},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["kind"] == "PCA"
    assert body["model_id"] >= 1
    assert body["component_names"] == ["PC1", "PC2"]
    assert len(body["scores"]["data"]) == 30
    assert len(body["explained_variance"]) == 2
    assert body["r2_cumulative"][-1] > 0.95
    assert body["t2_limit"] > 0


def test_fit_pca_with_explicit_spec_and_transform(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    response = client.post(
        "/api/models/pca",
        json={
            "dataset_id": dataset_id,
            "n_components": 2,
            "spec": {
                "x_columns": ["v0", "v1", "v2", "v3"],
                "excluded_rows": [0, 1, 2],
                "transforms": {"v0": {"kind": "none"}},
            },
        },
    )
    assert response.status_code == 201, response.text
    # Three observations were excluded.
    assert len(response.json()["scores"]["data"]) == 27


def test_fit_pca_unknown_dataset_is_404(client: TestClient) -> None:
    response = client.post(
        "/api/models/pca",
        json={"dataset_id": "does-not-exist", "n_components": 2},
    )
    assert response.status_code == 404


def test_fit_pca_too_many_components_is_422(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    response = client.post(
        "/api/models/pca",
        json={"dataset_id": dataset_id, "n_components": 99},
    )
    assert response.status_code == 422


def test_spa_fallback_serves_index(client: TestClient) -> None:
    response = client.get("/some/client/route")
    assert response.status_code == 200
    assert "ScorePilot" in response.text
