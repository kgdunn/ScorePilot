"""Numerical engine for ScorePilot.

Pure functions over numpy arrays / pandas DataFrames that wrap the
``process_improve`` chemometrics library. This package must never import
FastAPI, SQLAlchemy, or any other web/DB dependency: the boundary is
load-bearing and keeps the numerics independently testable.
"""

from scorepilot.core.pca import PCAResult, fit_pca
from scorepilot.core.preprocessing import Preprocessing, prepare
from scorepilot.core.profiling import (
    VariableSummary,
    histogram,
    infer_column_type,
    sequence,
    suggest_transform,
    variable_summary,
)
from scorepilot.core.quality import QualityReport, quality_report
from scorepilot.core.schema import (
    ColumnType,
    IdentifierRole,
    ScalingKind,
    TransformKind,
)
from scorepilot.core.transforms import apply_transform
from scorepilot.core.workset import (
    AppliedWorkset,
    PreprocessingSpec,
    VariableTransform,
    apply_spec,
)

__all__ = [
    "AppliedWorkset",
    "ColumnType",
    "IdentifierRole",
    "PCAResult",
    "Preprocessing",
    "PreprocessingSpec",
    "QualityReport",
    "ScalingKind",
    "TransformKind",
    "VariableSummary",
    "VariableTransform",
    "apply_spec",
    "apply_transform",
    "fit_pca",
    "histogram",
    "infer_column_type",
    "prepare",
    "quality_report",
    "sequence",
    "suggest_transform",
    "variable_summary",
]
