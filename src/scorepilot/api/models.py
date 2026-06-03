"""Model-fitting endpoints."""

from __future__ import annotations

import io

import numpy as np
from fastapi import APIRouter, HTTPException, status

from scorepilot.api.deps import DatasetStoreDep, RepositoryDep
from scorepilot.core import PCAResult, fit_pca
from scorepilot.db import Model
from scorepilot.schemas import FitPCARequest, PCAFitResponse, ScoresPayload

router = APIRouter(prefix="/models", tags=["models"])


def _pack_params(result: PCAResult) -> bytes:
    """Serialize the fitted arrays as a compressed npz blob for storage."""
    buffer = io.BytesIO()
    np.savez_compressed(
        buffer,
        loadings=result.loadings.to_numpy(),
        explained_variance=result.explained_variance,
        r2_cumulative=result.r2_cumulative.to_numpy(),
    )
    return buffer.getvalue()


def _to_response(model_id: int, result: PCAResult) -> PCAFitResponse:
    return PCAFitResponse(
        model_id=model_id,
        kind="PCA",
        n_components=result.n_components,
        preprocessing=result.preprocessing,
        conf_level=result.conf_level,
        component_names=result.component_names,
        explained_variance=result.explained_variance.tolist(),
        r2_cumulative=result.r2_cumulative.to_numpy().tolist(),
        scores=ScoresPayload(
            component_names=result.component_names,
            observation_names=result.observation_names,
            data=result.scores.to_numpy().tolist(),
        ),
        hotellings_t2=result.hotellings_t2.to_numpy().tolist(),
        spe=result.spe.to_numpy().tolist(),
        t2_limit=result.t2_limit,
        spe_limit=result.spe_limit,
    )


@router.post("/pca", response_model=PCAFitResponse, status_code=status.HTTP_201_CREATED)
def fit_pca_model(
    request: FitPCARequest,
    store: DatasetStoreDep,
    repository: RepositoryDep,
) -> PCAFitResponse:
    """Fit a PCA model from a previously uploaded dataset and persist it."""
    frame = store.get(request.dataset_id)
    if frame is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown dataset_id: {request.dataset_id}",
        )

    try:
        result = fit_pca(
            frame,
            request.n_components,
            preprocessing=request.preprocessing,
            conf_level=request.conf_level,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    model = repository.add(
        Model(
            kind="PCA",
            name=request.name,
            n_components=result.n_components,
            preprocessing={"method": result.preprocessing.value},
            excluded_samples=[],
            params=_pack_params(result),
        )
    )
    return _to_response(model.id, result)
