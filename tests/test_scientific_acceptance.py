"""Independent acceptance calculations tied to the paper and SI workbook."""

import hashlib
from pathlib import Path

import pytest

from tpm_app.core import (
    exposure_to_mmol_kg,
    plastic_phase_pnec,
    summarize_mixture,
    toxic_unit,
    water_concentration_to_plastic_mmol_kg,
)
from tpm_app.data import ROOT, burden_record, critical_burdens, dataset_manifest


EXPECTED_SI_SHA256 = "c6a7637d78cc92b5e043e296f3f59a023743168cd8a02375419455312faf4e2b"


def test_si_workbook_identity_when_available():
    source = ROOT.parent / "ci4c00574_si_002.xlsx"
    if not source.exists():
        pytest.skip("The source SI workbook is intentionally outside the public repository.")
    assert hashlib.sha256(source.read_bytes()).hexdigest() == EXPECTED_SI_SHA256
    assert dataset_manifest()["source"]["sha256"] == EXPECTED_SI_SHA256


@pytest.mark.parametrize(
    ("mode", "phase", "expected_mmol_kg"),
    [
        ("baseline", "PDMS", 36.596445014812936),
        ("baseline", "PA", 51.327801965934746),
        ("baseline", "POM", 19.20074146719083),
        ("baseline", "PE", 24.95492103708058),
        ("baseline", "PU", 0.1655094704516409),
        ("less_inert", "PDMS", 0.8587048187228404),
        ("less_inert", "PA", 26.622693973640573),
        ("less_inert", "POM", 6.898309358853262),
        ("less_inert", "PE", 1.600297270067045),
        ("less_inert", "PU", 0.04415521461690436),
    ],
)
def test_median_plastic_burdens_reproduce_si(mode, phase, expected_mmol_kg):
    assert burden_record(mode, phase)["critical_burden_mmol_kg"] == pytest.approx(
        expected_mmol_kg, rel=1e-12
    )


def test_published_baseline_evaluation_rmse_range_is_reproduced():
    burdens = critical_burdens()
    values = burdens[
        (burdens["toxic_mode"] == "baseline")
        & burdens["phase"].isin(["PDMS", "PA", "POM", "PE", "PU"])
    ]["rmse_evaluation_log_unit"]
    assert round(float(values.min()), 3) == 0.311
    assert round(float(values.max()), 3) == 0.538


def test_direct_naphthalene_example_matches_independent_hand_calculation():
    # 10 ng/g = 0.010 mg/kg; 0.010/128.1702 = 7.8021256e-5 mmol/kg.
    measured = exposure_to_mmol_kg(10.0, "ng/g", 128.1702)
    burden = burden_record("baseline", "PDMS")["critical_burden_mmol_kg"]
    component_tu = toxic_unit(measured, burden)
    pnec = plastic_phase_pnec(burden, 1000.0)
    result = summarize_mixture([component_tu], 1000.0, burden)

    assert measured == pytest.approx(7.80212561110149e-5, rel=1e-12)
    assert component_tu == pytest.approx(2.13193538551175e-6, rel=1e-12)
    assert pnec == pytest.approx(0.0365964450148129, rel=1e-12)
    assert result["risk_quotient"] == pytest.approx(0.00213193538551175, rel=1e-12)
    assert result["risk_quotient"] == pytest.approx(measured / pnec, rel=1e-12)


def test_water_pathway_is_partition_dependent_and_keeps_molar_units():
    # 1 ng/L naphthalene = 7.8021256e-9 mmol/L; logK=3 gives
    # 7.8021256e-6 mmol/kg plastic-equivalent.
    converted = water_concentration_to_plastic_mmol_kg(
        1.0, "ng/L", 128.1702, 3.0
    )
    assert converted == pytest.approx(7.80212561110149e-6, rel=1e-12)


def test_three_component_mixture_matches_equations_9_to_11():
    burden = burden_record("baseline", "POM")["critical_burden_mmol_kg"]
    components = [toxic_unit(value, burden) for value in (0.1, 0.2, 0.3)]
    result = summarize_mixture(components, 1000.0, burden)

    assert result["sum_tu"] == pytest.approx(0.0312487932315138, rel=1e-12)
    assert result["risk_quotient"] == pytest.approx(31.2487932315138, rel=1e-12)
    assert result["pnec_plastic_mmol_kg"] == pytest.approx(
        0.0192007414671908, rel=1e-12
    )
