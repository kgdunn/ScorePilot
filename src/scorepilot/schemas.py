"""Pydantic v2 request/response models for the HTTP API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from scorepilot.core import (
    ColumnType,
    IdentifierRole,
    PreprocessingSpec,
    ScalingKind,
    TransformKind,
    VariableTransform,
)


class ApiModel(BaseModel):
    """Base model that disables the protected ``model_`` namespace."""

    model_config = ConfigDict(protected_namespaces=())


# --- Datasets ---------------------------------------------------------------


class ColumnMetaModel(ApiModel):
    """Intrinsic metadata for one column."""

    name: str
    column_type: ColumnType
    identifier_role: IdentifierRole


class DatasetDetail(ApiModel):
    """Metadata for an imported dataset."""

    dataset_id: str
    name: str
    source: str
    sheet: str | None
    sheets: list[str]
    n_rows: int
    n_columns: int
    primary_id: str | None
    columns: list[ColumnMetaModel]


class ColumnUpdate(ApiModel):
    """Patch for a column's intrinsic metadata."""

    column_type: ColumnType | None = None
    identifier_role: IdentifierRole | None = None


class SampleInfo(ApiModel):
    """A bundled demo dataset offered on the home page."""

    name: str
    title: str
    description: str
    source_url: str


class DatasetUrlRequest(ApiModel):
    """Request to import a dataset from a CSV/Excel file at a URL."""

    url: str
    sheet: str | None = None


# --- Preprocessing spec (per model variant) ---------------------------------


class VariableTransformModel(ApiModel):
    """A transform and its constants for one variable."""

    kind: TransformKind = TransformKind.NONE
    c1: float = 0.0
    c2: float = 1.0

    def to_core(self) -> VariableTransform:
        return VariableTransform(kind=self.kind, c1=self.c1, c2=self.c2)


class PreprocessingSpecModel(ApiModel):
    """A model variant's preprocessing recipe over a dataset."""

    x_columns: list[str] = Field(default_factory=list)
    y_columns: list[str] = Field(default_factory=list)
    excluded_rows: list[int] = Field(default_factory=list)
    excluded_columns: list[str] = Field(default_factory=list)
    transforms: dict[str, VariableTransformModel] = Field(default_factory=dict)
    default_scaling: ScalingKind = ScalingKind.UNIT_VARIANCE
    scaling: dict[str, ScalingKind] = Field(default_factory=dict)

    def to_core(self) -> PreprocessingSpec:
        return PreprocessingSpec(
            x_columns=tuple(self.x_columns),
            y_columns=tuple(self.y_columns),
            excluded_rows=tuple(self.excluded_rows),
            excluded_columns=tuple(self.excluded_columns),
            transforms={k: v.to_core() for k, v in self.transforms.items()},
            default_scaling=self.default_scaling,
            scaling=dict(self.scaling),
        )


# --- Variable inspector & quality ------------------------------------------


class VariableInspector(ApiModel):
    """Per-variable summary, distribution, and sequence for the inspector."""

    name: str
    column_type: ColumnType
    n: int
    n_missing: int
    pct_missing: float
    n_unique: int
    mean: float | None
    std: float | None
    minimum: float | None
    maximum: float | None
    median: float | None
    q25: float | None
    q75: float | None
    skewness: float | None
    min_max_ratio: float | None
    suggested_transform: TransformKind
    histogram_counts: list[int]
    histogram_edges: list[float]
    sequence: list[float | None]
    # Primary-identifier value per row, aligned with ``sequence`` (issue #59).
    identifiers: list[str | None]
    # Whether the primary identifier is genuinely sequential (a synthetic Row
    # column or a monotonic run order); when false, plots label by the identifier.
    is_sequential: bool


class GridWindow(ApiModel):
    """A windowed block of cells for the data grid."""

    row_offset: int
    column_names: list[str]
    row_identifiers: list[str | None]
    cells: list[list[str | None]]


class ColumnQualityModel(ApiModel):
    """Quality summary for one column."""

    name: str
    n_missing: int
    pct_missing: float
    n_invalid: int
    invalid_rows: list[int]
    exceeds_tolerance: bool


class ObservationQualityModel(ApiModel):
    """Quality summary for one flagged observation."""

    index: int
    identifier: str | None
    n_missing: int
    pct_missing: float


class DuplicateIdentifierModel(ApiModel):
    """A primary identifier shared by more than one observation."""

    value: str
    rows: list[int]


class QualityReportModel(ApiModel):
    """Aggregate data-quality report for a dataset."""

    n_rows: int
    n_columns: int
    n_missing_cells: int
    pct_missing: float
    primary_id_unique: bool
    duplicate_primary_ids: list[DuplicateIdentifierModel]
    columns: list[ColumnQualityModel]
    observations_exceeding: list[ObservationQualityModel]


# --- Model fitting ----------------------------------------------------------


class FitPCARequest(ApiModel):
    """Request to fit a PCA model from a dataset and a preprocessing spec.

    If ``spec`` is omitted, a default spec is used: every quantitative column as
    X with unit-variance scaling.
    """

    dataset_id: str
    n_components: int = Field(ge=1)
    conf_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    name: str | None = None
    spec: PreprocessingSpecModel | None = None


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
    conf_level: float
    component_names: list[str]
    explained_variance: list[float]
    r2_cumulative: list[float]
    scores: ScoresPayload
    hotellings_t2: list[float]
    spe: list[float]
    t2_limit: float
    spe_limit: float


# --- Models: the Hangar and Logbook ----------------------------------------


class ModelSummary(ApiModel):
    """A model variant as listed in the Hangar."""

    id: int
    kind: str
    name: str | None
    n_components: int
    parent_id: int | None
    dataset_id: str | None
    created_at: datetime


class LoadingsPayload(ApiModel):
    """A loadings matrix, one row per variable."""

    component_names: list[str]
    variable_names: list[str]
    data: list[list[float]]


class ModelDiagnosticsModel(ApiModel):
    """Diagnostics for a fitted model."""

    kind: str
    n_components: int
    conf_level: float
    component_names: list[str]
    explained_variance: list[float]
    r2_per_component: list[float]
    r2_cumulative: list[float]
    scores: ScoresPayload
    x_loadings: LoadingsPayload
    y_loadings: LoadingsPayload | None
    hotellings_t2: list[float]
    spe: list[float]
    t2_limit: float
    spe_limit: float
    ellipse_x: list[float]
    ellipse_y: list[float]
    vip: dict[str, float]


class ModelDetail(ApiModel):
    """A model's Logbook: metadata, recipe, lineage, and diagnostics."""

    summary: ModelSummary
    preprocessing: dict
    excluded_samples: list[int]
    lineage: list[ModelSummary]
    diagnostics: ModelDiagnosticsModel | None


class ContributionsModel(ApiModel):
    """Per-variable contributions of one observation to T2 and SPE."""

    observation: int
    observation_name: str
    variable_names: list[str]
    t2: list[float]
    spe: list[float]


class FitModelRequest(ApiModel):
    """Request to fit a model variant from a dataset and a preprocessing spec.

    With ``auto_components`` the number of components is chosen by
    cross-validation (the Q2-optimal count) and ``n_components`` is used only as
    an upper bound on what is evaluated.
    """

    dataset_id: str
    kind: Literal["PCA", "PLS"] = "PCA"
    n_components: int = Field(ge=1)
    auto_components: bool = False
    conf_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    name: str | None = None
    parent_id: int | None = None
    spec: PreprocessingSpecModel | None = None


class UpdateModelRequest(ApiModel):
    """Patch a model's tunable hyperparameters in place (no refit-from-scratch)."""

    n_components: int = Field(ge=1)


class VariantRequest(ApiModel):
    """Create a child model variant from a brushed selection.

    ``observations`` are primary-identifier values and ``variables`` are column
    names (exactly what the plots' selection carries). In ``exclude`` mode the
    selected observations / variables are added to the parent's exclusions; in
    ``keep`` mode every *other* currently-active observation is excluded instead
    (variables are ignored in ``keep`` mode).
    """

    observations: list[str] = Field(default_factory=list)
    variables: list[str] = Field(default_factory=list)
    mode: Literal["exclude", "keep"] = "exclude"
    name: str | None = None


class CrossValidationModel(ApiModel):
    """Per-component calibration R2 and cross-validated Q2 for a model."""

    kind: str
    target: str
    n_splits: int
    component_numbers: list[int]
    r2: list[float]
    q2: list[float]
    r2_per_component: list[float]
    q2_per_component: list[float]
    recommended: int
