"""Tests for the PCA wrapper in ``scorepilot.core``."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scorepilot.core import Preprocessing, fit_pca


@pytest.fixture
def two_factor_data() -> pd.DataFrame:
    """A 40x5 block generated from two latent factors plus small noise."""
    rng = np.random.default_rng(0)
    n, k = 40, 5
    latent = rng.normal(size=(n, 2))
    loadings = rng.normal(size=(2, k))
    x = latent @ loadings + 0.05 * rng.normal(size=(n, k))
    return pd.DataFrame(
        x,
        columns=[f"v{i}" for i in range(k)],
        index=[f"obs{i}" for i in range(n)],
    )


def test_fit_pca_shapes_and_labels(two_factor_data: pd.DataFrame) -> None:
    result = fit_pca(two_factor_data, n_components=2)

    assert result.n_components == 2
    assert result.component_names == ["PC1", "PC2"]
    assert result.scores.shape == (40, 2)
    assert result.loadings.shape == (5, 2)
    assert list(result.scores.columns) == ["PC1", "PC2"]
    assert list(result.scores.index) == list(two_factor_data.index)
    assert list(result.loadings.index) == list(two_factor_data.columns)
    assert result.explained_variance.shape == (2,)
    assert result.hotellings_t2.shape == (40,)
    assert result.spe.shape == (40,)


def test_fit_pca_two_factors_dominate_variance(two_factor_data: pd.DataFrame) -> None:
    result = fit_pca(two_factor_data, n_components=2)

    # r2 is cumulative, non-decreasing, bounded by 1, and two factors explain
    # almost all variance of two-factor data.
    r2 = result.r2_cumulative.to_numpy()
    assert np.all(np.diff(r2) >= -1e-9)
    assert r2[-1] <= 1.0 + 1e-9
    assert r2[-1] > 0.95

    assert result.t2_limit > 0
    assert result.spe_limit >= 0


def test_fit_pca_without_scaling_runs(two_factor_data: pd.DataFrame) -> None:
    result = fit_pca(two_factor_data, n_components=1, preprocessing=Preprocessing.NONE)
    assert result.preprocessing is Preprocessing.NONE
    assert result.scores.shape == (40, 1)


@pytest.mark.parametrize("n_components", [0, 6])
def test_fit_pca_rejects_out_of_range_components(
    two_factor_data: pd.DataFrame, n_components: int
) -> None:
    with pytest.raises(ValueError, match="n_components"):
        fit_pca(two_factor_data, n_components=n_components)
