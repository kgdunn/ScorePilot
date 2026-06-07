"""Model-fitting endpoints, the Hangar (list), and the Logbook (detail)."""

from __future__ import annotations

import io
from dataclasses import replace
from typing import Annotated

import numpy as np
from fastapi import APIRouter, HTTPException, Query, status

from scorepilot.api.deps import DatasetStoreDep, RepositoryDep
from scorepilot.core import (
    AppliedWorkset,
    ModelDiagnostics,
    PreprocessingSpec,
    apply_spec,
    cross_validate,
    fit_model,
    observation_contributions,
)
from scorepilot.core._pandas import column as get_column
from scorepilot.core.cross_validation import CvScheme, SelectionRule
from scorepilot.dataset_store import Dataset
from scorepilot.db import Model
from scorepilot.schemas import (
    ContributionsModel,
    CrossValidationModel,
    FitModelRequest,
    FitPCARequest,
    LoadingsPayload,
    ModelDetail,
    ModelDiagnosticsModel,
    ModelSummary,
    PCAFitResponse,
    ScoresPayload,
    UpdateModelRequest,
    VariantRequest,
)

router = APIRouter(prefix="/models", tags=["models"])

# Ceiling on components evaluated when auto-fitting by cross-validation; matches
# the components input's upper bound in the build form.
_AUTO_MAX_COMPONENTS = 20


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


def _format_identifier(value: object) -> str:
    """Render a primary-identifier value as a plot label (compact floats)."""
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _observation_names(dataset: Dataset, applied: AppliedWorkset) -> list[str]:
    """Labels for the model's rows: the dataset's primary identifier where set.

    ``apply_spec`` drops excluded rows but keeps the surviving rows' original
    positions as the X-block index, so the primary-identifier column is read at
    exactly those positions to label scores and T2/SPE bars.
    """
    positions = [int(i) for i in applied.X.index]
    if dataset.primary_id is not None:
        ids = get_column(dataset.raw, dataset.primary_id)
        return [_format_identifier(ids.iloc[p]) for p in positions]
    return [str(p) for p in positions]


def _positions_for_identifiers(dataset: Dataset, names: set[str]) -> set[int]:
    """Raw-dataset row positions whose primary identifier is in ``names``.

    ``names`` are the labels carried by the plots' selection - primary-identifier
    values formatted exactly as :func:`_observation_names` produces them, so the
    match is consistent. With no primary identifier the labels are row positions.
    """
    if not names:
        return set()
    if dataset.primary_id is None:
        positions: set[int] = set()
        for n in names:
            try:
                positions.add(int(n))
            except ValueError:
                continue
        return {p for p in positions if 0 <= p < len(dataset.raw)}
    ids = get_column(dataset.raw, dataset.primary_id)
    return {i for i, v in enumerate(ids) if _format_identifier(v) in names}


def _run_fit(
    dataset: Dataset,
    spec: PreprocessingSpec,
    kind: str,
    n_components: int,
    conf_level: float,
    *,
    auto_components: bool = False,
    selection_rule: SelectionRule | None = None,
    cv_scheme: CvScheme | None = None,
    n_repeats: int | None = None,
    min_q2_increase: float | None = None,
) -> ModelDiagnostics:
    applied = apply_spec(dataset.raw, spec)
    names = _observation_names(dataset, applied)
    if auto_components:
        # Let cross-validation pick the count freely (up to the UI's ceiling),
        # rather than capping at whatever number the user happened to type.
        n_components = cross_validate(
            applied.X,
            applied.Y,
            kind,
            max_components=_AUTO_MAX_COMPONENTS,
            selection_rule=selection_rule,
            cv_scheme=cv_scheme,
            n_repeats=n_repeats,
            min_q2_increase=min_q2_increase,
        ).recommended
    return fit_model(
        applied.X, applied.Y, kind, n_components, conf_level=conf_level, observation_names=names
    )


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
        diag = _run_fit(
            dataset,
            spec,
            request.kind,
            request.n_components,
            request.conf_level,
            auto_components=request.auto_components,
            selection_rule=request.selection_rule,
            cv_scheme=request.cv_scheme,
            n_repeats=request.n_repeats,
            min_q2_increase=request.min_q2_increase,
        )
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


@router.post("/{model_id}/variant", response_model=ModelDetail, status_code=status.HTTP_201_CREATED)
def create_variant(
    model_id: int, request: VariantRequest, store: DatasetStoreDep, repository: RepositoryDep
) -> ModelDetail:
    """Fork a child variant from a brushed selection of points.

    Copies the parent's preprocessing recipe and adds exclusions derived from the
    selection (exclude the selected rows/variables, or keep only the selected
    rows), then refits and persists the result with ``parent_id`` set so the
    lineage is preserved.
    """
    parent = repository.get(model_id)
    if parent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown model id: {model_id}"
        )
    dataset = store.get(parent.dataset_id) if parent.dataset_id else None
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source dataset is no longer loaded; cannot create a variant.",
        )

    spec = PreprocessingSpec.from_dict(parent.preprocessing)
    existing_rows = set(spec.excluded_rows)
    selected = _positions_for_identifiers(dataset, set(request.observations))
    if request.mode == "keep":
        active = (i for i in range(len(dataset.raw)) if i not in existing_rows)
        new_rows = existing_rows | {i for i in active if i not in selected}
        new_cols = spec.excluded_columns
    else:
        new_rows = existing_rows | selected
        new_cols = tuple(sorted(set(spec.excluded_columns) | set(request.variables)))
    new_spec = replace(spec, excluded_rows=tuple(sorted(new_rows)), excluded_columns=new_cols)

    try:
        diag = _run_fit(dataset, new_spec, parent.kind, parent.n_components, 0.95)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    base_name = parent.name or f"Model {parent.id}"
    model = repository.add(
        Model(
            kind=parent.kind,
            name=request.name or f"{base_name} (variant)",
            dataset_id=dataset.id,
            n_components=diag.n_components,
            preprocessing=new_spec.to_dict(),
            excluded_samples=list(new_spec.excluded_rows),
            params=_pack_params(diag),
            parent_id=parent.id,
        )
    )
    return ModelDetail(
        summary=_summary(model),
        preprocessing=new_spec.to_dict(),
        excluded_samples=list(new_spec.excluded_rows),
        lineage=[_summary(m) for m in repository.lineage(model.id)],
        diagnostics=_diagnostics_model(diag),
    )


@router.get("", response_model=list[ModelSummary])
def list_models(repository: RepositoryDep) -> list[ModelSummary]:
    """List all model variants (the Hangar)."""
    return [_summary(m) for m in repository.list()]


@router.get("/{model_id}", response_model=ModelDetail)
def get_model(
    model_id: int,
    store: DatasetStoreDep,
    repository: RepositoryDep,
    n_components: Annotated[int | None, Query(ge=1)] = None,
) -> ModelDetail:
    """Return a model's Logbook: metadata, recipe, lineage, and diagnostics.

    Diagnostics are recomputed from the source dataset and stored spec. If the
    dataset is no longer in memory, the entry is returned without diagnostics.

    ``n_components`` previews the diagnostics at a different component count
    without persisting it - this backs the live component explorer, which scrubs
    the count and re-renders every plot before you commit the change.
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
            diag = _run_fit(dataset, spec, model.kind, n_components or model.n_components, 0.95)
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


@router.patch("/{model_id}", response_model=ModelDetail)
def update_model(
    model_id: int, request: UpdateModelRequest, store: DatasetStoreDep, repository: RepositoryDep
) -> ModelDetail:
    """Change a model's component count in place and refit (no new variant).

    Backs the component explorer's "apply": the same model keeps its identity,
    preprocessing, and lineage; only ``n_components`` changes.
    """
    model = repository.get(model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown model id: {model_id}"
        )
    dataset = store.get(model.dataset_id) if model.dataset_id else None
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source dataset is no longer loaded; cannot refit.",
        )

    spec = PreprocessingSpec.from_dict(model.preprocessing)
    try:
        diag = _run_fit(dataset, spec, model.kind, request.n_components, 0.95)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    model.n_components = diag.n_components
    model.params = _pack_params(diag)
    repository.update(model)

    return ModelDetail(
        summary=_summary(model),
        preprocessing=dict(model.preprocessing),
        excluded_samples=list(model.excluded_samples),
        lineage=[_summary(m) for m in repository.lineage(model.id)],
        diagnostics=_diagnostics_model(diag),
    )


@router.get("/{model_id}/contributions/{observation}", response_model=ContributionsModel)
def model_contributions(
    model_id: int, observation: int, store: DatasetStoreDep, repository: RepositoryDep
) -> ContributionsModel:
    """Per-variable contributions of one observation to the model's T2 and SPE.

    Used by the contribution-plot modal when a score, T2, or SPE point is opened.
    """
    model = repository.get(model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown model id: {model_id}"
        )
    dataset = store.get(model.dataset_id) if model.dataset_id else None
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source dataset is no longer loaded; cannot compute contributions.",
        )

    spec = PreprocessingSpec.from_dict(model.preprocessing)
    applied = apply_spec(dataset.raw, spec)
    names = _observation_names(dataset, applied)
    name = names[observation] if 0 <= observation < len(names) else None
    try:
        contrib = observation_contributions(
            applied.X,
            applied.Y,
            model.kind,
            model.n_components,
            observation,
            observation_name=name,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return ContributionsModel(
        observation=contrib.observation,
        observation_name=contrib.observation_name,
        variable_names=contrib.variable_names,
        t2=contrib.t2,
        spe=contrib.spe,
    )


@router.get("/{model_id}/cross-validation", response_model=CrossValidationModel)
def model_cross_validation(
    model_id: int,
    store: DatasetStoreDep,
    repository: RepositoryDep,
    max_components: Annotated[int | None, Query(ge=1)] = None,
    selection_rule: Annotated[SelectionRule | None, Query()] = None,
    cv_scheme: Annotated[CvScheme | None, Query()] = None,
    n_repeats: Annotated[int | None, Query(ge=1)] = None,
    min_q2_increase: Annotated[float | None, Query(ge=0.0)] = None,
) -> CrossValidationModel:
    """Per-component calibration R2 and cross-validated Q2 for a fitted model.

    Backs the R2/Q2 plot and table: R2 is the in-sample fit after each component,
    Q2 the cross-validated (out-of-sample) prediction, with the recommended
    component count flagged.

    ``max_components`` extends the curve beyond the model's current count (capped
    at the auto-fit ceiling) so the component explorer can show the diminishing
    returns of adding more. ``selection_rule`` (and, for PCA, ``cv_scheme``)
    choose how the recommended count is picked; ``n_repeats`` and
    ``min_q2_increase`` tune the cross-validation.
    """
    model = repository.get(model_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Unknown model id: {model_id}"
        )
    dataset = store.get(model.dataset_id) if model.dataset_id else None
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source dataset is no longer loaded; cannot cross-validate.",
        )

    ceiling = min(max_components or model.n_components, _AUTO_MAX_COMPONENTS)
    spec = PreprocessingSpec.from_dict(model.preprocessing)
    applied = apply_spec(dataset.raw, spec)
    try:
        cv = cross_validate(
            applied.X,
            applied.Y,
            model.kind,
            max_components=ceiling,
            selection_rule=selection_rule,
            cv_scheme=cv_scheme,
            n_repeats=n_repeats,
            min_q2_increase=min_q2_increase,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return CrossValidationModel(
        kind=cv.kind,
        target=cv.target,
        n_splits=cv.n_splits,
        n_repeats=cv.n_repeats,
        selection_rule=cv.selection_rule,
        cv_scheme=cv.cv_scheme,
        component_numbers=cv.component_numbers,
        r2=cv.r2,
        q2=cv.q2,
        q2_se=cv.q2_se,
        r2_per_component=cv.r2_per_component,
        q2_per_component=cv.q2_per_component,
        recommended=cv.recommended,
        recommended_is_stable=cv.recommended_is_stable,
        recommended_vote_share=cv.recommended_vote_share,
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
