"""Tests for cross-validated component selection (PCA and PLS)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scorepilot.core import PreprocessingSpec, apply_spec, cross_validate


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
    assert 1 <= cv.recommended <= 2


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
