"""Tests for the data-exploration core: profiling, quality, transforms, workset."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
import pytest

from scorepilot.core import (
    ColumnType,
    PreprocessingSpec,
    ScalingKind,
    TransformKind,
    VariableTransform,
    apply_spec,
    apply_transform,
    histogram,
    infer_column_type,
    quality_report,
    sequence,
    suggest_transform,
    variable_summary,
)


@pytest.fixture
def mixed_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "id": ["a", "b", "c", "c", "d"],  # duplicate "c"
            "amount": [1.0, 2.0, np.nan, 4.0, 5.0],
            "label": ["x", "y", "x", "z", "x"],
            "when": ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
            "textnum": ["1", "2", "oops", "4", "5"],  # 80% numeric, one invalid
        }
    )


def _col(frame: pd.DataFrame, name: str) -> pd.Series:
    return cast("pd.Series", frame[name])


def test_infer_column_type(mixed_frame: pd.DataFrame) -> None:
    assert infer_column_type(_col(mixed_frame, "amount")) is ColumnType.QUANTITATIVE
    assert infer_column_type(_col(mixed_frame, "label")) is ColumnType.QUALITATIVE
    assert infer_column_type(_col(mixed_frame, "when")) is ColumnType.DATETIME
    # 80% parse as numeric -> still quantitative.
    assert infer_column_type(_col(mixed_frame, "textnum")) is ColumnType.QUANTITATIVE


def test_variable_summary_quantitative() -> None:
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0], name="v")
    summary = variable_summary(s)
    assert summary.column_type is ColumnType.QUANTITATIVE
    assert summary.n == 5
    assert summary.n_missing == 0
    assert summary.mean == pytest.approx(3.0)
    assert summary.minimum == 1.0
    assert summary.maximum == 5.0
    assert summary.min_max_ratio == pytest.approx(5.0)


def test_variable_summary_counts_missing() -> None:
    s = pd.Series([1.0, np.nan, 3.0], name="v")
    summary = variable_summary(s)
    assert summary.n == 2
    assert summary.n_missing == 1
    assert summary.pct_missing == pytest.approx(100 / 3)


def test_histogram_and_sequence() -> None:
    s = pd.Series([0.0, 1.0, 1.0, 2.0, np.nan])
    counts, edges = histogram(s, bins=2)
    assert sum(counts) == 4  # missing excluded
    assert len(edges) == 3
    assert sequence(s) == [0.0, 1.0, 1.0, 2.0, None]


def test_quality_report_flags(mixed_frame: pd.DataFrame) -> None:
    types = {str(name): infer_column_type(s) for name, s in mixed_frame.items()}
    report = quality_report(mixed_frame, types=types, primary_id="id")

    assert report.primary_id_unique is False
    assert report.duplicate_primary_ids[0].value == "c"
    assert report.duplicate_primary_ids[0].rows == [2, 3]

    textnum = next(c for c in report.columns if c.name == "textnum")
    assert textnum.n_invalid == 1
    assert textnum.invalid_rows == [2]

    amount = next(c for c in report.columns if c.name == "amount")
    assert amount.n_missing == 1


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (TransformKind.NONE, 4.0),
        (TransformKind.LOG, np.log(4.0)),
        (TransformKind.EXPONENTIAL, np.exp(4.0)),
    ],
)
def test_apply_transform(kind: TransformKind, expected: float) -> None:
    out = apply_transform(pd.Series([4.0]), kind)
    assert out.iloc[0] == pytest.approx(expected)


def test_apply_transform_out_of_domain_is_nan() -> None:
    out = apply_transform(pd.Series([-1.0]), TransformKind.LOG)
    assert np.isnan(out.iloc[0])


def test_suggest_transform_for_skewed_positive() -> None:
    rng = np.random.default_rng(0)
    skewed = pd.Series(np.exp(rng.normal(size=500)) * 100, name="v")
    assert suggest_transform(variable_summary(skewed)) is TransformKind.LOG


def test_apply_spec_selects_transforms_and_scales() -> None:
    df = pd.DataFrame(
        {
            "a": [1.0, 2.0, 3.0, 4.0],
            "b": [10.0, 20.0, 30.0, 40.0],
            "drop_me": [1.0, 1.0, 1.0, 1.0],
            "y": [0.0, 1.0, 0.0, 1.0],
        }
    )
    spec = PreprocessingSpec(
        x_columns=("a", "b"),
        y_columns=("y",),
        excluded_columns=("drop_me",),
        default_scaling=ScalingKind.UNIT_VARIANCE,
    )
    applied = apply_spec(df, spec)
    assert list(applied.X.columns) == ["a", "b"]
    assert applied.Y is not None
    # Autoscaled columns are mean-centered to ~0 and unit std.
    assert applied.X["a"].mean() == pytest.approx(0.0, abs=1e-9)
    assert applied.X["a"].std(ddof=1) == pytest.approx(1.0, abs=1e-9)


def test_two_specs_over_one_dataset_differ() -> None:
    df = pd.DataFrame({"a": [1.0, 10.0, 100.0, 1000.0], "b": [1.0, 2.0, 3.0, 4.0]})
    plain = apply_spec(df, PreprocessingSpec(x_columns=("a", "b")))
    logged = apply_spec(
        df,
        PreprocessingSpec(
            x_columns=("a", "b"),
            transforms={"a": VariableTransform(kind=TransformKind.LOG)},
        ),
    )
    # The same dataset yields different X under different specs.
    assert not np.allclose(plain.X["a"].to_numpy(), logged.X["a"].to_numpy())


def test_apply_spec_excludes_rows() -> None:
    df = pd.DataFrame({"a": [1.0, 2.0, 3.0, 4.0]})
    applied = apply_spec(df, PreprocessingSpec(x_columns=("a",), excluded_rows=(0, 1)))
    assert applied.X.shape[0] == 2


def test_spec_round_trips_through_dict() -> None:
    spec = PreprocessingSpec(
        x_columns=("a", "b"),
        y_columns=("y",),
        excluded_rows=(3,),
        transforms={"a": VariableTransform(kind=TransformKind.LOG, c1=1.0)},
        scaling={"b": ScalingKind.PARETO},
    )
    restored = PreprocessingSpec.from_dict(spec.to_dict())
    assert restored == spec
