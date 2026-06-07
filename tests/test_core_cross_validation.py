"""Tests for cross-validated component selection (PCA and PLS)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scorepilot.core import PreprocessingSpec, apply_spec, cross_validate
from scorepilot.core.cross_validation import PCA_RULES, PLS_RULES


@pytest.fixture
def rank2() -> tuple[pd.DataFrame, pd.DataFrame]:
    """X and Y driven by a 2-component latent structure with light noise."""
    rng = np.random.default_rng(0)
    n = 60
    latent = rng.normal(size=(n, 2))
    px = rng.normal(size=(2, 6))
    py = rng.normal(size=(2, 1))
    x = pd.DataFrame(
        latent @ px + 0.05 * rng.normal(size=(n, 6)), columns=[f"x{i}" for i in range(6)]
    )
    y = pd.DataFrame(latent @ py + 0.05 * rng.normal(size=(n, 1)), columns=["y"])
    return x, y


def test_pca_cross_validation_curves(rank2: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    x, _ = rank2
    applied = apply_spec(x, PreprocessingSpec(x_columns=tuple(x.columns)))
    cv = cross_validate(applied.X, None, "PCA", max_components=5)

    assert cv.kind == "PCA"
    assert cv.target == "X"
    assert cv.component_numbers == [1, 2, 3, 4, 5]
    assert len(cv.r2) == len(cv.q2) == 5
    # R2 is cumulative and non-decreasing; Q2 never exceeds R2 (out-of-sample).
    assert cv.r2 == sorted(cv.r2)
    assert all(q <= r + 1e-9 for q, r in zip(cv.q2, cv.r2, strict=True))
    # Two latent components explain almost everything.
    assert cv.q2[1] > 0.9
    # The recommendation comes from the library's selector; just sanity-check it.
    assert 1 <= cv.recommended <= 5


def test_pls_cross_validation_targets_y(rank2: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    x, y = rank2
    combined = pd.concat([x, y], axis=1)
    spec = PreprocessingSpec(x_columns=tuple(x.columns), y_columns=("y",))
    applied = apply_spec(combined, spec)
    cv = cross_validate(applied.X, applied.Y, "PLS", max_components=5)

    assert cv.target == "Y"
    assert cv.q2[-1] > 0.9
    assert cv.recommended >= 1


def test_pls_cross_validation_requires_y(rank2: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    x, _ = rank2
    applied = apply_spec(x, PreprocessingSpec(x_columns=tuple(x.columns)))
    with pytest.raises(ValueError, match="requires at least one Y"):
        cross_validate(applied.X, None, "PLS")


def test_cross_validation_unknown_kind(rank2: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    x, _ = rank2
    applied = apply_spec(x, PreprocessingSpec(x_columns=tuple(x.columns)))
    with pytest.raises(ValueError, match="Unknown model kind"):
        cross_validate(applied.X, None, "QPCA")


def test_default_rule_metadata(rank2: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    """Per-kind defaults and metadata are reported on the result."""
    x, y = rank2
    pca = cross_validate(
        apply_spec(x, PreprocessingSpec(x_columns=tuple(x.columns))).X,
        None,
        "PCA",
        max_components=5,
    )
    # PCA defaults to the lowest-error rule on element-wise k-fold, single pass.
    assert pca.selection_rule == "min"
    assert pca.cv_scheme == "ekf"
    assert pca.n_repeats == 1
    assert pca.recommended_is_stable is None  # PCA does not vote across repeats

    combined = pd.concat([x, y], axis=1)
    spec = PreprocessingSpec(x_columns=tuple(x.columns), y_columns=("y",))
    applied = apply_spec(combined, spec)
    pls = cross_validate(applied.X, applied.Y, "PLS", max_components=5)
    # PLS defaults to the 1-SE rule on repeated K-fold.
    assert pls.selection_rule == "1se"
    assert pls.cv_scheme is None
    assert pls.n_repeats == 10
    assert isinstance(pls.recommended_is_stable, bool)


def test_pca_selection_rules_and_schemes(rank2: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    x, _ = rank2
    block = apply_spec(x, PreprocessingSpec(x_columns=tuple(x.columns))).X
    for rule in PCA_RULES:
        cv = cross_validate(block, None, "PCA", max_components=5, selection_rule=rule)
        assert cv.selection_rule == rule
        assert 1 <= cv.recommended <= 5
    # The legacy row-wise scheme is still selectable.
    cv = cross_validate(block, None, "PCA", max_components=5, cv_scheme="row_wise")
    assert cv.cv_scheme == "row_wise"


def test_pls_selection_rules(rank2: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    x, y = rank2
    spec = PreprocessingSpec(x_columns=tuple(x.columns), y_columns=("y",))
    applied = apply_spec(pd.concat([x, y], axis=1), spec)
    for rule in PLS_RULES:
        cv = cross_validate(applied.X, applied.Y, "PLS", max_components=5, selection_rule=rule)
        assert cv.selection_rule == rule
        assert cv.recommended >= 1


def test_pca_rejects_randomization(rank2: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    x, _ = rank2
    block = apply_spec(x, PreprocessingSpec(x_columns=tuple(x.columns))).X
    with pytest.raises(ValueError, match="not supported for PCA"):
        cross_validate(block, None, "PCA", selection_rule="randomization")


def test_collinear_pls_raises_value_error() -> None:
    """A rank-deficient X makes the in-fold PLS inversion ill-conditioned; the
    adapter surfaces that as a clean ValueError rather than a raw LinAlgError."""
    rng = np.random.default_rng(0)
    base = rng.normal(size=(40, 2))
    # Six columns spanning only a 2D space (each a duplicate of the two bases).
    x = pd.DataFrame(
        np.hstack([base, base, base]), columns=[f"x{i}" for i in range(6)]
    )
    y = pd.DataFrame(base @ rng.normal(size=(2, 1)), columns=["y"])
    spec = PreprocessingSpec(x_columns=tuple(x.columns), y_columns=("y",))
    applied = apply_spec(pd.concat([x, y], axis=1), spec)
    with pytest.raises(ValueError, match="singular|ill-conditioned|collinear|variance"):
        cross_validate(applied.X, applied.Y, "PLS", max_components=6)
