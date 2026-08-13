"""Transparent scientific calculations for the Target Plastic Model.

All internal concentrations use mol/L for water and mol/kg for the receiving
phase. Display conversions are performed only at the application boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping


class ScientificInputError(ValueError):
    """Raised when an input would make a calculation scientifically invalid."""


@dataclass(frozen=True)
class Prediction:
    phase: str
    mode: str
    log_k_phase_water: float
    neglog_critical_burden_mol_kg: float
    predicted_neglog_lc50_mol_l: float
    predicted_lc50_mol_l: float
    predicted_lc50_mg_l: float


@dataclass(frozen=True)
class ApplicabilityAssessment:
    """Structured applicability-domain result for a TPM prediction."""

    status: str
    label: str
    reasons: tuple[str, ...]
    warnings: tuple[str, ...]


def lfer_log_k(log_kow: float, intercept: float, slope: float) -> float:
    """Calculate log10(Kphase-water) from a documented one-parameter LFER."""

    return finite_number(intercept, "LFER intercept") + finite_number(
        slope, "LFER slope"
    ) * finite_number(log_kow, "log Kow")


def assess_applicability(
    *,
    mode: str,
    phase_validated: bool,
    partition_source: str,
    log_k_phase_water: float,
    domain_min: float,
    domain_max: float,
    ionization_status: str,
    mode_confidence: str,
    method_documented: bool = True,
) -> ApplicabilityAssessment:
    """Assess whether a requested prediction resembles the paper's model domain.

    This is a transparent rule-based screen, not a statistical leverage model.
    The numerical range is supplied by the relevant model-development cohort.
    """

    log_k = finite_number(log_k_phase_water, "log Kphase-water")
    lower = finite_number(domain_min, "domain minimum")
    upper = finite_number(domain_max, "domain maximum")
    if lower > upper:
        raise ScientificInputError("Applicability-domain bounds are reversed.")

    reasons: list[str] = []
    warnings: list[str] = []
    outside = False

    if mode == "reactive":
        outside = True
        reasons.append("Reactive toxicants are outside the supported predictive domain.")
    elif mode == "less_inert":
        warnings.append("Less-inert predictions require a defensible polar-narcosis assignment.")

    if not phase_validated:
        outside = True
        reasons.append("The selected phase is not one of the five paper-validated plastics.")

    ionization = str(ionization_status).strip().casefold()
    if ionization == "predominantly ionized":
        outside = True
        reasons.append("The TPM was developed for neutral organic chemicals, not predominantly ionized species.")
    elif ionization in {"partly ionized", "unknown"}:
        warnings.append("Ionization at the relevant pH is not fully resolved.")

    confidence = str(mode_confidence).strip().casefold()
    if confidence == "unknown":
        warnings.append("The toxic-mode assignment is unknown.")
    elif confidence == "provisional":
        warnings.append("The toxic-mode assignment is provisional.")

    if not (lower <= log_k <= upper):
        outside = True
        reasons.append(
            f"log K ({log_k:.3f}) is outside the development-cohort range "
            f"({lower:.3f} to {upper:.3f})."
        )

    source = str(partition_source).strip().casefold()
    if source in {"log kow lfer", "other predicted log k"}:
        warnings.append("The partition coefficient comes from a secondary prediction method.")
    if not method_documented and source not in {"published compound", "measured log k"}:
        warnings.append("The partition-coefficient prediction method lacks a documented source.")

    if outside:
        return ApplicabilityAssessment("outside", "Outside domain", tuple(reasons), tuple(warnings))
    if warnings:
        return ApplicabilityAssessment(
            "caution", "Supported with caution", tuple(reasons), tuple(warnings)
        )
    return ApplicabilityAssessment(
        "inside",
        "Inside domain",
        ("Inputs are within the paper-aligned screening rules.",),
        (),
    )


def finite_number(value: object, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ScientificInputError(f"{label} must be numeric.") from exc
    if not math.isfinite(result):
        raise ScientificInputError(f"{label} must be finite.")
    return result


def abraham_log_k(descriptors: Mapping[str, float], coefficients: Mapping[str, float]) -> float:
    """Calculate log10(Kphase-water) from an Abraham solvation equation."""

    total = finite_number(coefficients.get("intercept", 0.0), "intercept")
    for descriptor in ("e", "s", "a", "b", "v", "l"):
        total += finite_number(descriptors.get(descriptor), descriptor.upper()) * finite_number(
            coefficients.get(descriptor, 0.0), f"coefficient {descriptor}"
        )
    return total


def predict_lc50(
    phase: str,
    mode: str,
    log_k_phase_water: float,
    neglog_critical_burden_mol_kg: float,
    molecular_weight_g_mol: float,
) -> Prediction:
    """Predict acute fish LC50 using -logLC50 = logK + -logCcrit."""

    if mode == "reactive":
        raise ScientificInputError(
            "Reactive-toxicant prediction is disabled: the paper treats these values as "
            "out of the Target Plastic Model's predictive domain."
        )
    log_k = finite_number(log_k_phase_water, "log Kphase-water")
    neglog_c = finite_number(neglog_critical_burden_mol_kg, "-log critical burden")
    molecular_weight = finite_number(molecular_weight_g_mol, "molecular weight")
    if molecular_weight <= 0:
        raise ScientificInputError("Molecular weight must be greater than zero.")
    predicted_neglog = log_k + neglog_c
    mol_l = 10 ** (-predicted_neglog)
    return Prediction(
        phase=phase,
        mode=mode,
        log_k_phase_water=log_k,
        neglog_critical_burden_mol_kg=neglog_c,
        predicted_neglog_lc50_mol_l=predicted_neglog,
        predicted_lc50_mol_l=mol_l,
        predicted_lc50_mg_l=mol_l * molecular_weight * 1000.0,
    )


def mg_l_to_neglog_mol_l(lc50_mg_l: float, molecular_weight_g_mol: float) -> float:
    lc50 = finite_number(lc50_mg_l, "LC50")
    molecular_weight = finite_number(molecular_weight_g_mol, "molecular weight")
    if lc50 <= 0 or molecular_weight <= 0:
        raise ScientificInputError("LC50 and molecular weight must be greater than zero.")
    return -math.log10(lc50 / (molecular_weight * 1000.0))


def exposure_to_mmol_kg(value: float, unit: str, molecular_weight_g_mol: float) -> float:
    """Convert a plastic concentration to mmol/kg.

    Supported mass units assume the entered mass refers to the parent chemical.
    """

    concentration = finite_number(value, "exposure concentration")
    if concentration < 0:
        raise ScientificInputError("Exposure must be non-negative.")
    if unit == "mmol/kg":
        return concentration
    if unit == "mol/kg":
        return concentration * 1000.0
    molecular_weight = finite_number(molecular_weight_g_mol, "molecular weight")
    if molecular_weight <= 0:
        raise ScientificInputError(
            "Molecular weight must be positive when converting a mass-based concentration."
        )
    conversions = {
        "mg/kg": lambda x: x / molecular_weight,
        "ug/kg": lambda x: x * 1e-3 / molecular_weight,
        "ng/kg": lambda x: x * 1e-6 / molecular_weight,
        "mg/g": lambda x: x * 1000.0 / molecular_weight,
        "ug/g": lambda x: x / molecular_weight,
        "ng/g": lambda x: x * 1e-3 / molecular_weight,
    }
    if unit not in conversions:
        raise ScientificInputError(f"Unsupported exposure unit: {unit}")
    return conversions[unit](concentration)


def water_concentration_to_plastic_mmol_kg(
    value: float,
    unit: str,
    molecular_weight_g_mol: float,
    log_k_phase_water: float,
) -> float:
    """Convert a water-column concentration to an equilibrium plastic equivalent.

    Unlike the direct plastic-measurement pathway, this conversion necessarily
    requires a plastic-water partition coefficient.
    """

    concentration = finite_number(value, "water concentration")
    log_k = finite_number(log_k_phase_water, "log Kphase-water")
    if concentration < 0:
        raise ScientificInputError("Water concentration must be non-negative.")
    if unit == "mmol/L":
        water_mmol_l = concentration
    elif unit == "mol/L":
        water_mmol_l = concentration * 1000.0
    else:
        molecular_weight = finite_number(molecular_weight_g_mol, "molecular weight")
        if molecular_weight <= 0:
            raise ScientificInputError(
                "Molecular weight must be positive when converting a mass-based water concentration."
            )
        conversions = {
            "mg/L": lambda x: x / molecular_weight,
            "ug/L": lambda x: x * 1e-3 / molecular_weight,
            "ng/L": lambda x: x * 1e-6 / molecular_weight,
        }
        if unit not in conversions:
            raise ScientificInputError(f"Unsupported water concentration unit: {unit}")
        water_mmol_l = conversions[unit](concentration)
    return water_mmol_l * 10**log_k


def substitute_censored_value(
    concentration: float,
    qualifier: str,
    detection_limit: float | None,
    method: str,
) -> float:
    """Return a transparent numeric substitute for a censored mixture result."""

    value = finite_number(concentration, "concentration")
    if value < 0:
        raise ScientificInputError("Concentration must be non-negative.")
    normalized = str(qualifier).strip().upper()
    if normalized in {"=", "DETECTED"}:
        return value
    if normalized not in {"<", "ND"}:
        raise ScientificInputError(f"Unsupported result qualifier: {qualifier}")
    limit = value if normalized == "<" and detection_limit in (None, "") else finite_number(
        detection_limit, "detection limit"
    )
    if limit < 0:
        raise ScientificInputError("Detection limit must be non-negative.")
    fractions = {"zero": 0.0, "half detection limit": 0.5, "detection limit": 1.0}
    key = str(method).strip().casefold()
    if key not in fractions:
        raise ScientificInputError(f"Unsupported nondetect method: {method}")
    return limit * fractions[key]


def critical_burden_from_observation(
    observed_neglog_lc50_mol_l: float, log_k_phase_water: float
) -> dict[str, float]:
    """Calculate a record-level critical burden from observed LC50 and log K."""

    neglog_burden = finite_number(
        observed_neglog_lc50_mol_l, "observed -log LC50"
    ) - finite_number(log_k_phase_water, "log Kphase-water")
    mol_kg = 10 ** (-neglog_burden)
    return {
        "neglog_critical_burden_mol_kg": neglog_burden,
        "critical_burden_mol_kg": mol_kg,
        "critical_burden_mmol_kg": mol_kg * 1000.0,
    }


def passive_dosing_series(
    *,
    critical_burden_mmol_kg: float,
    log_k_phase_water: float,
    molecular_weight_g_mol: float,
    polymer_mass_g: float,
    minimum_fraction: float,
    maximum_fraction: float,
    number_of_doses: int,
    hill_slope: float = 1.0,
) -> list[dict[str, float]]:
    """Design an idealized logarithmic passive-dosing series around Ccrit.

    The response column is a Hill illustration anchored to 50% at Ccrit. It is
    not a fitted biological dose-response model.
    """

    burden = finite_number(critical_burden_mmol_kg, "critical burden")
    log_k = finite_number(log_k_phase_water, "log Kphase-water")
    molecular_weight = finite_number(molecular_weight_g_mol, "molecular weight")
    mass_g = finite_number(polymer_mass_g, "polymer mass")
    low = finite_number(minimum_fraction, "minimum Ccrit fraction")
    high = finite_number(maximum_fraction, "maximum Ccrit fraction")
    slope = finite_number(hill_slope, "Hill slope")
    try:
        count = int(number_of_doses)
    except (TypeError, ValueError) as exc:
        raise ScientificInputError("Number of doses must be an integer.") from exc
    if burden <= 0 or molecular_weight <= 0 or mass_g <= 0:
        raise ScientificInputError("Critical burden, molecular weight, and polymer mass must be positive.")
    if low <= 0 or high <= 0 or low >= high:
        raise ScientificInputError("Dose fractions must be positive and minimum must be below maximum.")
    if count < 2 or count > 50:
        raise ScientificInputError("Number of doses must be between 2 and 50.")
    if slope <= 0:
        raise ScientificInputError("Hill slope must be positive.")

    log_low = math.log10(low)
    step = (math.log10(high) - log_low) / (count - 1)
    partition_coefficient = 10**log_k
    polymer_mass_kg = mass_g / 1000.0
    rows: list[dict[str, float]] = []
    for index in range(count):
        fraction = 10 ** (log_low + index * step)
        polymer_burden = burden * fraction
        water_mmol_l = polymer_burden / partition_coefficient
        rows.append(
            {
                "dose_number": float(index + 1),
                "fraction_of_critical_burden": fraction,
                "polymer_burden_mmol_kg": polymer_burden,
                "chemical_loaded_mg": polymer_burden * molecular_weight * polymer_mass_kg,
                "ideal_water_concentration_mmol_l": water_mmol_l,
                "ideal_water_concentration_mg_l": water_mmol_l * molecular_weight,
                "illustrative_response_pct": 100.0 * fraction**slope / (1.0 + fraction**slope),
            }
        )
    return rows


def toxic_unit(exposure_mmol_kg: float, critical_burden_mmol_kg: float) -> float:
    exposure = finite_number(exposure_mmol_kg, "exposure")
    burden = finite_number(critical_burden_mmol_kg, "critical burden")
    if exposure < 0 or burden <= 0:
        raise ScientificInputError("Exposure must be non-negative and critical burden positive.")
    return exposure / burden


def plastic_phase_pnec(critical_burden_mmol_kg: float, assessment_factor: float) -> float:
    """Derive the plastic-phase PNEC equivalent as Ccrit / AF."""

    burden = finite_number(critical_burden_mmol_kg, "critical burden")
    factor = finite_number(assessment_factor, "assessment factor")
    if burden <= 0 or factor <= 0:
        raise ScientificInputError("Critical burden and assessment factor must be greater than zero.")
    return burden / factor


def summarize_mixture(
    toxic_units: Iterable[float],
    assessment_factor: float,
    critical_burden_mmol_kg: float | None = None,
) -> dict[str, float]:
    values = [finite_number(value, "toxic unit") for value in toxic_units]
    if any(value < 0 for value in values):
        raise ScientificInputError("Toxic units cannot be negative.")
    factor = finite_number(assessment_factor, "assessment factor")
    if factor <= 0:
        raise ScientificInputError("Assessment factor must be greater than zero.")
    total = sum(values)
    result = {
        "sum_tu": total,
        "assessment_factor": factor,
        "risk_quotient": total * factor,
    }
    if critical_burden_mmol_kg is not None:
        result["pnec_plastic_mmol_kg"] = plastic_phase_pnec(
            critical_burden_mmol_kg, factor
        )
    return result


def prediction_metrics(observed: Iterable[float], predicted: Iterable[float]) -> dict[str, float | int]:
    pairs = [
        (finite_number(obs, "observed value"), finite_number(pred, "predicted value"))
        for obs, pred in zip(observed, predicted)
    ]
    if not pairs:
        return {
            "n": 0,
            "rmse": math.nan,
            "mae": math.nan,
            "bias": math.nan,
            "within_factor_2_pct": math.nan,
            "within_factor_5_pct": math.nan,
            "within_factor_10_pct": math.nan,
        }
    errors = [pred - obs for obs, pred in pairs]
    return {
        "n": len(errors),
        "rmse": math.sqrt(sum(error * error for error in errors) / len(errors)),
        "mae": sum(abs(error) for error in errors) / len(errors),
        "bias": sum(errors) / len(errors),
        "within_factor_2_pct": 100.0 * sum(abs(error) <= math.log10(2) for error in errors) / len(errors),
        "within_factor_5_pct": 100.0 * sum(abs(error) <= math.log10(5) for error in errors) / len(errors),
        "within_factor_10_pct": 100.0 * sum(abs(error) <= 1.0 for error in errors) / len(errors),
    }


def individual_prediction_error(observed_neglog: float, predicted_neglog: float) -> dict[str, float]:
    """Return record-specific error on log and fold-difference scales.

    The fold difference is always at least one. ``lc50_ratio`` retains direction:
    values below one mean the predicted LC50 concentration is lower than observed.
    """

    observed = finite_number(observed_neglog, "observed -log LC50")
    predicted = finite_number(predicted_neglog, "predicted -log LC50")
    log_error = predicted - observed
    return {
        "log_error": log_error,
        "fold_difference": 10 ** abs(log_error),
        "lc50_ratio": 10 ** (-log_error),
    }
