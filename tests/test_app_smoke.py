from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from tpm_app.comptox import (
    CompToxEvidenceBundle,
    CompToxIdentity,
    FishLC50Evidence,
    LogKowEvidence,
)


ROOT = Path(__file__).resolve().parents[1]


def navigation_radio(app):
    return next(radio for radio in app.radio if radio.label == "Navigate")


def navigate_to(app, page):
    workspace_by_page = {
        "Start assessment": "Assessment",
        "Advanced field processor": "Assessment",
        "Overview": "Model science",
        "Mechanistic investigation": "Model science",
        "Polymer atlas": "Model science",
        "Polymer selection": "Model science",
        "Validation lab": "Model science",
        "Passive dosing": "Experiment design",
        "CompTox fish": "Evidence",
        "Evidence & methods": "Evidence",
    }
    workspace = next(selectbox for selectbox in app.selectbox if selectbox.label == "Workspace")
    if workspace.value != workspace_by_page[page]:
        workspace.set_value(workspace_by_page[page]).run()
    navigation_radio(app).set_value(page).run()
    return app


def test_start_assessment_is_the_default_page():
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    assert navigation_radio(app).value == "Start assessment"
    assert any("Measure on plastic" in markdown.value for markdown in app.markdown)
    calculate = next(button for button in app.button if button.label == "Calculate single-chemical risk")
    calculate.click().run()
    assert not app.exception
    metric_labels = [metric.label for metric in app.metric]
    assert "Cplastic used" in metric_labels
    assert "Toxic unit" in metric_labels
    assert "Risk quotient" in metric_labels


@pytest.mark.parametrize(
    "page",
    [
        "Overview",
        "Mechanistic investigation",
        "Advanced field processor",
        "Polymer atlas",
        "Polymer selection",
        "Validation lab",
        "Passive dosing",
        "CompTox fish",
        "Evidence & methods",
    ],
)
def test_every_page_renders_without_exception(page):
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    navigate_to(app, page)
    assert not app.exception


def test_single_chemical_renders_integrated_comptox_evidence():
    identity = CompToxIdentity(
        query="benzene",
        dtxsid="DTXSID3039242",
        preferred_name="Benzene",
        casrn="71-43-2",
        smiles="C1=CC=CC=C1",
        molecular_weight=78.114,
        raw={},
    )
    fish = FishLC50Evidence(
        endpoint="96 Hour Fathead Minnow LC50",
        model_name="TEST_FHM_LC50",
        source_name="TEST5.1.3",
        experimental_mol_l=0.0003589219346450053,
        experimental_neglog_mol_l=3.445,
        experimental_mg_l=28.039,
        predicted_mol_l=0.0005255205674303918,
        predicted_neglog_mol_l=3.279,
        predicted_mg_l=41.054,
        applicability_conclusion="Inside",
        applicability_reasoning="Compound is inside TEST applicability domains",
        raw={},
    )
    bundle = CompToxEvidenceBundle(
        identity=identity,
        log_kow=LogKowEvidence(2.13, 4, 2.13, 2.15, 2.0855, 2, 2.13, "experimental median"),
        fish_lc50=fish,
    )
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    app.session_state["comptox_evidence"] = bundle
    app.session_state["comptox_identity"] = identity
    app.session_state["single_partition_input"] = "CompTox logKow screening"
    app.run()
    unified_metric_labels = [metric.label for metric in app.metric]
    assert "Molecular weight" in unified_metric_labels
    assert "Experimental fish LC50 (96 h)" in unified_metric_labels
    experimental_metric = next(
        metric for metric in app.metric
        if metric.label == "Experimental fish LC50 (96 h)"
    )
    assert "mmol/L" in str(experimental_metric.value)
    navigate_to(app, "Mechanistic investigation")
    assert not app.exception
    metric_labels = [metric.label for metric in app.metric]
    assert "ECOTOX-derived experimental 96 h LC50" in metric_labels
    assert "Chemical-specific difference" in metric_labels
