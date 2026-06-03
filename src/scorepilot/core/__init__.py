"""Numerical engine for ScorePilot.

Pure functions over numpy arrays / pandas DataFrames that wrap the
``process_improve`` chemometrics library. This package must never import
FastAPI, SQLAlchemy, or any other web/DB dependency: the boundary is
load-bearing and keeps the numerics independently testable.
"""

from scorepilot.core.pca import PCAResult, fit_pca
from scorepilot.core.preprocessing import Preprocessing, prepare

__all__ = ["PCAResult", "Preprocessing", "fit_pca", "prepare"]
