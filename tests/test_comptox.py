import pytest

from tpm_app.comptox import (
    CompToxClient,
    comptox_dashboard_url,
    parse_webtest_prediction,
    webtest_report_url,
)


class MockClient(CompToxClient):
    def _get_json(self, path):
        assert path.startswith("/search/equal/")
        return [
            {
                "dtxsid": "DTXSID7020182",
                "preferredName": "n-Hexane",
                "casrn": "110-54-3",
                "smiles": "CCCCCC",
                "molWeight": 86.175,
            }
        ]


def test_exact_identity_mapping():
    identity = MockClient("test-key").exact_identity("110-54-3")
    assert identity.dtxsid == "DTXSID7020182"
    assert identity.preferred_name == "n-Hexane"
    assert identity.smiles == "CCCCCC"
    assert identity.molecular_weight == 86.175


def test_external_urls_are_encoded_and_read_only():
    url = webtest_report_url("O=C(O)c1ccccc1")
    assert "/web-test/LC50?" in url
    assert "method=consensus" in url
    assert "O%3DC%28O%29" in url
    assert comptox_dashboard_url("DTXSID7020182").endswith("/DTXSID7020182")


def test_webtest_fish_prediction_parser_keeps_endpoint_and_units_separate():
    report = """
    <table>
      <tr><th>Endpoint</th><th>Experimental value</th><th>Predicted value</th></tr>
      <tr><td>Fathead minnow LC50 (96 hr) -Log10(mol/L)</td><td>N/A</td><td>5.53</td></tr>
      <tr><td>Fathead minnow LC50 (96 hr) mg/L</td><td>N/A</td><td>1.35</td></tr>
    </table>
    """
    parsed = parse_webtest_prediction(report, "https://example.test/report")
    assert parsed.predicted_neglog_mol_l == 5.53
    assert parsed.predicted_mg_l == 1.35
    assert "96 h" in parsed.endpoint


def test_current_webtest_json_parser_keeps_experimental_value_separate():
    parsed = parse_webtest_prediction(
        {
            "endpoint": "LC50",
            "predValMolarLog": "3.279",
            "predValMass": "41.054",
            "expValMolarLog": "3.445",
            "expValMass": "28.039",
            "dtxsid": "DTXSID3039242",
        },
        "https://example.test/web-test/LC50",
    )
    assert parsed.predicted_neglog_mol_l == 3.279
    assert parsed.experimental_neglog_mol_l == 3.445
    assert parsed.predicted_mg_l == 41.054
    assert parsed.experimental_mg_l == 28.039


def test_property_evidence_extracts_logkow_and_96_hour_fish_values():
    rows = [
        {
            "propName": "LogKow",
            "modelName": "OPERA_LogP",
            "propValueExperimental": 2.13,
            "propValue": 2.08,
        },
        {
            "propName": "96 Hour Fathead Minnow LC50",
            "modelName": "TEST_FHM_LC50",
            "sourceName": "TEST5.1.3",
            "propValueExperimental": 0.0003589219346450053,
            "propValue": 0.0005255205674303918,
            "propUnit": "mol/L",
            "adConclusion": "Inside",
        },
    ]
    fish = CompToxClient.fish_lc50_evidence(rows, 78.114)
    assert fish is not None
    assert fish.experimental_neglog_mol_l == pytest.approx(3.445, abs=0.001)
    assert fish.experimental_mg_l == pytest.approx(28.039, rel=1e-4)
    assert fish.applicability_conclusion == "Inside"
