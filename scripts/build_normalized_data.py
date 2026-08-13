"""Normalize the published TPM supporting workbook without loading styled empty cells.

The ACS workbook contains useful row-level data in fewer than 100 columns, but its
worksheets also contain formatting across nearly Excel's full column range. Reading
the XLSX as Open XML avoids importing millions of styled empty cells.
"""

from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "ci4c00574_si_002.xlsx"
DATA_DIR = ROOT / "data"
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def column_number(reference: str) -> int:
    match = re.match(r"[A-Z]+", reference)
    result = 0
    for character in match.group(0) if match else "":
        result = result * 26 + ord(character) - 64
    return result


def column_reference(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def cell_value(cell: ET.Element, strings: list[str]):
    value = cell.find(f"{NS}v")
    if value is None or value.text is None:
        inline = cell.find(f"{NS}is/{NS}t")
        return inline.text if inline is not None else None
    if cell.attrib.get("t") == "s":
        return strings[int(value.text)]
    try:
        return float(value.text)
    except ValueError:
        return value.text


def load_sheet(
    archive: zipfile.ZipFile,
    target: str,
    strings: list[str],
    max_column: int = 99,
) -> list[dict[str, object]]:
    rows: dict[int, dict[str, object]] = defaultdict(dict)
    with archive.open(target) as stream:
        for _, cell in ET.iterparse(stream, events=("end",)):
            if cell.tag != f"{NS}c":
                continue
            reference = cell.attrib.get("r", "")
            column = column_number(reference)
            if column <= max_column:
                match = re.search(r"(\d+)$", reference)
                row_number = int(match.group(1)) if match else 0
                value = cell_value(cell, strings)
                if value is not None:
                    rows[row_number][column_reference(column)] = value
            cell.clear()
    return [row for number, row in sorted(rows.items()) if number > 1 and row]


def numeric(value):
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def rmse(values: list[float]) -> float | None:
    return math.sqrt(sum(value * value for value in values) / len(values)) if values else None


def write_csv(path: Path, records: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def normalize_core_row(row, metadata, other_columns):
    common = {
        "source_sheet": metadata["sheet"],
        "set_key": metadata["set_key"],
        "set_label": metadata["set_label"],
        "set_role": metadata["role"],
        "toxic_mode": metadata["mode"],
        "record_id": int(row["A"]),
        "query": row.get("B"),
        "name": row.get("C"),
        "casrn": row.get("D"),
        "smiles": row.get("E"),
        "experimental_neglog_lc50_mol_l": numeric(row.get("F")),
        "molecular_weight_g_mol": numeric(row.get("G")),
        "chemical_class": row.get("H"),
        "ecosar_class": row.get("I"),
        "log_kow_epi": numeric(row.get("J")),
        "abraham_e": numeric(row.get("L")),
        "abraham_s": numeric(row.get("M")),
        "abraham_a": numeric(row.get("N")),
        "abraham_b": numeric(row.get("O")),
        "abraham_v": numeric(row.get("P")),
        "abraham_l": numeric(row.get("Q")),
        "literature": row.get("R"),
        "log_k_phospholipid_water": numeric(row.get("T")),
        "log_k_storage_lipid_water": numeric(row.get("U")),
        "log_k_pooled_lipid_water": numeric(row.get("V")),
        "log_k_muscle_protein_water": numeric(row.get("W")),
        "log_k_serum_protein_water": numeric(row.get("X")),
        "log_k_octanol_water": numeric(row.get("Y")),
        "log_k_pdms_water": numeric(row.get("Z")),
        "log_k_pa_water": numeric(row.get("AA")),
        "log_k_pom_water": numeric(row.get("AB")),
        "log_k_pe_water": numeric(row.get("AC")),
        "log_k_pu_water": numeric(row.get("AD")),
        "prediction_asm_neglog_lc50": numeric(row.get(other_columns[0])),
        "prediction_ecosar_neglog_lc50": numeric(row.get(other_columns[1])),
        "prediction_bl_neglog_lc50": numeric(row.get(other_columns[2])),
        "prediction_lim_neglog_lc50": numeric(row.get(other_columns[3])),
    }
    return common


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f"Supporting workbook not found: {SOURCE}")

    sheet_specs = [
        {
            "sheet": "Table_S1-Baseline_Evaluation",
            "set_key": "baseline_evaluation",
            "set_label": "Baseline evaluation",
            "role": "evaluation",
            "mode": "baseline",
            "other": ("CM", "CN", "CO", "CP"),
        },
        {
            "sheet": "Table_S2-Baseline_Validation",
            "set_key": "baseline_validation",
            "set_label": "Baseline validation",
            "role": "validation",
            "mode": "baseline",
            "other": ("CC", "CD", "CE", "CF"),
        },
        {
            "sheet": "Table_S3-Less_Inert_Evaluation",
            "set_key": "less_inert_evaluation",
            "set_label": "Less-inert evaluation",
            "role": "evaluation",
            "mode": "less_inert",
            "other": ("CM", "CN", "CO", "CP"),
        },
        {
            "sheet": "Table_S4-Less_Inert_Validation",
            "set_key": "less_inert_validation",
            "set_label": "Less-inert validation",
            "role": "validation",
            "mode": "less_inert",
            "other": ("CM", "CN", "CO", "CP"),
        },
        {
            "sheet": "Table_S5-Reactive_Toxicants",
            "set_key": "reactive_evaluation",
            "set_label": "Reactive evaluation",
            "role": "evaluation",
            "mode": "reactive",
            "other": ("CM", "CN", "CO", "CP"),
        },
    ]

    with zipfile.ZipFile(SOURCE) as archive:
        shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
        strings = ["".join(node.itertext()) for node in shared_root.findall(f"{NS}si")]
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
        relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"
        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in relationships.findall(f"{rel_ns}Relationship")
        }
        rel_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        targets = {}
        for sheet in workbook.find(f"{NS}sheets"):
            target = rel_map[sheet.attrib[rel_attr]].lstrip("/")
            targets[sheet.attrib["name"]] = target if target.startswith("xl/") else f"xl/{target}"

        raw_by_key = {}
        normalized = []
        for spec in sheet_specs:
            rows = load_sheet(archive, targets[spec["sheet"]], strings)
            rows = [row for row in rows if numeric(row.get("A")) is not None and row.get("C")]
            raw_by_key[spec["set_key"]] = rows
            normalized.extend(normalize_core_row(row, spec, spec["other"]) for row in rows)

        other_rows = load_sheet(
            archive,
            targets["Table_S6_OtherPlastics"],
            strings,
            max_column=54,
        )

    phase_map = {
        "phospholipid": "log_k_phospholipid_water",
        "octanol": "log_k_octanol_water",
        "PDMS": "log_k_pdms_water",
        "PA": "log_k_pa_water",
        "POM": "log_k_pom_water",
        "PE": "log_k_pe_water",
        "PU": "log_k_pu_water",
    }
    critical_source_columns = {
        "phospholipid": "AW",
        "octanol": "AX",
        "PDMS": "AY",
        "PA": "AZ",
        "POM": "BA",
        "PE": "BB",
        "PU": "BC",
    }
    mode_sources = {
        "baseline": ("baseline_evaluation", "baseline_validation"),
        "less_inert": ("less_inert_evaluation", "less_inert_validation"),
        "reactive": ("reactive_evaluation", None),
    }
    normalized_by_set = defaultdict(list)
    for record in normalized:
        normalized_by_set[record["set_key"]].append(record)

    burden_records = []
    for mode, (evaluation_key, validation_key) in mode_sources.items():
        raw_evaluation = raw_by_key[evaluation_key]
        for order, (phase, k_column) in enumerate(phase_map.items(), start=1):
            values = [
                numeric(row.get(critical_source_columns[phase]))
                for row in raw_evaluation
                if numeric(row.get(critical_source_columns[phase])) is not None
            ]
            neglog = statistics.median(values)
            mol_kg = 10 ** (-neglog)

            def residuals(set_key):
                if not set_key:
                    return []
                result = []
                for record in normalized_by_set[set_key]:
                    observed = numeric(record["experimental_neglog_lc50_mol_l"])
                    log_k = numeric(record[k_column])
                    if observed is not None and log_k is not None:
                        result.append(log_k + neglog - observed)
                return result

            burden_records.append(
                {
                    "toxic_mode": mode,
                    "phase": phase,
                    "display_order": order,
                    "neglog_critical_burden_mol_kg": neglog,
                    "critical_burden_mol_kg": mol_kg,
                    "critical_burden_mmol_kg": mol_kg * 1000,
                    "n_evaluation": len(normalized_by_set[evaluation_key]),
                    "rmse_evaluation_log_unit": rmse(residuals(evaluation_key)),
                    "n_validation": len(normalized_by_set[validation_key]) if validation_key else 0,
                    "rmse_validation_log_unit": rmse(residuals(validation_key)),
                    "calculator_status": (
                        "supported"
                        if mode == "baseline"
                        else "supported_with_caution"
                        if mode == "less_inert"
                        else "not_supported"
                    ),
                    "evidence_tier": (
                        "reference"
                        if phase in {"phospholipid", "octanol"}
                        else "paper_validated"
                        if mode != "reactive"
                        else "out_of_domain"
                    ),
                }
            )

    other_normalized = []
    current_plastic = None
    for row in other_rows:
        if isinstance(row.get("A"), str) and row["A"].strip():
            current_plastic = row["A"].strip()
        if not current_plastic or not row.get("B"):
            continue
        other_normalized.append(
            {
                "plastic": current_plastic,
                "name": row.get("B"),
                "casrn": row.get("C"),
                "smiles": row.get("D"),
                "ecosar_class": row.get("E"),
                "experimental_or_reference_neglog_lc50": numeric(row.get("F")),
                "log_kow_epi": numeric(row.get("H")),
                "abraham_e": numeric(row.get("J")),
                "abraham_s": numeric(row.get("K")),
                "abraham_a": numeric(row.get("L")),
                "abraham_b": numeric(row.get("M")),
                "abraham_v": numeric(row.get("N")),
                "abraham_l": numeric(row.get("O")),
                "literature": row.get("P"),
                "log_k_plastic_water": numeric(row.get("X")),
                "prediction_asm_neglog_lc50": numeric(row.get("AH")),
                "prediction_ecosar_neglog_lc50": numeric(row.get("AI")),
                "prediction_bl_neglog_lc50": numeric(row.get("AJ")),
                "prediction_lim_neglog_lc50": numeric(row.get("AK")),
                "neglog_critical_burden_mol_kg": numeric(row.get("AS")),
                "prediction_tpm_median_neglog_lc50": numeric(row.get("AX")),
                "evidence_tier": "exploratory",
            }
        )

    validation_fields = list(normalized[0])
    burden_fields = list(burden_records[0])
    other_fields = list(other_normalized[0])
    write_csv(DATA_DIR / "validation_records.csv", normalized, validation_fields)
    write_csv(DATA_DIR / "critical_burdens.csv", burden_records, burden_fields)
    write_csv(DATA_DIR / "other_plastics.csv", other_normalized, other_fields)

    checksum = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    manifest = {
        "schema_version": "1.0.0",
        "source": {
            "file": SOURCE.name,
            "sha256": checksum,
            "doi": "10.1021/acs.jcim.4c00574",
            "citation": (
                "Nabi, D.; Beck, A. J.; Achterberg, E. P. Assessing Aquatic Baseline "
                "Toxicity of Plastic-Associated Chemicals: Development and Validation "
                "of the Target Plastic Model. J. Chem. Inf. Model. 2024, 64, 6492-6505."
            ),
        },
        "datasets": {
            key: {"rows": len(rows), "source_sheet": next(s["sheet"] for s in sheet_specs if s["set_key"] == key)}
            for key, rows in normalized_by_set.items()
        },
        "other_plastics": {
            plastic: sum(record["plastic"] == plastic for record in other_normalized)
            for plastic in sorted({record["plastic"] for record in other_normalized})
        },
        "transformation": (
            "Values were extracted from cached Open XML cell values. Styled empty cells, "
            "charts, and workbook presentation formatting were excluded. Source rows were "
            "not altered. Derived critical burdens use Ccrit(mol/kg)=10^(-median[-log10 Ccrit])."
        ),
        "unit_note": (
            "The workbook stores reactive critical burdens as -log10(mol/kg). The app converts "
            "mol/kg to mmol/kg by multiplying by 1000. This yields 0.001001 to 0.678054 mmol/kg "
            "for the five reactive plastic phases; these calculations remain out of domain."
        ),
    }
    (DATA_DIR / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"validation_rows": len(normalized), "burden_rows": len(burden_records), "other_rows": len(other_normalized)}, indent=2))


if __name__ == "__main__":
    main()
