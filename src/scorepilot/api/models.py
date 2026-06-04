"""Model-fitting endpoints, the Hangar (list), and the Logbook (detail)."""

from __future__ import annotations

import io

import numpy as np
from fastapi import APIRouter, HTTPException, status

from scorepilot.api.deps import DatasetStoreDep, RepositoryDep
from scorepilot.core import (
    ModelDiagnostics,
    PreprocessingSpec,
    apply_spec,
    fit_model,
)
from scorepilot.dataset_store import Dataset
from scorepilot.db import Model
from scorepilot.schemas import (
    FitModelRequest,
    FitPCARequest,
    LoadingsPayload,
    ModelDetail,
    ModelDiagnosticsModel,
    ModelSummary,
    PCAFitResponse,
    ScoresPayload,
)

router = APIRouter(prefix="/models", tags=["models"])


# --- helpers ----------------------------------------------------------------


def _pack_params(diag: ModelDiagnostics) -> bytes:
    buffer = io.BytesIO()
    np.savez_compressed(
        buffer,
        x_loadings=diag.x_loadings.to_numpy(),
        explained_variance=diag.explained_variance,
        r2_cumulative=np.asarray(diag.r2_cumulative),
    )
    return buffer.getvalue()


def _default_spec(dataset: Dataset, spec: PreprocessingSpec | None) -> PreprocessingSpec:
    if spec is not None:
        return spec
    return PreprocessingSpec(x_columns=tuple(dataset.quantitative_columns()))


def _run_fit(
    dataset: Dataset, spec: PreprocessingSpec, kind: str, n_components: int, conf_level: float
) -> ModelDiagnostics:
    applied = apply_spec(dataset.raw, spec)
    return fit_model(applied.X, applied.Y, kind, n_components, conf_level=conf_level)


def _summary(model: Model) -> ModelSummary:
    return ModelSummary(
        id=model.id,
        kind=model.kind,
        name=model.name,
        n_components=model.n_components,
        parent_id=model.parent_id,
        dataset_id=model.dataset_id,
        created_at=model.created_at,
    )


def _diagnostics_model(diag: ModelDiagnostics) -> ModelDiagnosticsModel:
    y_loadings = None
    if diag.y_loadings is not None:
        y_loadings = LoadingsPayload(
            component_names=diag.component_names,
            variable_names=diag.y_variable_names,
            data=diag.y_loadings.to_numpy().tolist(),
        )
    return ModelDiagnosticsModel(
        kind=diag.kind,
        n_components=diag.n_components,
        conf_level=diag.conf_level,
        component_names=diag.component_names,
        explained_variance=diag.explained_variance.tolist(),
        r2_per_component=diag.r2_per_component,
        r2_cumulative=diag.r2_cumulative,
        scores=ScoresPayload(
            component_names=diag.component_names,
            observation_names=diag.observation_names,
            data=diag.scores.to_numpy().tolist(),
        ),
        x_loadings=LoadingsPayload(
            component_names=diag.component_names,
            variable_names=diag.x_variable_names,
            data=diag.x_loadings.to_numpy().tolist(),
        ),
        y_loadings=y_loadings,
        hotellings_t2=diag.hotellings_t2.to_numpy().tolist(),
        spe=diag.spe.to_numpy().tolist(),
        t2_limit=diag.t2_limit,
        spe_limit=diag.spe_limit,
        ellipse_x=diag.ellipse_x,
        ellipse_y=diag.ellipse_y,
        vip=diag.vip,
    )


def _require_dataset(store: DatasetStoreDep, dataset_id: str) -> Dataset:
    dataset = store.get(dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown dataset_id: {dataset_id}",
        )
    return dataset


# --- endpoints --------------------------------------------------------------


@router.post("", response_model=ModelDetail, status_code=status.HTTP_201_CREATED)
def fit_model_endpoint(
    request: FitModelRequest, store: DatasetStoreDep, repository: RepositoryDep
) -> ModelDetail:
    """Fit a PCA/PLS model variant from a dataset and a spec, and persist it."""
    dataset = _require_dataset(store, request.dataset_id)
    if request.parent_id is not None and repository.get(request.parent_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown parent_id: {request.parent_id}",
        )

    spec = _default_spec(dataset, request.spec.to_core() if request.spec else None)
    try:
        diag = _run_fit(dataset, spec, request.kind, request.n_components, request.conf_level)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    model = repository.add(
        Model(
            kind=request.kind,
            name=request.name,
            dataset_id=dataset.id,
            n_components=diag.n_components,
            preprocessing=spec.to_dict(),
            excluded_samples=list(spec.excluded_rows),
            params=_pack_params(diag),
            parent_id=request.parent_id,
        )
    )
    return ModelDetail(
        summary=_summary(model),
        preprocessing=spec.to_dict(),
        excluded_samples=list(spec.excluded_rows),
        lineage=[_summary(m) for m in repository.lineage(model.id)],
        diagnostics=_diagnostics_model(diag),
    )


@router.get("", response_model=list[ModelSummary])
def list_models(repository: RepositoryDep) -> list[ModelSummary]:
    """List all model variants (the Hangar)."""
    return [_summary(m) for m in repository.list()]


@router.get("/{model_id}", response_model=ModelDetail)
def get_model(model_id: int, store: DatasetStoreDep, repository: RepositoryDep) -> ModelDetail:
    """Return a model's Logbook: metadata, recipe, lineage, and diagnostics.

    Diagnostics are recomputed from the source dataset and stored spec. If the
    dataset is no longer in memory, the entry is returned without diagnostics.
    """
    model = repository.get(model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown model id: {model_id}"
        )

    diagnostics = None
    dataset = store.get(model.dataset_id) if model.dataset_id else None
    if dataset is not None:
        spec = PreprocessingSpec.from_dict(model.preprocessing)
        try:
            diag = _run_fit(dataset, spec, model.kind, model.n_components, 0.95)
            diagnostics = _diagnostics_model(diag)
        except ValueError:
            diagnostics = None

    return ModelDetail(
        summary=_summary(model),
        preprocessing=dict(model.preprocessing),
        excluded_samples=list(model.excluded_samples),
        lineage=[_summary(m) for m in repository.lineage(model.id)],
        diagnostics=diagnostics,
    )


@router.post("/pca", response_model=PCAFitResponse, status_code=status.HTTP_201_CREATED)
def fit_pca_model(
    request: FitPCARequest, store: DatasetStoreDep, repository: RepositoryDep
) -> PCAFitResponse:
    """Fit a PCA model (legacy endpoint used by the scores playground)."""
    dataset = _require_dataset(store, request.dataset_id)
    spec = _default_spec(dataset, request.spec.to_core() if request.spec else None)
    try:
        diag = _run_fit(dataset, spec, "PCA", request.n_components, request.conf_level)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    model = repository.add(
        Model(
            kind="PCA",
            name=request.name,
            dataset_id=dataset.id,
            n_components=diag.n_components,
            preprocessing=spec.to_dict(),
            excluded_samples=list(spec.excluded_rows),
            params=_pack_params(diag),
        )
    )
    return PCAFitResponse(
        model_id=model.id,
        kind="PCA",
        n_components=diag.n_components,
        conf_level=diag.conf_level,
        component_names=diag.component_names,
        explained_variance=diag.explained_variance.tolist(),
        r2_cumulative=diag.r2_cumulative,
        scores=ScoresPayload(
            component_names=diag.component_names,
            observation_names=diag.observation_names,
            data=diag.scores.to_numpy().tolist(),
        ),
        hotellings_t2=diag.hotellings_t2.to_numpy().tolist(),
        spe=diag.spe.to_numpy().tolist(),
        t2_limit=diag.t2_limit,
        spe_limit=diag.spe_limit,
    )
