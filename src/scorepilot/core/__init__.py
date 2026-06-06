"""Numerical engine for ScorePilot.

Pure functions over numpy arrays / pandas DataFrames that wrap the
``process_improve`` chemometrics library. This package must never import
FastAPI, SQLAlchemy, or any other web/DB dependency: the boundary is
load-bearing and keeps the numerics independently testable.
"""

from scorepilot.core.cross_validation import CrossValidation, cross_validate
from scorepilot.core.modeling import (
    Contributions,
    ModelDiagnostics,
    fit_model,
    observation_contributions,
)
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
    "Contributions",
    "CrossValidation",
    "IdentifierRole",
    "ModelDiagnostics",
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
    "cross_validate",
    "fit_model",
    "fit_pca",
    "histogram",
    "infer_column_type",
    "observation_contributions",
    "prepare",
    "quality_report",
    "sequence",
    "suggest_transform",
    "variable_summary",
]
