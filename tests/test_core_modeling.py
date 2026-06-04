"""Tests for fit_model (PCA and PLS) and its diagnostics."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scorepilot.core import PreprocessingSpec, apply_spec, fit_model


@pytest.fixture
def xy() -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(0)
    n = 40
    latent = rng.normal(size=(n, 2))
    px = rng.normal(size=(2, 5))
    py = rng.normal(size=(2, 2))
    xcols = [f"x{i}" for i in range(5)]
    x = pd.DataFrame(latent @ px + 0.05 * rng.normal(size=(n, 5)), columns=xcols)
    y = pd.DataFrame(latent @ py + 0.05 * rng.normal(size=(n, 2)), columns=["y0", "y1"])
    return x, y


def test_fit_pca_diagnostics(xy: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    x, _ = xy
    applied = apply_spec(x, PreprocessingSpec(x_columns=tuple(x.columns)))
    diag = fit_model(applied.X, None, "PCA", 2)

    assert diag.kind == "PCA"
    assert diag.component_names == ["PC1", "PC2"]
    assert diag.scores.shape == (40, 2)
    assert diag.x_loadings.shape == (5, 2)
    assert diag.y_loadings is None
    assert len(diag.ellipse_x) == 100
    assert set(diag.vip) == set(x.columns)
    assert diag.r2_cumulative[-1] > 0.95
    assert diag.t2_limit > 0


def test_fit_pls_diagnostics(xy: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    x, y = xy
    spec = PreprocessingSpec(x_columns=tuple(x.columns), y_columns=("y0", "y1"))
    combined = pd.concat([x, y], axis=1)
    applied = apply_spec(combined, spec)
    diag = fit_model(applied.X, applied.Y, "PLS", 2)

    assert diag.kind == "PLS"
    assert diag.y_loadings is not None
    assert diag.y_variable_names == ["y0", "y1"]
    assert diag.scores.shape == (40, 2)


def test_fit_pls_without_y_raises(xy: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    x, _ = xy
    applied = apply_spec(x, PreprocessingSpec(x_columns=tuple(x.columns)))
    with pytest.raises(ValueError, match="PLS requires"):
        fit_model(applied.X, None, "PLS", 2)


def test_fit_model_unknown_kind_raises(xy: tuple[pd.DataFrame, pd.DataFrame]) -> None:
    x, _ = xy
    applied = apply_spec(x, PreprocessingSpec(x_columns=tuple(x.columns)))
    with pytest.raises(ValueError, match="Unknown model kind"):
        fit_model(applied.X, None, "QPCA", 2)
