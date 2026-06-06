"""Exploration endpoints: data-quality, grid windows, and the variable inspector.

These are read-only views over an immutable dataset. The transform shown in the
inspector is a non-destructive *preview*; it never changes the stored data.
"""

from __future__ import annotations

import json
from typing import Annotated

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, status

from scorepilot.api.deps import DatasetStoreDep
from scorepilot.core import (
    ColumnType,
    PreprocessingSpec,
    TransformKind,
    VariableTransform,
    apply_spec,
    apply_transform,
    histogram,
    quality_report,
    sequence,
    suggest_transform,
    variable_summary,
)
from scorepilot.core._pandas import column as get_column
from scorepilot.core._pandas import to_numeric
from scorepilot.dataset_store import SYNTHETIC_ID_NAME, Dataset
from scorepilot.schemas import (
    ColumnQualityModel,
    DuplicateIdentifierModel,
    GridWindow,
    ObservationQualityModel,
    QualityReportModel,
    VariableInspector,
)

router = APIRouter(prefix="/datasets", tags=["exploration"])


def _require(store: DatasetStoreDep, dataset_id: str) -> Dataset:
    dataset = store.get(dataset_id)
    if dataset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown dataset_id: {dataset_id}",
        )
    return dataset


def _format_cell(value: object) -> str | None:
    if pd.isna(value):  # type: ignore[arg-type]
        return None
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


@router.get("/{dataset_id}/quality", response_model=QualityReportModel)
def get_quality(dataset_id: str, store: DatasetStoreDep) -> QualityReportModel:
    """Return the data-quality report for a dataset."""
    dataset = _require(store, dataset_id)
    report = quality_report(dataset.raw, types=dataset.types(), primary_id=dataset.primary_id)
    return QualityReportModel(
        n_rows=report.n_rows,
        n_columns=report.n_columns,
        n_missing_cells=report.n_missing_cells,
        pct_missing=report.pct_missing,
        primary_id_unique=report.primary_id_unique,
        duplicate_primary_ids=[
            DuplicateIdentifierModel(value=d.value, rows=d.rows)
            for d in report.duplicate_primary_ids
        ],
        columns=[
            ColumnQualityModel(
                name=c.name,
                n_missing=c.n_missing,
                pct_missing=c.pct_missing,
                n_invalid=c.n_invalid,
                invalid_rows=c.invalid_rows,
                exceeds_tolerance=c.exceeds_tolerance,
            )
            for c in report.columns
        ],
        observations_exceeding=[
            ObservationQualityModel(
                index=o.index,
                identifier=o.identifier,
                n_missing=o.n_missing,
                pct_missing=o.pct_missing,
            )
            for o in report.observations_exceeding
        ],
    )


@router.get("/{dataset_id}/grid", response_model=GridWindow)
def get_grid(
    dataset_id: str,
    store: DatasetStoreDep,
    row_offset: Annotated[int, Query(ge=0)] = 0,
    row_limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    col_offset: Annotated[int, Query(ge=0)] = 0,
    col_limit: Annotated[int, Query(ge=1, le=200)] = 50,
    form: Annotated[str, Query(pattern="^(raw|scaled)$")] = "raw",
    transforms: Annotated[
        str | None,
        Query(description='JSON map of column -> {"kind", "c1", "c2"} applied in scaled view'),
    ] = None,
) -> GridWindow:
    """Return a windowed block of cells for the grid, raw or autoscaled.

    In the scaled view, the draft spec's per-variable transforms (passed as a JSON
    ``transforms`` map) are applied before scaling, so the table matches the scaled
    plots in the inspector.
    """
    dataset = _require(store, dataset_id)
    display = _display_frame(dataset, form, _parse_transforms(transforms))

    all_columns = [str(c) for c in display.columns]
    column_names = all_columns[col_offset : col_offset + col_limit]
    window = display.iloc[row_offset : row_offset + row_limit][column_names]

    row_identifiers = _row_identifiers(dataset, row_offset, len(window))
    cells = [
        [_format_cell(window.iat[r, c]) for c in range(window.shape[1])]
        for r in range(window.shape[0])
    ]
    return GridWindow(
        row_offset=row_offset,
        column_names=column_names,
        row_identifiers=row_identifiers,
        cells=cells,
    )


def _parse_transforms(raw: str | None) -> dict[str, VariableTransform]:
    """Parse the ``transforms`` query (a JSON column -> transform map)."""
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid transforms parameter: expected a JSON object.",
        ) from exc
    if not isinstance(data, dict):
        return {}
    result: dict[str, VariableTransform] = {}
    for name, spec in data.items():
        if not isinstance(spec, dict):
            continue
        try:
            kind = TransformKind(spec.get("kind", "none"))
        except ValueError:
            continue
        result[str(name)] = VariableTransform(
            kind=kind,
            c1=float(spec.get("c1", 0.0)),
            c2=float(spec.get("c2", 1.0)),
        )
    return result


def _display_frame(
    dataset: Dataset, form: str, transforms: dict[str, VariableTransform] | None = None
) -> pd.DataFrame:
    if form != "scaled":
        return dataset.raw
    quantitative = dataset.quantitative_columns()
    if not quantitative:
        return dataset.raw
    # Apply any per-variable transforms, then scale on full-column statistics so the
    # view is stable across scrolling and consistent with the inspector's plots.
    spec = PreprocessingSpec(x_columns=tuple(quantitative), transforms=transforms or {})
    scaled = apply_spec(dataset.raw, spec).X
    display = dataset.raw.copy()
    for name in quantitative:
        display[name] = scaled[name]
    return display


def _row_identifiers(dataset: Dataset, row_offset: int, count: int) -> list[str | None]:
    if dataset.primary_id is not None:
        ids = get_column(dataset.raw, dataset.primary_id).iloc[row_offset : row_offset + count]
        return [_format_cell(v) for v in ids]
    return [str(row_offset + i) for i in range(count)]


def _is_sequential_identifier(name: str | None, series: pd.Series) -> bool:
    """Whether the primary identifier is "truly sequential" (issue #59).

    The synthetic ``Row`` counter (and the implicit row index) are sequential, as
    is any integer identifier that is a constant-step arithmetic run (a row
    counter under a different name). A labelled identifier is not: its values
    carry meaning and should be shown rather than collapsed to ``1..n``.
    """
    if name is None or name == SYNTHETIC_ID_NAME:
        return True
    numeric = to_numeric(series)
    if bool(numeric.isna().any()):
        return False
    values = numeric.astype(float)
    if len(values) < 2 or not bool((values == values.round()).all()):
        return False
    diffs = values.diff().dropna()
    return bool((diffs == diffs.iloc[0]).all()) and bool(diffs.iloc[0] != 0)


@router.get("/{dataset_id}/variables/{column}", response_model=VariableInspector)
def inspect_variable(
    dataset_id: str,
    column: str,
    store: DatasetStoreDep,
    transform: Annotated[TransformKind, Query()] = TransformKind.NONE,
    c1: Annotated[float, Query()] = 0.0,
    c2: Annotated[float, Query()] = 1.0,
    form: Annotated[str, Query(pattern="^(raw|scaled)$")] = "raw",
    excluded_rows: Annotated[list[int] | None, Query()] = None,
) -> VariableInspector:
    """Return summary, histogram, and sequence for a variable (with optional preview).

    When ``form=scaled`` the quantitative column is mean-centered and scaled to unit
    variance (after any transform), so the distribution and sequence match the grid's
    scaled view. ``excluded_rows`` are dropped first, so excluding an outlier updates
    the plots (and the scaling statistics in the scaled view).
    """
    dataset = _require(store, dataset_id)
    meta = dataset.column(column)
    if meta is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown column: {column}",
        )

    excluded = {i for i in (excluded_rows or []) if 0 <= i < len(dataset.raw)}
    active = [i for i in range(len(dataset.raw)) if i not in excluded]
    series = get_column(dataset.raw, column).iloc[active]
    suggested = suggest_transform(variable_summary(series, column_type=meta.column_type))

    if form == "scaled" and meta.column_type is ColumnType.QUANTITATIVE:
        # apply_spec drops excluded rows, applies the transform (if any), then
        # mean-centers and scales, exactly as the scaled grid does.
        transforms = (
            {column: VariableTransform(kind=transform, c1=c1, c2=c2)}
            if transform is not TransformKind.NONE
            else {}
        )
        spec = PreprocessingSpec(
            x_columns=(column,), transforms=transforms, excluded_rows=tuple(sorted(excluded))
        )
        display = get_column(apply_spec(dataset.raw, spec).X, column)
    elif transform is not TransformKind.NONE:
        display = apply_transform(series, transform, c1=c1, c2=c2)
    else:
        display = series
    summary = variable_summary(display, column_type=meta.column_type)
    counts, edges = histogram(display)

    # Issue #59: carry the primary identifier per (surviving) row, aligned with
    # the sequence, plus whether that identifier is genuinely sequential.
    identifiers: list[str | None]
    if dataset.primary_id is not None:
        id_column = get_column(dataset.raw, dataset.primary_id)
        identifiers = [_format_cell(v) for v in id_column.iloc[active]]
        is_sequential = _is_sequential_identifier(dataset.primary_id, id_column)
    else:
        identifiers = [str(i) for i in active]
        is_sequential = True

    return VariableInspector(
        name=meta.name,
        column_type=meta.column_type,
        n=summary.n,
        n_missing=summary.n_missing,
        pct_missing=summary.pct_missing,
        n_unique=summary.n_unique,
        mean=summary.mean,
        std=summary.std,
        minimum=summary.minimum,
        maximum=summary.maximum,
        median=summary.median,
        q25=summary.q25,
        q75=summary.q75,
        skewness=summary.skewness,
        min_max_ratio=summary.min_max_ratio,
        suggested_transform=suggested,
        histogram_counts=counts,
        histogram_edges=edges,
        sequence=sequence(display),
        identifiers=identifiers,
        is_sequential=is_sequential,
    )
