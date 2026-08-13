import math

import pytest

from tpm_app.core import (
    ScientificInputError,
    abraham_log_k,
    assess_applicability,
    critical_burden_from_observation,
    exposure_to_mmol_kg,
    individual_prediction_error,
    lfer_log_k,
    mg_l_to_neglog_mol_l,
    passive_dosing_series,
    plastic_phase_pnec,
    predict_lc50,
    prediction_metrics,
    summarize_mixture,
    substitute_censored_value,
    toxic_unit,
    water_concentration_to_plastic_mmol_kg,
)


def test_n_hexane_pdms_reference_prediction():
    prediction = predict_lc50(
        phase="PDMS",
        mode="baseline",
        log_k_phase_water=3.737698,
        neglog_critical_burden_mol_kg=1.4365611,
        molecular_weight_g_mol=86.1748,
    )
    assert prediction.predicted_neglog_lc50_mol_l == pytest.approx(5.1742591)
    assert prediction.predicted_lc50_mg_l == pytest.approx(
        10 ** (-5.1742591) * 86.1748 * 1000
    )


def test_reactive_prediction_is_blocked():
    with pytest.raises(ScientificInputError, match="Reactive-toxicant prediction is disabled"):
        predict_lc50("PDMS", "reactive", 3.0, 4.0, 100.0)


@pytest.mark.parametrize(
    ("value", "unit", "molecular_weight", "expected"),
    [
        (2.0, "mmol/kg", 100.0, 2.0),
        (0.002, "mol/kg", 100.0, 2.0),
        (200.0, "mg/kg", 100.0, 2.0),
        (200_000.0, "ug/kg", 100.0, 2.0),
        (200_000_000.0, "ng/kg", 100.0, 2.0),
        (0.2, "mg/g", 100.0, 2.0),
        (200.0, "ug/g", 100.0, 2.0),
        (200_000.0, "ng/g", 100.0, 2.0),
    ],
)
def test_exposure_unit_conversions(value, unit, molecular_weight, expected):
    assert exposure_to_mmol_kg(value, unit, molecular_weight) == pytest.approx(expected)


def test_molar_plastic_concentration_does_not_require_molecular_weight():
    assert exposure_to_mmol_kg(2.5, "mmol/kg", math.nan) == pytest.approx(2.5)
    assert exposure_to_mmol_kg(0.0025, "mol/kg", math.nan) == pytest.approx(2.5)


def test_water_concentration_requires_partitioning_for_plastic_equivalent():
    assert water_concentration_to_plastic_mmol_kg(
        100.0, "ng/L", 100.0, 4.0
    ) == pytest.approx(0.01)
    assert water_concentration_to_plastic_mmol_kg(
        0.001, "mmol/L", math.nan, 3.0
    ) == pytest.approx(1.0)


def test_mixture_summary_and_toxic_unit():
    units = [toxic_unit(5.0, 20.0), toxic_unit(10.0, 20.0)]
    summary = summarize_mixture(
        units,
        assessment_factor=1000.0,
        critical_burden_mmol_kg=20.0,
    )
    assert summary == {
        "sum_tu": 0.75,
        "assessment_factor": 1000.0,
        "risk_quotient": 750.0,
        "pnec_plastic_mmol_kg": 0.02,
    }


def test_plastic_phase_pnec_defaults_from_paper():
    critical_burden = 36.596445014812936
    assert plastic_phase_pnec(critical_burden, 1000) == pytest.approx(0.036596445014812936)
    assert plastic_phase_pnec(critical_burden, 10000) == pytest.approx(0.0036596445014812936)


def test_abraham_equation_uses_all_descriptors():
    descriptors = {"e": 1, "s": 2, "a": 3, "b": 4, "v": 5, "l": 6}
    coefficients = {"intercept": 0.5, "e": 1, "s": 1, "a": 1, "b": 1, "v": 1, "l": 1}
    assert abraham_log_k(descriptors, coefficients) == pytest.approx(21.5)


def test_one_parameter_lfer():
    assert lfer_log_k(4.0, intercept=0.5, slope=0.75) == pytest.approx(3.5)


def test_applicability_domain_distinguishes_inside_caution_and_outside():
    inside = assess_applicability(
        mode="baseline",
        phase_validated=True,
        partition_source="Measured log K",
        log_k_phase_water=3.0,
        domain_min=0.0,
        domain_max=6.0,
        ionization_status="Neutral",
        mode_confidence="Established",
    )
    caution = assess_applicability(
        mode="less_inert",
        phase_validated=True,
        partition_source="log Kow LFER",
        log_k_phase_water=3.0,
        domain_min=0.0,
        domain_max=6.0,
        ionization_status="Unknown",
        mode_confidence="Provisional",
        method_documented=False,
    )
    outside = assess_applicability(
        mode="baseline",
        phase_validated=True,
        partition_source="Measured log K",
        log_k_phase_water=8.0,
        domain_min=0.0,
        domain_max=6.0,
        ionization_status="Predominantly ionized",
        mode_confidence="Established",
    )
    assert inside.status == "inside"
    assert caution.status == "caution"
    assert outside.status == "outside"


def test_record_level_critical_burden_conversion():
    result = critical_burden_from_observation(5.0, 3.0)
    assert result["neglog_critical_burden_mol_kg"] == pytest.approx(2.0)
    assert result["critical_burden_mmol_kg"] == pytest.approx(10.0)


def test_nondetect_substitution_is_explicit():
    assert substitute_censored_value(1.0, "=", None, "Zero") == pytest.approx(1.0)
    assert substitute_censored_value(0.0, "ND", 0.2, "Half detection limit") == pytest.approx(0.1)
    assert substitute_censored_value(0.2, "<", None, "Detection limit") == pytest.approx(0.2)


def test_passive_dosing_series_is_anchored_at_critical_burden():
    rows = passive_dosing_series(
        critical_burden_mmol_kg=20.0,
        log_k_phase_water=3.0,
        molecular_weight_g_mol=100.0,
        polymer_mass_g=1.0,
        minimum_fraction=0.1,
        maximum_fraction=10.0,
        number_of_doses=3,
        hill_slope=1.0,
    )
    assert rows[1]["fraction_of_critical_burden"] == pytest.approx(1.0)
    assert rows[1]["polymer_burden_mmol_kg"] == pytest.approx(20.0)
    assert rows[1]["ideal_water_concentration_mg_l"] == pytest.approx(2.0)
    assert rows[1]["illustrative_response_pct"] == pytest.approx(50.0)


def test_lc50_round_trip():
    neglog = mg_l_to_neglog_mol_l(2.5, 125.0)
    reconstructed = 10 ** (-neglog) * 125.0 * 1000.0
    assert reconstructed == pytest.approx(2.5)


def test_prediction_metrics_use_log_factor_bands():
    observed = [1.0, 2.0, 3.0]
    predicted = [1.0, 2.2, 4.1]
    metrics = prediction_metrics(observed, predicted)
    assert metrics["n"] == 3
    assert metrics["within_factor_2_pct"] == pytest.approx(200 / 3)
    assert metrics["within_factor_5_pct"] == pytest.approx(200 / 3)
    assert metrics["within_factor_10_pct"] == pytest.approx(200 / 3)
    assert metrics["bias"] == pytest.approx((0.0 + 0.2 + 1.1) / 3)
    assert math.isfinite(metrics["rmse"])


def test_individual_prediction_error_changes_with_record():
    exact = individual_prediction_error(4.0, 4.0)
    high = individual_prediction_error(4.0, 4.5)
    low = individual_prediction_error(4.0, 3.0)
    assert exact["fold_difference"] == pytest.approx(1.0)
    assert high["fold_difference"] == pytest.approx(10**0.5)
    assert high["lc50_ratio"] == pytest.approx(10**-0.5)
    assert low["fold_difference"] == pytest.approx(10.0)
    assert low["lc50_ratio"] == pytest.approx(10.0)
