"""Run deterministic scientific and repository checks for a TPM release."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_VERSION = "1.2.0"
EXPECTED_SI_SHA256 = "c6a7637d78cc92b5e043e296f3f59a023743168cd8a02375419455312faf4e2b"
EXPECTED_DATA_HASHES = {
    "critical_burdens.csv": "ca4e891b6441a3054ad3aa646184df04bbae52d454c80e5a76504a3d39a1fab1",
    "dataset_manifest.json": "7f0cdba6eeb5bbd5adee6c2c5a9bb5e96b3a278db0448ae256e5a60fa057e43a",
    "model_registry.json": "5aad9e4058225a52f3261a3a07dc6642ed5886371051f1f7d8ad58f02bd70fc8",
    "other_plastics.csv": "cff1bca46416734738678b2fcb9d63f83d16248dd72293f4dd5ac58b6cbae711",
    "validation_records.csv": "2855740b5457ad67a7f2b393cf64ef2a7691e3f48dbb656cd2aefe98ec75a067",
}


def sha256(path: Path, *, canonical_text: bool = False) -> str:
    content = path.read_bytes()
    if canonical_text:
        content = content.replace(b"\r\n", b"\n")
    return hashlib.sha256(content).hexdigest()


def read_csv(name: str) -> list[dict[str, str]]:
    with (ROOT / "data" / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    failures: list[str] = []
    passed: list[str] = []
    notes: list[str] = []

    def check(condition: bool, label: str) -> None:
        (passed if condition else failures).append(label)

    for name, expected in EXPECTED_DATA_HASHES.items():
        check(
            sha256(ROOT / "data" / name, canonical_text=True) == expected,
            f"release hash: data/{name}",
        )

    manifest = json.loads((ROOT / "data" / "dataset_manifest.json").read_text(encoding="utf-8"))
    registry = json.loads((ROOT / "data" / "model_registry.json").read_text(encoding="utf-8"))
    zenodo = json.loads((ROOT / ".zenodo.json").read_text(encoding="utf-8"))
    version_text = (ROOT / "tpm_app" / "__init__.py").read_text(encoding="utf-8")
    citation_text = (ROOT / "CITATION.cff").read_text(encoding="utf-8")

    check(manifest["source"]["sha256"] == EXPECTED_SI_SHA256, "SI hash in manifest")
    check(registry["model"]["version"] == EXPECTED_VERSION, "model-registry version")
    check(f'__version__ = "{EXPECTED_VERSION}"' in version_text, "package version")
    check(zenodo.get("version") == EXPECTED_VERSION, "Zenodo version")
    check(f"version: {EXPECTED_VERSION}" in citation_text, "CFF version")
    check("github.com/OWNER" not in citation_text, "no placeholder repository URL")

    expected_counts = {
        "baseline_evaluation": 115,
        "baseline_validation": 132,
        "less_inert_evaluation": 73,
        "less_inert_validation": 128,
        "reactive_evaluation": 75,
    }
    records = read_csv("validation_records.csv")
    observed_counts = {
        key: sum(row["set_key"] == key for row in records) for key in expected_counts
    }
    check(observed_counts == expected_counts, "paper/SI cohort counts")

    burdens = read_csv("critical_burdens.csv")
    baseline_plastics = [
        float(row["rmse_evaluation_log_unit"])
        for row in burdens
        if row["toxic_mode"] == "baseline" and row["phase"] in {"PDMS", "PA", "POM", "PE", "PU"}
    ]
    check(round(min(baseline_plastics), 3) == 0.311, "baseline minimum evaluation RMSE")
    check(round(max(baseline_plastics), 3) == 0.538, "baseline maximum evaluation RMSE")

    reactive = [
        row
        for row in burdens
        if row["toxic_mode"] == "reactive" and row["phase"] in {"PDMS", "PA", "POM", "PE", "PU"}
    ]
    reactive_values = [float(row["critical_burden_mmol_kg"]) for row in reactive]
    check(
        math.isclose(min(reactive_values), 0.0010010500140370132, rel_tol=1e-12)
        and math.isclose(max(reactive_values), 0.6780535592271908, rel_tol=1e-12),
        "reactive mol/kg-to-mmol/kg conversion",
    )
    check(all(row["calculator_status"] == "not_supported" for row in reactive), "reactive prediction lockout")

    source = ROOT.parent / manifest["source"]["file"]
    if source.exists():
        check(sha256(source) == EXPECTED_SI_SHA256, "local SI workbook identity")
    else:
        notes.append("Source SI workbook absent; local identity check skipped as expected for a public clone.")

    secret = ROOT / ".streamlit" / "secrets.toml"
    if secret.exists():
        notes.append("Local Streamlit secrets file exists; confirm it remains git-ignored before committing.")

    result = {
        "release": EXPECTED_VERSION,
        "status": "PASS" if not failures else "FAIL",
        "passed_checks": len(passed),
        "failed_checks": failures,
        "notes": notes,
    }
    print(json.dumps(result, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
