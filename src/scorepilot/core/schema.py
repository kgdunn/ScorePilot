"""Shared enumerations for datasets and preprocessing.

These ``StrEnum`` types are the vocabulary used across ``core``, the API schemas,
and persisted preprocessing recipes. They are plain string enums so they serialize
cleanly to JSON and round-trip through ``Model.preprocessing``.
"""

from __future__ import annotations

from enum import StrEnum


class ColumnType(StrEnum):
    """The kind of data a column holds.

    A column's type is intrinsic to the dataset (what the data *is*), independent
    of how any particular model uses it.
    """

    QUANTITATIVE = "quantitative"
    QUALITATIVE = "qualitative"
    DATETIME = "datetime"
    UNKNOWN = "unknown"


class IdentifierRole(StrEnum):
    """Whether a column identifies or classifies observations.

    Like :class:`ColumnType`, identifier roles describe the dataset itself, not a
    modelling choice.
    """

    NONE = "none"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    CLASS = "class"


class TransformKind(StrEnum):
    """A per-variable transform applied as part of a preprocessing recipe."""

    NONE = "none"
    LINEAR = "linear"
    LOG = "log"
    NEGLOG = "neglog"
    LOGIT = "logit"
    EXPONENTIAL = "exponential"
    POWER = "power"


class ScalingKind(StrEnum):
    """A per-variable scaling applied after transformation."""

    NONE = "none"
    UNIT_VARIANCE = "unit_variance"
    PARETO = "pareto"
