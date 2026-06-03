"""Small typing helpers that keep pandas results Series/DataFrame-typed.

``pd.to_numeric`` / ``pd.to_datetime`` / ``DataFrame.__getitem__`` are overloaded
to return broad unions, which the type checker cannot narrow. These thin wrappers
pin the expected concrete type for the common Series-in / Series-out case.
"""

from __future__ import annotations

from typing import cast

import pandas as pd


def to_numeric(series: pd.Series) -> pd.Series:
    """Coerce a series to numeric, with non-parsable entries as ``NaN``."""
    return cast("pd.Series", pd.to_numeric(series, errors="coerce"))


def to_datetime(series: pd.Series) -> pd.Series:
    """Coerce a series to datetimes, with non-parsable entries as ``NaT``."""
    return cast("pd.Series", pd.to_datetime(series, errors="coerce", format="mixed"))


def column(frame: pd.DataFrame, name: str) -> pd.Series:
    """Return a single column as a Series (assumes unique column labels)."""
    return cast("pd.Series", frame[name])
