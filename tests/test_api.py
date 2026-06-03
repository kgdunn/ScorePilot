"""End-to-end API tests: upload a CSV, then fit a PCA from it."""

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


def _csv_bytes() -> bytes:
    rng = np.random.default_rng(1)
    latent = rng.normal(size=(30, 2))
    loadings = rng.normal(size=(2, 4))
    x = latent @ loadings + 0.05 * rng.normal(size=(30, 4))
    frame = pd.DataFrame(
        x,
        columns=[f"v{i}" for i in range(4)],
        index=pd.Index([f"obs{i}" for i in range(30)], name="sample"),
    )
    return frame.to_csv().encode()


def _upload(client: TestClient) -> str:
    response = client.post(
        "/api/datasets",
        files={"file": ("data.csv", io.BytesIO(_csv_bytes()), "text/csv")},
    )
    assert response.status_code == 201, response.text
    return response.json()["dataset_id"]


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_upload_returns_summary(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": ("data.csv", io.BytesIO(_csv_bytes()), "text/csv")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["n_rows"] == 30
    assert body["n_columns"] == 4
    assert body["columns"] == ["v0", "v1", "v2", "v3"]
    assert isinstance(body["dataset_id"], str)


def test_fit_pca_end_to_end(client: TestClient) -> None:
    dataset_id = _upload(client)

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
    assert len(body["scores"]["data"][0]) == 2
    assert len(body["explained_variance"]) == 2
    assert body["r2_cumulative"][-1] > 0.95
    assert body["t2_limit"] > 0


def test_fit_pca_unknown_dataset_is_404(client: TestClient) -> None:
    response = client.post(
        "/api/models/pca",
        json={"dataset_id": "does-not-exist", "n_components": 2},
    )
    assert response.status_code == 404


def test_fit_pca_too_many_components_is_422(client: TestClient) -> None:
    dataset_id = _upload(client)
    response = client.post(
        "/api/models/pca",
        json={"dataset_id": dataset_id, "n_components": 99},
    )
    assert response.status_code == 422


def test_spa_fallback_serves_index(client: TestClient) -> None:
    # An unknown non-API path should fall back to the SPA index.html.
    response = client.get("/some/client/route")
    assert response.status_code == 200
    assert "ScorePilot" in response.text
