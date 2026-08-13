import hashlib
from pathlib import Path

import pytest

from tpm_app.data import (
    ROOT,
    burden_record,
    critical_burdens,
    dataset_manifest,
    model_registry,
    other_plastics,
    validation_records,
)


def test_published_cohort_counts():
    records = validation_records()
    counts = records.groupby("set_key").size().to_dict()
    assert counts == {
        "baseline_evaluation": 115,
        "baseline_validation": 132,
        "less_inert_evaluation": 73,
        "less_inert_validation": 128,
        "reactive_evaluation": 75,
    }


def test_critical_burden_registry_shape_and_reference_values():
    burdens = critical_burdens()
    assert len(burdens) == 21
    assert burden_record("baseline", "PDMS")["neglog_critical_burden_mol_kg"] == pytest.approx(1.4365611)
    assert burden_record("less_inert", "PU")["neglog_critical_burden_mol_kg"] == pytest.approx(4.355018)
    assert burden_record("reactive", "PU")["neglog_critical_burden_mol_kg"] == pytest.approx(5.99954422)


def test_reactive_unit_conversion_range_is_explicit():
    burdens = critical_burdens()
    reactive_plastics = burdens[
        (burdens["toxic_mode"] == "reactive")
        & (burdens["phase"].isin(["PDMS", "PA", "POM", "PE", "PU"]))
    ]
    assert reactive_plastics["critical_burden_mmol_kg"].min() == pytest.approx(0.0010010499, rel=1e-6)
    assert reactive_plastics["critical_burden_mmol_kg"].max() == pytest.approx(0.6780538, rel=1e-6)
    assert set(reactive_plastics["calculator_status"]) == {"not_supported"}


def test_only_paper_validated_phases_are_enabled():
    registry = model_registry()
    enabled = {phase for phase, metadata in registry["phases"].items() if metadata["validated"]}
    assert enabled == {"PDMS", "PA", "POM", "PE", "PU"}
    assert registry["modes"]["reactive"]["calculator_status"] == "not_supported"


def test_logkow_screening_registry_distinguishes_published_and_derived_equations():
    registry = model_registry()["log_kow_lfer"]
    assert set(registry) == {"PDMS", "PA", "POM", "PE", "PU"}
    assert registry["PE"]["status"] == "published_screening"
    assert registry["PE"]["intercept"] == pytest.approx(-0.696)
    assert registry["PE"]["slope"] == pytest.approx(1.059)
    assert all(
        registry[phase]["status"] == "dashboard_derived_screening"
        for phase in ["PDMS", "PA", "POM", "PU"]
    )


def test_other_plastic_counts():
    records = other_plastics()
    assert records.groupby("plastic").size().to_dict() == {
        "HDPE": 10,
        "Polypropylene": 9,
        "Polystyrene": 8,
        "Polyvinyl Chloride": 29,
        "UHMWPE": 3,
    }


def test_source_workbook_hash_when_source_is_available():
    manifest = dataset_manifest()
    source = ROOT.parent / manifest["source"]["file"]
    if not source.exists():
        pytest.skip("The public repository intentionally omits the source workbook.")
    assert hashlib.sha256(source.read_bytes()).hexdigest() == manifest["source"]["sha256"]
