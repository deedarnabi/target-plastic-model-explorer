"""Versioned local data access for the Target Plastic Model Explorer."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


@lru_cache(maxsize=1)
def model_registry() -> dict:
    return json.loads((DATA_DIR / "model_registry.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def dataset_manifest() -> dict:
    return json.loads((DATA_DIR / "dataset_manifest.json").read_text(encoding="utf-8"))


def validation_records() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "validation_records.csv")


def critical_burdens() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "critical_burdens.csv")


def other_plastics() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "other_plastics.csv")


def burden_record(mode: str, phase: str) -> dict:
    records = critical_burdens()
    selected = records[(records["toxic_mode"] == mode) & (records["phase"] == phase)]
    if selected.empty:
        raise KeyError(f"No critical burden is registered for {mode}/{phase}.")
    return selected.iloc[0].to_dict()


def phase_log_k_column(phase: str) -> str:
    aliases = {
        "phospholipid": "log_k_phospholipid_water",
        "octanol": "log_k_octanol_water",
        "PDMS": "log_k_pdms_water",
        "PA": "log_k_pa_water",
        "POM": "log_k_pom_water",
        "PE": "log_k_pe_water",
        "PU": "log_k_pu_water",
    }
    return aliases[phase]
