"""Pydantic v2 request/response models for the HTTP API."""

from __future__ import annotations

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


class GridWindow(ApiModel):
    """A windowed block of cells for the data grid."""

    row_offset: int
    column_names: list[str]
    row_identifiers: list[str | None]
    cells: list[list[str | None]]


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
