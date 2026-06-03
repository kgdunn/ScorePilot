"""Pydantic v2 request/response models for the HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from scorepilot.core import Preprocessing


class ApiModel(BaseModel):
    """Base model that disables the protected ``model_`` namespace.

    Chemometrics responses legitimately use ``model_id``; without this, Pydantic
    warns about the ``model_`` prefix.
    """

    model_config = ConfigDict(protected_namespaces=())


class DatasetSummary(ApiModel):
    """Metadata returned after a dataset is uploaded."""

    dataset_id: str
    n_rows: int
    n_columns: int
    columns: list[str]


class FitPCARequest(ApiModel):
    """Request body to fit a PCA model from an uploaded dataset."""

    dataset_id: str
    n_components: int = Field(ge=1)
    preprocessing: Preprocessing = Preprocessing.MEAN_CENTER_SCALE
    conf_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    name: str | None = None


class ScoresPayload(ApiModel):
    """Score matrix in a plotting-friendly shape (one row per observation)."""

    component_names: list[str]
    observation_names: list[str]
    data: list[list[float]]


class PCAFitResponse(ApiModel):
    """Result of fitting a PCA model."""

    model_id: int
    kind: str
    n_components: int
    preprocessing: Preprocessing
    conf_level: float
    component_names: list[str]
    explained_variance: list[float]
    r2_cumulative: list[float]
    scores: ScoresPayload
    hotellings_t2: list[float]
    spe: list[float]
    t2_limit: float
    spe_limit: float
