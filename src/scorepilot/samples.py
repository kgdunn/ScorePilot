"""Bundled sample datasets so the app is useful on first run.

The CSVs in ``sample_data/`` are loaded through the same import path as an upload,
so they behave exactly like a user-provided dataset.
"""

from __future__ import annotations

import gzip
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
    Sample(
        name="raw-material-properties",
        filename="raw-material-properties.csv",
        title="Raw material properties",
        description="36 raw-material lots; 6 particle-size and density measurements.",
        source_url="https://openmv.net/info/raw-material-properties",
    ),
    Sample(
        name="silicon-wafer-thickness",
        filename="silicon-wafer-thickness.csv",
        title="Silicon wafer thickness",
        description="Thickness at 9 gauge positions across 184 silicon wafers.",
        source_url="https://openmv.net/info/silicon-wafer-thickness",
    ),
    Sample(
        name="solvents",
        filename="solvents.csv",
        title="Solvent properties",
        description="Physical properties of 103 common solvents; includes missing values.",
        source_url="https://openmv.net/info/solvents",
    ),
    Sample(
        name="tablet-spectra",
        filename="tablet-spectra.csv.gz",
        title="Tablet NIR spectra",
        description="Near-infrared spectra of 460 tablets at 650 wavelengths; a spectral PCA demo.",
        source_url="https://openmv.net/info/tablet-spectra",
    ),
)


def get_sample(name: str) -> Sample | None:
    """Return the sample with ``name``, or ``None`` if unknown."""
    return next((s for s in SAMPLES if s.name == name), None)


def load_sample_frame(sample: Sample) -> pd.DataFrame:
    """Read a bundled sample file into a DataFrame, decompressing ``.gz`` blobs.

    Large samples (e.g. spectra) are stored gzipped to keep the wheel small.
    """
    raw = (files("scorepilot").joinpath("sample_data", sample.filename)).read_bytes()
    filename = sample.filename
    if filename.endswith(".gz"):
        raw = gzip.decompress(raw)
        filename = filename[: -len(".gz")]
    frame, _source, _sheets, _used = load_table(raw, filename)
    return frame
