"""End-to-end API tests: import a dataset, inspect it, and fit a PCA from it."""

from __future__ import annotations

import io
import json
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


def test_upload_autodetects_datetime_and_categorical(client: TestClient) -> None:
    csv = (
        b"date,city,sales\n"
        b"2020-01-15,Paris,100\n"
        b"2020-02-20,Lyon,110\n"
        b"2020-03-25,Paris,95\n"
        b"2021-04-01,Nice,130\n"
    )
    response = client.post(
        "/api/datasets",
        files={"file": ("dates.csv", io.BytesIO(csv), "text/csv")},
    )
    assert response.status_code == 201, response.text
    types = {c["name"]: c["column_type"] for c in response.json()["columns"]}
    assert types["date"] == "datetime"
    assert types["city"] == "qualitative"
    assert types["sales"] == "quantitative"


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


def test_quality_endpoint(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    report = client.get(f"/api/datasets/{dataset_id}/quality").json()
    assert report["n_rows"] == 30
    assert report["primary_id_unique"] is True
    assert {c["name"] for c in report["columns"]} == {"sample", "v0", "v1", "v2", "v3"}


def test_grid_raw_and_scaled(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]

    raw = client.get(f"/api/datasets/{dataset_id}/grid?row_limit=5").json()
    assert raw["column_names"] == ["sample", "v0", "v1", "v2", "v3"]
    assert len(raw["cells"]) == 5
    assert raw["row_identifiers"][0] == "obs0"

    scaled = client.get(f"/api/datasets/{dataset_id}/grid?row_limit=5&form=scaled").json()
    # Scaling changes the numeric column values but not the identifier column.
    assert scaled["cells"][0][1] != raw["cells"][0][1]
    assert scaled["cells"][0][0] == raw["cells"][0][0]


def test_grid_scaled_applies_transforms(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    plain = client.get(f"/api/datasets/{dataset_id}/grid?row_limit=5&form=scaled").json()
    transforms = json.dumps({"v0": {"kind": "exponential", "c1": 0.0, "c2": 1.0}})
    transformed = client.get(
        f"/api/datasets/{dataset_id}/grid?row_limit=5&form=scaled&transforms={transforms}"
    ).json()
    # The transformed column (index 1) changes; the identifier (index 0) does not.
    assert transformed["cells"][0][1] != plain["cells"][0][1]
    assert transformed["cells"][0][0] == plain["cells"][0][0]


def test_grid_invalid_transforms_param_is_400(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    response = client.get(f"/api/datasets/{dataset_id}/grid?form=scaled&transforms=not-json")
    assert response.status_code == 400


def test_variable_inspector(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    inspector = client.get(f"/api/datasets/{dataset_id}/variables/v0").json()
    assert inspector["column_type"] == "quantitative"
    assert inspector["n"] == 30
    assert sum(inspector["histogram_counts"]) == 30
    assert len(inspector["sequence"]) == 30


def test_variable_inspector_excludes_rows(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    full = client.get(f"/api/datasets/{dataset_id}/variables/v0").json()
    trimmed = client.get(
        f"/api/datasets/{dataset_id}/variables/v0?excluded_rows=0&excluded_rows=1&excluded_rows=2"
    ).json()
    # Excluding three rows drops them from the stats and the sequence/plots.
    assert trimmed["n"] == full["n"] - 3
    assert len(trimmed["sequence"]) == len(full["sequence"]) - 3


def test_variable_inspector_scaled(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    scaled = client.get(f"/api/datasets/{dataset_id}/variables/v0?form=scaled").json()
    # Mean-centered, unit-variance scaling: mean is ~0 and std is ~1.
    assert abs(scaled["mean"]) < 1e-9
    assert abs(scaled["std"] - 1.0) < 1e-6
    # The sequence and histogram still cover every observation.
    assert len(scaled["sequence"]) == 30
    assert sum(scaled["histogram_counts"]) == 30


def test_variable_inspector_unknown_column_404(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    response = client.get(f"/api/datasets/{dataset_id}/variables/nope")
    assert response.status_code == 404


def test_fit_model_hangar_and_logbook(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]

    created = client.post(
        "/api/models",
        json={"dataset_id": dataset_id, "kind": "PCA", "n_components": 2, "name": "m1"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    model_id = body["summary"]["id"]
    assert body["summary"]["kind"] == "PCA"
    assert body["diagnostics"]["x_loadings"]["data"]
    assert len(body["diagnostics"]["ellipse_x"]) == 100

    hangar = client.get("/api/models").json()
    assert any(m["id"] == model_id for m in hangar)

    detail = client.get(f"/api/models/{model_id}").json()
    assert detail["summary"]["id"] == model_id
    assert detail["diagnostics"] is not None
    assert [s["id"] for s in detail["lineage"]] == [model_id]

    variant = client.post(
        "/api/models",
        json={
            "dataset_id": dataset_id,
            "kind": "PCA",
            "n_components": 2,
            "parent_id": model_id,
            "name": "m2",
        },
    )
    assert variant.status_code == 201, variant.text
    v = variant.json()
    assert v["summary"]["parent_id"] == model_id
    assert [s["id"] for s in v["lineage"]] == [model_id, v["summary"]["id"]]


def test_model_contributions(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    created = client.post(
        "/api/models", json={"dataset_id": dataset_id, "kind": "PCA", "n_components": 2}
    )
    model_id = created.json()["summary"]["id"]
    diag = created.json()["diagnostics"]

    obs = 3
    response = client.get(f"/api/models/{model_id}/contributions/{obs}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["observation"] == obs
    assert len(body["t2"]) == len(diag["x_loadings"]["variable_names"])
    assert len(body["spe"]) == len(body["variable_names"])
    # T2 contributions sum to the observation's Hotelling's T2.
    assert abs(sum(body["t2"]) - diag["hotellings_t2"][obs]) < 1e-6
    # SPE is the residual norm, so squared contributions sum to spe**2.
    assert abs(sum(v * v for v in body["spe"]) - diag["spe"][obs] ** 2) < 1e-6


def test_model_contributions_out_of_range_422(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    created = client.post(
        "/api/models", json={"dataset_id": dataset_id, "kind": "PCA", "n_components": 2}
    )
    model_id = created.json()["summary"]["id"]
    response = client.get(f"/api/models/{model_id}/contributions/9999")
    assert response.status_code == 422


def test_fit_pls_model(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    response = client.post(
        "/api/models",
        json={
            "dataset_id": dataset_id,
            "kind": "PLS",
            "n_components": 2,
            "spec": {"x_columns": ["v0", "v1"], "y_columns": ["v2", "v3"]},
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["diagnostics"]["y_loadings"] is not None


def test_fit_pls_without_y_is_422(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    response = client.post(
        "/api/models",
        json={"dataset_id": dataset_id, "kind": "PLS", "n_components": 2},
    )
    assert response.status_code == 422


def test_get_unknown_model_is_404(client: TestClient) -> None:
    assert client.get("/api/models/999").status_code == 404


def test_scores_use_primary_identifier_labels(client: TestClient) -> None:
    # The "sample" column (obs0..obs29) is the auto-detected primary identifier,
    # so scores and contributions are labelled with it, not positional integers.
    dataset_id = _upload_csv(client)["dataset_id"]
    created = client.post(
        "/api/models", json={"dataset_id": dataset_id, "kind": "PCA", "n_components": 2}
    )
    diag = created.json()["diagnostics"]
    assert diag["scores"]["observation_names"][:3] == ["obs0", "obs1", "obs2"]

    model_id = created.json()["summary"]["id"]
    contrib = client.get(f"/api/models/{model_id}/contributions/3").json()
    assert contrib["observation_name"] == "obs3"


def test_excluded_rows_keep_identifier_alignment(client: TestClient) -> None:
    # Excluding a row must not shift the remaining identifier labels.
    dataset_id = _upload_csv(client)["dataset_id"]
    created = client.post(
        "/api/models",
        json={
            "dataset_id": dataset_id,
            "kind": "PCA",
            "n_components": 2,
            "spec": {"x_columns": ["v0", "v1", "v2", "v3"], "excluded_rows": [0]},
        },
    )
    names = created.json()["diagnostics"]["scores"]["observation_names"]
    assert names[:3] == ["obs1", "obs2", "obs3"]


def test_auto_components_picks_count_by_cross_validation(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    # With auto_components the count is chosen by cross-validation, so it lands in
    # the valid range for the four quantitative columns rather than the typed value.
    created = client.post(
        "/api/models",
        json={
            "dataset_id": dataset_id,
            "kind": "PCA",
            "n_components": 2,
            "auto_components": True,
        },
    )
    assert created.status_code == 201, created.text
    n = created.json()["summary"]["n_components"]
    assert 1 <= n <= 4


def test_cross_validation_endpoint(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]
    created = client.post(
        "/api/models", json={"dataset_id": dataset_id, "kind": "PCA", "n_components": 3}
    )
    model_id = created.json()["summary"]["id"]
    cv = client.get(f"/api/models/{model_id}/cross-validation")
    assert cv.status_code == 200, cv.text
    body = cv.json()
    assert body["component_numbers"] == [1, 2, 3]
    assert len(body["r2"]) == len(body["q2"]) == 3
    assert 1 <= body["recommended"] <= 3
    assert body["target"] == "X"


def test_cross_validation_unknown_model_is_404(client: TestClient) -> None:
    assert client.get("/api/models/999/cross-validation").status_code == 404


def test_list_samples(client: TestClient) -> None:
    names = {s["name"] for s in client.get("/api/datasets/samples").json()}
    assert {
        "ldpe",
        "food-consumption",
        "raw-material-properties",
        "silicon-wafer-thickness",
        "solvents",
        "tablet-spectra",
    } <= names


def test_load_sample(client: TestClient) -> None:
    response = client.post("/api/datasets/samples/food-consumption")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["n_rows"] == 16
    # The unique "Country" column is auto-detected as the primary identifier.
    assert body["primary_id"] == "Country"


def test_load_gzipped_spectra_sample(client: TestClient) -> None:
    # tablet-spectra is bundled gzipped; loading it exercises the decompression
    # path and confirms a wide spectral table imports cleanly.
    response = client.post("/api/datasets/samples/tablet-spectra")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["n_rows"] == 460
    assert body["n_columns"] == 651
    assert body["primary_id"] == "Tablet"


def test_load_unknown_sample_is_404(client: TestClient) -> None:
    assert client.post("/api/datasets/samples/nope").status_code == 404


class _FakeUrlResponse:
    """Minimal stand-in for urllib's response, used to avoid real network I/O."""

    def __init__(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        self._data = data
        self._pos = 0
        self.headers = headers or {}

    def read(self, size: int = -1) -> bytes:
        end = len(self._data) if size is None or size < 0 else self._pos + size
        chunk = self._data[self._pos : end]
        self._pos += len(chunk)
        return chunk

    def __enter__(self) -> _FakeUrlResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def _stub_public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the SSRF guard treat every host as a public IP, without live DNS."""
    monkeypatch.setattr(
        "scorepilot.api.datasets._host_addresses",
        lambda _host: ["93.184.216.34"],
    )


def _stub_url_response(monkeypatch: pytest.MonkeyPatch, response: _FakeUrlResponse) -> None:
    monkeypatch.setattr(
        "scorepilot.api.datasets._URL_OPENER.open",
        lambda *_a, **_k: response,
    )


def test_open_dataset_from_url(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_public_dns(monkeypatch)
    _stub_url_response(monkeypatch, _FakeUrlResponse(_csv_bytes()))
    response = client.post("/api/datasets/from-url", json={"url": "https://example.com/data.csv"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["source"] == "url"
    assert body["n_rows"] == 30


def test_open_dataset_from_url_rejects_non_http(client: TestClient) -> None:
    response = client.post("/api/datasets/from-url", json={"url": "file:///etc/passwd"})
    assert response.status_code == 400


def test_open_dataset_from_url_rejects_private_host(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Even a syntactically valid public-looking URL must be refused if it resolves
    # to a private/loopback/metadata address (SSRF guard).
    monkeypatch.setattr(
        "scorepilot.api.datasets._host_addresses",
        lambda _host: ["169.254.169.254"],
    )
    response = client.post(
        "/api/datasets/from-url", json={"url": "https://metadata.example/data.csv"}
    )
    assert response.status_code == 400
    assert "public host" in response.json()["detail"]


def test_open_dataset_from_url_rejects_oversized(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_public_dns(monkeypatch)
    big = {"Content-Length": str(6 * 1024 * 1024)}
    _stub_url_response(monkeypatch, _FakeUrlResponse(b"x", headers=big))
    response = client.post("/api/datasets/from-url", json={"url": "https://example.com/big.csv"})
    assert response.status_code == 413


def test_upload_rejects_oversized(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'cap.db'}", max_upload_mb=1)
    with TestClient(create_app(settings)) as client:
        payload = b"a,b,c\n" + b"1,2,3\n" * 200_000  # ~1.2 MB, over the 1 MB cap
        response = client.post(
            "/api/datasets",
            files={"file": ("big.csv", payload, "text/csv")},
        )
    assert response.status_code == 413


def test_upload_rejects_too_many_cells(tmp_path: Path) -> None:
    # A tiny CSV that parses to more cells than the configured limit is refused,
    # bounding what a small but expansive file can turn into.
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'cells.db'}", max_cells=10)
    with TestClient(create_app(settings)) as client:
        csv = b"a,b,c\n" + b"1,2,3\n" * 20  # 20 rows x 4 cols (Row id added) > 10
        response = client.post(
            "/api/datasets",
            files={"file": ("wide.csv", csv, "text/csv")},
        )
    assert response.status_code == 413


def test_auth_gate_blocks_and_allows(tmp_path: Path) -> None:
    settings = Settings(
        database_url=f"sqlite:///{tmp_path / 'auth.db'}",
        auth_password="s3cret",
    )
    with TestClient(create_app(settings)) as client:
        # Health stays open for proxy/container health checks.
        assert client.get("/api/health").status_code == 200
        # Everything else demands credentials.
        anon = client.get("/api/datasets")
        assert anon.status_code == 401
        assert anon.headers["WWW-Authenticate"].startswith("Basic")
        # Wrong password is refused; correct one passes.
        assert client.get("/api/datasets", auth=("scorepilot", "nope")).status_code == 401
        ok = client.get("/api/datasets", auth=("scorepilot", "s3cret"))
        assert ok.status_code == 200


def test_docs_served_by_default(client: TestClient) -> None:
    schema = client.get("/api/openapi.json")
    assert schema.status_code == 200
    assert schema.json()["openapi"].startswith("3.")
    assert "swagger" in client.get("/api/docs").text.lower()


def test_docs_can_be_disabled(tmp_path: Path) -> None:
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'nodocs.db'}", docs_enabled=False)
    with TestClient(create_app(settings)) as client:
        # The OpenAPI schema is no longer served as JSON (the SPA catch-all answers
        # instead), and the Swagger UI is gone.
        assert "application/json" not in client.get("/api/openapi.json").headers.get(
            "content-type", ""
        )
        assert "swagger" not in client.get("/api/docs").text.lower()


def test_spa_fallback_serves_index(client: TestClient) -> None:
    response = client.get("/some/client/route")
    assert response.status_code == 200
    assert "ScorePilot" in response.text


def test_datasets_persist_across_restart(tmp_path: Path) -> None:
    """A dataset (and a model built from it) survives a process restart (#33)."""
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'persist.db'}")

    with TestClient(create_app(settings)) as first:
        upload = first.post(
            "/api/datasets", files={"file": ("data.csv", io.BytesIO(_csv_bytes()), "text/csv")}
        ).json()
        dataset_id = upload["dataset_id"]
        model_id = first.post(
            "/api/models", json={"dataset_id": dataset_id, "kind": "PCA", "n_components": 2}
        ).json()["summary"]["id"]

    # A brand-new app instance against the same database stands in for a redeploy.
    with TestClient(create_app(settings)) as second:
        detail = second.get(f"/api/datasets/{dataset_id}")
        assert detail.status_code == 200
        assert detail.json()["n_rows"] == 30
        # The grid still serves the exact data, so model diagnostics recompute.
        grid = second.get(f"/api/datasets/{dataset_id}/grid?row_limit=5").json()
        assert grid["cells"]
        model = second.get(f"/api/models/{model_id}").json()
        assert model["diagnostics"] is not None


def test_dataset_column_edit_persists(tmp_path: Path) -> None:
    """Editing a column's role/type is durable across a restart."""
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'edit.db'}")

    with TestClient(create_app(settings)) as first:
        dataset_id = first.post(
            "/api/datasets", files={"file": ("data.csv", io.BytesIO(_csv_bytes()), "text/csv")}
        ).json()["dataset_id"]
        patched = first.patch(
            f"/api/datasets/{dataset_id}/columns/v0", json={"column_type": "qualitative"}
        )
        assert patched.status_code == 200

    with TestClient(create_app(settings)) as second:
        columns = {
            c["name"]: c["column_type"]
            for c in second.get(f"/api/datasets/{dataset_id}").json()["columns"]
        }
        assert columns["v0"] == "qualitative"


def _upload(client: TestClient, csv: bytes) -> dict:
    response = client.post(
        "/api/datasets", files={"file": ("data.csv", io.BytesIO(csv), "text/csv")}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_synthetic_primary_id_when_no_unique_column(client: TestClient) -> None:
    """All-numeric data with no usable identifier gets a synthetic Row column."""
    csv = b"a,b\n0.1,1.1\n0.2,1.2\n0.3,1.3\n"
    body = _upload(client, csv)
    assert body["primary_id"] == "Row"
    # The synthetic identifier is added as the leftmost column.
    assert [c["name"] for c in body["columns"]] == ["Row", "a", "b"]

    # ...but it is not a model variable: PCA still fits on the two real columns.
    fit = client.post(
        "/api/models/pca", json={"dataset_id": body["dataset_id"], "n_components": 2}
    ).json()
    assert fit["scores"]["data"] and len(fit["component_names"]) == 2
    # The grid shows the Row column with values 1, 2, 3.
    grid = client.get(f"/api/datasets/{body['dataset_id']}/grid?row_limit=3").json()
    assert grid["column_names"][0] == "Row"
    assert [row[0] for row in grid["cells"]] == ["1", "2", "3"]


def test_integer_column_auto_detected_as_primary(client: TestClient) -> None:
    csv = b"id,x\n10,0.1\n20,0.2\n30,0.3\n"
    body = _upload(client, csv)
    assert body["primary_id"] == "id"


def test_set_primary_requires_unique_values(client: TestClient) -> None:
    # 'grp' repeats; 'val' is the auto-detected primary.
    body = _upload(client, b"grp,val\nA,1\nA,2\nB,3\n")
    dataset_id = body["dataset_id"]
    assert body["primary_id"] == "val"

    rejected = client.patch(
        f"/api/datasets/{dataset_id}/columns/grp", json={"identifier_role": "primary"}
    )
    assert rejected.status_code == 422
    assert "unique" in rejected.json()["detail"]


def test_set_primary_relinquishes_previous(client: TestClient) -> None:
    dataset_id = _upload_csv(client)["dataset_id"]  # primary auto-detected as 'sample'
    # v0 is complete and unique, so it can become the new primary.
    updated = client.patch(
        f"/api/datasets/{dataset_id}/columns/v0", json={"identifier_role": "primary"}
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["primary_id"] == "v0"
    roles = {c["name"]: c["identifier_role"] for c in body["columns"]}
    # The previous primary is relinquished back to a regular column.
    assert roles["sample"] == "none"
    assert roles["v0"] == "primary"
