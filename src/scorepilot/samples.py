"""Bundled sample datasets so the app is useful on first run.

The CSVs in ``sample_data/`` are loaded through the same import path as an upload,
so they behave exactly like a user-provided dataset.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files

import pandas as pd

from scorepilot.dataset_store import load_table


@dataclass(frozen=True)
class Sample:
    """A bundled demo dataset."""

    name: str  # URL-safe id
    filename: str
    title: str
    description: str
    source_url: str


SAMPLES: tuple[Sample, ...] = (
    Sample(
        name="ldpe",
        filename="ldpe.csv",
        title="LDPE process data",
        description="54 low-density-polyethylene reactor runs; 19 numeric process variables.",
        source_url="https://openmv.net/info/ldpe",
    ),
    Sample(
        name="food-consumption",
        filename="food-consumption.csv",
        title="Food consumption",
        description="Consumption of 20 foods across European countries; includes missing values.",
        source_url="https://openmv.net/info/food-consumption",
    ),
)


def get_sample(name: str) -> Sample | None:
    """Return the sample with ``name``, or ``None`` if unknown."""
    return next((s for s in SAMPLES if s.name == name), None)


def load_sample_frame(sample: Sample) -> pd.DataFrame:
    """Read a bundled sample CSV into a DataFrame."""
    raw = (files("scorepilot").joinpath("sample_data", sample.filename)).read_bytes()
    frame, _source, _sheets, _used = load_table(raw, sample.filename)
    return frame
