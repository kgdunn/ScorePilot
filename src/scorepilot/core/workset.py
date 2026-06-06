"""Preprocessing recipes (worksets) over an immutable dataset.

A dataset is raw and shared. The choices that define a *model variant* - which
columns are X or Y, which rows/columns are excluded, and the per-variable
transform and scaling - live in a :class:`PreprocessingSpec`. One dataset has many
specs (one per variant), and a spec serializes to/from plain JSON so it can be
stored on a model and evolved along a lineage.

``apply_spec`` turns a dataset plus a spec into the model-ready X (and Y) matrices:
it selects columns, drops excluded rows/columns, applies each variable's transform,
then mean-centers and scales. The result is ready to fit with no further scaling.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from process_improve.multivariate import MCUVScaler

from scorepilot.core._pandas import column as get_column
from scorepilot.core._pandas import to_numeric
from scorepilot.core.schema import ScalingKind, TransformKind
from scorepilot.core.transforms import apply_transform


@dataclass(frozen=True)
class VariableTransform:
    """A transform and its constants for one variable."""

    kind: TransformKind = TransformKind.NONE
    c1: float = 0.0
    c2: float = 1.0

    def to_dict(self) -> dict[str, object]:
        return {"kind": self.kind.value, "c1": self.c1, "c2": self.c2}

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> VariableTransform:
        return cls(
            kind=TransformKind(str(data.get("kind", TransformKind.NONE.value))),
            c1=float(data.get("c1", 0.0)),  # type: ignore[arg-type]
            c2=float(data.get("c2", 1.0)),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class PreprocessingSpec:
    """A model variant's preprocessing recipe over a dataset.

    Attributes
    ----------
    x_columns, y_columns
        Column names assigned to the X and Y blocks.
    excluded_rows
        Positional indices of excluded observations.
    excluded_columns
        Names of excluded variables (removed from X and Y when applying).
    transforms
        Per-variable transform. Columns absent from the mapping are untransformed.
    default_scaling
        Scaling used for columns without an explicit override.
    scaling
        Per-variable scaling override.
    """

    x_columns: tuple[str, ...]
    y_columns: tuple[str, ...] = ()
    excluded_rows: tuple[int, ...] = ()
    excluded_columns: tuple[str, ...] = ()
    transforms: Mapping[str, VariableTransform] = field(default_factory=dict)
    default_scaling: ScalingKind = ScalingKind.UNIT_VARIANCE
    scaling: Mapping[str, ScalingKind] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Serialize to a JSON-friendly dict (for ``Model.preprocessing``)."""
        return {
            "x_columns": list(self.x_columns),
            "y_columns": list(self.y_columns),
            "excluded_rows": list(self.excluded_rows),
            "excluded_columns": list(self.excluded_columns),
            "transforms": {k: v.to_dict() for k, v in self.transforms.items()},
            "default_scaling": self.default_scaling.value,
            "scaling": {k: v.value for k, v in self.scaling.items()},
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, object]) -> PreprocessingSpec:
        """Rebuild a spec from its serialized form."""
        transforms_raw: Mapping[str, Mapping[str, object]] = data.get("transforms", {})  # type: ignore[assignment]
        scaling_raw: Mapping[str, str] = data.get("scaling", {})  # type: ignore[assignment]
        return cls(
            x_columns=tuple(data.get("x_columns", [])),  # type: ignore[arg-type]
            y_columns=tuple(data.get("y_columns", [])),  # type: ignore[arg-type]
            excluded_rows=tuple(int(i) for i in data.get("excluded_rows", [])),  # type: ignore[union-attr]
            excluded_columns=tuple(data.get("excluded_columns", [])),  # type: ignore[arg-type]
            transforms={k: VariableTransform.from_dict(v) for k, v in transforms_raw.items()},
            default_scaling=ScalingKind(
                str(data.get("default_scaling", ScalingKind.UNIT_VARIANCE.value))
            ),
            scaling={k: ScalingKind(v) for k, v in scaling_raw.items()},
        )


@dataclass(frozen=True)
class AppliedWorkset:
    """The model-ready matrices produced by :func:`apply_spec`."""

    X: pd.DataFrame
    Y: pd.DataFrame | None


def apply_spec(df: pd.DataFrame, spec: PreprocessingSpec) -> AppliedWorkset:
    """Apply a preprocessing spec to a dataset, returning the X (and Y) matrices.

    Columns are coerced to numeric, transformed per the spec, then mean-centered
    and scaled. Excluded rows and columns are dropped. The result needs no further
    scaling before fitting.

    Raises
    ------
    ValueError
        If no X columns remain after applying exclusions.
    """
    excluded_cols = set(spec.excluded_columns)
    excluded_rows = set(spec.excluded_rows)
    active_rows = [i for i in range(len(df)) if i not in excluded_rows]

    x_cols = [c for c in spec.x_columns if c in df.columns and c not in excluded_cols]
    if not x_cols:
        msg = "The preprocessing spec selects no X columns after exclusions."
        raise ValueError(msg)

    rows = df.iloc[active_rows]
    x_block = _build_block(rows, x_cols, spec)

    y_cols = [c for c in spec.y_columns if c in df.columns and c not in excluded_cols]
    y_block = _build_block(rows, y_cols, spec) if y_cols else None

    return AppliedWorkset(X=x_block, Y=y_block)


def _build_block(rows: pd.DataFrame, columns: list[str], spec: PreprocessingSpec) -> pd.DataFrame:
    block = pd.DataFrame({c: to_numeric(get_column(rows, c)) for c in columns})
    block = _apply_transforms(block, spec.transforms)
    return _center_scale(block, spec.scaling, spec.default_scaling)


def _apply_transforms(
    frame: pd.DataFrame, transforms: Mapping[str, VariableTransform]
) -> pd.DataFrame:
    out = frame.copy()
    for name in list(out.columns):
        spec = transforms.get(str(name))
        if spec is not None and spec.kind is not TransformKind.NONE:
            transformed = apply_transform(
                get_column(out, str(name)), spec.kind, c1=spec.c1, c2=spec.c2
            )
            out[name] = transformed
    return out


def _center_scale(
    frame: pd.DataFrame,
    scaling: Mapping[str, ScalingKind],
    default: ScalingKind,
) -> pd.DataFrame:
    """Mean-center every column and apply each column's scaling.

    The centering and unit-variance scaling come from ``process_improve``'s
    ``MCUVScaler`` (mean centre, divide by the ``ddof=1`` standard deviation, and
    leave zero-variance columns centred only). Pareto scaling reuses the same
    fitted statistics - dividing by ``sqrt(std)`` instead of ``std`` - so every
    scaling kind shares one source of truth for the column means and spreads.
    """
    numeric = frame.astype(float)
    scaler = MCUVScaler().fit(numeric)
    centered = numeric - scaler.center_
    unit_variance = scaler.transform(numeric)  # mean-centred, unit variance

    out = numeric.copy()
    for name in list(out.columns):
        kind = scaling.get(str(name), default)
        if kind is ScalingKind.UNIT_VARIANCE:
            out[name] = unit_variance[name]
        elif kind is ScalingKind.PARETO:
            # MCUVScaler stores std (zero-variance -> 1.0); sqrt(std) is Pareto,
            # and sqrt(1.0) leaves a zero-variance column centred only.
            out[name] = centered[name] / np.sqrt(scaler.scale_[name])
        else:  # ScalingKind.NONE
            out[name] = centered[name]
    return out
