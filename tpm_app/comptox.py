"""Read-only EPA CompTox identity, property, and acute-fish evidence client."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import http.client
import json
import math
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


DEFAULT_BASE_URL = "https://comptox.epa.gov/ctx-api/chemical"
WEBTEST_BASE_URL = "https://comptox.epa.gov/dashboard/web-test"
ECOTOX_URL = "https://cfpub.epa.gov/ecotox/"
EPA_FATHEAD_MINNOW_LIST_URL = "https://comptox.epa.gov/dashboard/chemical_lists/EPAFHM"


class CompToxError(RuntimeError):
    """Readable failure from the optional EPA connection."""


@dataclass(frozen=True)
class CompToxIdentity:
    query: str
    dtxsid: str
    preferred_name: str
    casrn: str | None
    smiles: str | None
    molecular_weight: float | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class LogKowEvidence:
    """CompTox logKow evidence summarized without mixing measured and predicted values."""

    experimental_median: float | None
    experimental_count: int
    experimental_min: float | None
    experimental_max: float | None
    predicted_median: float | None
    predicted_count: int
    selected_value: float | None
    selected_basis: str


@dataclass(frozen=True)
class FishLC50Evidence:
    """EPA TEST 96-hour fathead-minnow LC50 evidence in explicit molar units."""

    endpoint: str
    model_name: str
    source_name: str
    experimental_mol_l: float | None
    experimental_neglog_mol_l: float | None
    experimental_mg_l: float | None
    predicted_mol_l: float | None
    predicted_neglog_mol_l: float | None
    predicted_mg_l: float | None
    applicability_conclusion: str | None
    applicability_reasoning: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class CompToxEvidenceBundle:
    identity: CompToxIdentity
    log_kow: LogKowEvidence
    fish_lc50: FishLC50Evidence | None


@dataclass(frozen=True)
class WebTestPrediction:
    """Fish-only consensus result returned by EPA WebTEST."""

    endpoint: str
    predicted_neglog_mol_l: float
    predicted_mg_l: float
    report_url: str
    experimental_neglog_mol_l: float | None = None
    experimental_mg_l: float | None = None
    dtxsid: str | None = None


class _TableTextParser(HTMLParser):
    """Compatibility parser for archived HTML WebTEST responses."""

    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs):
        if tag.casefold() == "tr":
            self._row = []
        elif tag.casefold() in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str):
        normalized = tag.casefold()
        if normalized in {"td", "th"} and self._cell is not None and self._row is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif normalized == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None


def _last_float(cells: list[str]) -> float | None:
    for cell in reversed(cells):
        try:
            return float(cell.replace(",", ""))
        except (TypeError, ValueError):
            continue
    return None


def _first(row: dict[str, Any], *keys: str):
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _float_or_none(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _int_or_zero(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("data", "content", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
        return [payload]
    return []


def _to_neglog(value_mol_l: float | None) -> float | None:
    if value_mol_l is None or value_mol_l <= 0:
        return None
    return -math.log10(value_mol_l)


def _to_mg_l(value_mol_l: float | None, molecular_weight: float | None) -> float | None:
    if value_mol_l is None or molecular_weight is None:
        return None
    return value_mol_l * molecular_weight * 1000.0


class CompToxClient:
    """Minimal, read-only client for identity and property evidence retrieval."""

    def __init__(self, api_key: str, base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0):
        self.api_key = str(api_key).strip()
        if not self.api_key:
            raise CompToxError("A CompTox API key is not configured.")
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)

    def _get_json(self, path: str) -> Any:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            headers={"Accept": "application/json", "x-api-key": self.api_key},
            method="GET",
        )
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                if error.code in {429, 502, 503, 504} and attempt < 2:
                    time.sleep(2**attempt)
                    continue
                if error.code in {401, 403}:
                    raise CompToxError("CompTox rejected the API key.") from error
                if error.code in {400, 404}:
                    raise CompToxError("No matching CompTox evidence was found.") from error
                raise CompToxError(f"CompTox returned HTTP {error.code}.") from error
            except (urllib.error.URLError, http.client.HTTPException, OSError) as error:
                if attempt < 2:
                    time.sleep(2**attempt)
                    continue
                raise CompToxError("The EPA CompTox service could not be reached.") from error
            except json.JSONDecodeError as error:
                raise CompToxError("CompTox returned an unreadable response.") from error
        raise CompToxError("The EPA CompTox service could not be reached.")

    def exact_identity(self, identifier: str) -> CompToxIdentity:
        query = str(identifier).strip()
        if not query:
            raise CompToxError("Enter a chemical name, CAS RN, DTXSID, or InChIKey.")
        payload = self._get_json(f"/search/equal/{urllib.parse.quote(query, safe='')}")
        matches = _rows(payload)
        if not matches:
            raise CompToxError("No exact CompTox match was found.")
        normalized = query.casefold()
        exact = [
            row for row in matches
            if normalized in {
                str(_first(row, "dtxsid") or "").casefold(),
                str(_first(row, "casrn", "casRn") or "").casefold(),
                str(_first(row, "preferredName", "preferred_name") or "").casefold(),
            }
        ]
        if len(matches) == 1:
            row = matches[0]
        elif len(exact) == 1:
            row = exact[0]
        else:
            choices = ", ".join(
                f"{_first(item, 'preferredName', 'preferred_name')} ({_first(item, 'dtxsid')})"
                for item in matches[:5]
            )
            raise CompToxError(f"Multiple substances matched; use a DTXSID. Candidates: {choices}")

        dtxsid = str(_first(row, "dtxsid") or "")
        detail = row
        needs_detail = not _first(row, "averageMass", "molWeight", "molecularWeight") or not _first(
            row, "smiles", "smilesCanonical", "canonicalSmiles"
        )
        if dtxsid and needs_detail:
            try:
                detail_rows = _rows(
                    self._get_json(
                        f"/detail/search/by-dtxsid/{urllib.parse.quote(dtxsid, safe='')}?projection=chemicaldetailall"
                    )
                )
                if detail_rows:
                    detail = {**row, **detail_rows[0]}
            except CompToxError:
                detail = row
        return CompToxIdentity(
            query=query,
            dtxsid=dtxsid,
            preferred_name=str(_first(detail, "preferredName", "preferred_name") or query),
            casrn=_first(detail, "casrn", "casRn"),
            smiles=_first(detail, "smiles", "smilesCanonical", "canonicalSmiles"),
            molecular_weight=_float_or_none(
                _first(detail, "averageMass", "molWeight", "molecularWeight", "monoisotopicMass")
            ),
            raw=detail,
        )

    def property_summary(self, dtxsid: str) -> list[dict[str, Any]]:
        payload = self._get_json(
            f"/property/summary/search/by-dtxsid/{urllib.parse.quote(str(dtxsid), safe='')}"
        )
        return _rows(payload)

    def predicted_properties(self, dtxsid: str) -> list[dict[str, Any]]:
        payload = self._get_json(
            f"/property/predicted/search/by-dtxsid/{urllib.parse.quote(str(dtxsid), safe='')}"
        )
        return _rows(payload)

    def log_kow_evidence(
        self, dtxsid: str, predicted_rows: list[dict[str, Any]] | None = None
    ) -> LogKowEvidence:
        summary_rows: list[dict[str, Any]] = []
        try:
            summary_rows = self.property_summary(dtxsid)
        except CompToxError:
            pass
        row = next(
            (
                item for item in summary_rows
                if "logkow" in str(_first(item, "propertyName", "propName", "name") or "")
                .replace(" ", "").replace("_", "").casefold()
                or "logp" == str(_first(item, "propertyName", "propName", "name") or "").casefold()
            ),
            {},
        )
        experimental = _float_or_none(
            _first(row, "experimentalMedian", "experimental_median", "expMedian")
        )
        predicted = _float_or_none(_first(row, "predictedMedian", "predicted_median", "predMedian"))
        experimental_count = _int_or_zero(
            _first(row, "experimentalCount", "experimental_count", "expCount")
        )
        predicted_count = _int_or_zero(_first(row, "predictedCount", "predicted_count", "predCount"))

        candidates = predicted_rows if predicted_rows is not None else self.predicted_properties(dtxsid)
        logp_rows = [
            item for item in candidates
            if any(
                token in str(_first(item, "propName", "propertyName", "modelName") or "")
                .replace(" ", "").replace("_", "").casefold()
                for token in ("logkow", "logp")
            )
        ]
        if experimental is None:
            experimental_values = [
                value for value in (
                    _float_or_none(_first(item, "propValueExperimental", "experimentalValue"))
                    for item in logp_rows
                ) if value is not None
            ]
            if experimental_values:
                experimental = sorted(experimental_values)[len(experimental_values) // 2]
                experimental_count = len(experimental_values)
        if predicted is None:
            predicted_values = [
                value for value in (
                    _float_or_none(_first(item, "propValue", "predictedValue")) for item in logp_rows
                ) if value is not None
            ]
            if predicted_values:
                predicted = sum(predicted_values) / len(predicted_values)
                predicted_count = len(predicted_values)

        selected = experimental if experimental is not None else predicted
        basis = "experimental median" if experimental is not None else (
            "predicted median" if predicted is not None else "unavailable"
        )
        return LogKowEvidence(
            experimental_median=experimental,
            experimental_count=experimental_count,
            experimental_min=_float_or_none(
                _first(row, "experimentalMin", "experimental_min", "expMin")
            ),
            experimental_max=_float_or_none(
                _first(row, "experimentalMax", "experimental_max", "expMax")
            ),
            predicted_median=predicted,
            predicted_count=predicted_count,
            selected_value=selected,
            selected_basis=basis,
        )

    @staticmethod
    def fish_lc50_evidence(
        predicted_rows: list[dict[str, Any]], molecular_weight: float | None
    ) -> FishLC50Evidence | None:
        candidates = [
            row for row in predicted_rows
            if "fatheadminnow" in str(_first(row, "propName", "propertyName") or "")
            .replace(" ", "").replace("-", "").casefold()
            and "lc50" in str(_first(row, "propName", "propertyName") or "").casefold()
        ]
        if not candidates:
            return None
        row = next(
            (item for item in candidates if str(_first(item, "modelName") or "").casefold() == "test_fhm_lc50"),
            candidates[0],
        )
        unit = str(_first(row, "propUnit", "unit") or "mol/L").casefold()
        experimental = _float_or_none(
            _first(row, "propValueExperimental", "experimentalValue", "experimental")
        )
        predicted = _float_or_none(_first(row, "propValue", "predictedValue", "prediction"))
        if "mg/l" in unit and molecular_weight:
            experimental = experimental / (molecular_weight * 1000.0) if experimental is not None else None
            predicted = predicted / (molecular_weight * 1000.0) if predicted is not None else None
        return FishLC50Evidence(
            endpoint=str(_first(row, "propName", "propertyName") or "96 Hour Fathead Minnow LC50"),
            model_name=str(_first(row, "modelName") or "TEST_FHM_LC50"),
            source_name=str(_first(row, "sourceName") or "EPA TEST"),
            experimental_mol_l=experimental,
            experimental_neglog_mol_l=_to_neglog(experimental),
            experimental_mg_l=_to_mg_l(experimental, molecular_weight),
            predicted_mol_l=predicted,
            predicted_neglog_mol_l=_to_neglog(predicted),
            predicted_mg_l=_to_mg_l(predicted, molecular_weight),
            applicability_conclusion=_first(row, "adConclusion", "applicabilityConclusion"),
            applicability_reasoning=_first(row, "adReasoning", "applicabilityReasoning"),
            raw=row,
        )

    def evidence_bundle(self, identifier: str) -> CompToxEvidenceBundle:
        identity = self.exact_identity(identifier)
        predicted_rows = self.predicted_properties(identity.dtxsid)
        return CompToxEvidenceBundle(
            identity=identity,
            log_kow=self.log_kow_evidence(identity.dtxsid, predicted_rows),
            fish_lc50=self.fish_lc50_evidence(predicted_rows, identity.molecular_weight),
        )


def webtest_report_url(smiles: str, endpoint: str = "LC50") -> str:
    """Build the current official WebTEST consensus JSON-service URL."""

    query = urllib.parse.urlencode({"smiles": str(smiles).strip(), "method": "consensus"})
    return f"{WEBTEST_BASE_URL}/{urllib.parse.quote(str(endpoint), safe='')}?{query}"


def parse_webtest_prediction(payload: str | dict[str, Any], report_url: str = "") -> WebTestPrediction:
    """Parse current JSON or archived HTML EPA WebTEST LC50 output."""

    if isinstance(payload, dict):
        neglog = _float_or_none(_first(payload, "predValMolarLog", "predictedNegLogMolL"))
        mg_l = _float_or_none(_first(payload, "predValMass", "predictedMgL"))
        if neglog is None or mg_l is None:
            raise CompToxError("EPA WebTEST returned no readable 96-hour fish LC50 prediction.")
        return WebTestPrediction(
            endpoint="Fathead minnow LC50 (96 h), consensus QSAR",
            predicted_neglog_mol_l=neglog,
            predicted_mg_l=mg_l,
            report_url=report_url,
            experimental_neglog_mol_l=_float_or_none(_first(payload, "expValMolarLog")),
            experimental_mg_l=_float_or_none(_first(payload, "expValMass")),
            dtxsid=_first(payload, "dtxsid", "DTXSID"),
        )

    text = str(payload)
    try:
        decoded = json.loads(text)
    except json.JSONDecodeError:
        decoded = None
    if isinstance(decoded, dict):
        return parse_webtest_prediction(decoded, report_url)

    parser = _TableTextParser()
    parser.feed(text)
    neglog = None
    mg_l = None
    for row in parser.rows:
        label = " ".join(row).casefold()
        if "fathead minnow" not in label or "96" not in label or "lc" not in label:
            continue
        value = _last_float(row)
        if value is None:
            continue
        if "log10" in label or "log 10" in label or "mol/l" in label:
            neglog = value
        elif "mg/l" in label:
            mg_l = value
    if neglog is None or mg_l is None:
        raise CompToxError("EPA WebTEST returned no readable 96-hour fish LC50 prediction.")
    return WebTestPrediction(
        endpoint="Fathead minnow LC50 (96 h), consensus QSAR",
        predicted_neglog_mol_l=neglog,
        predicted_mg_l=mg_l,
        report_url=report_url,
    )


def fetch_webtest_prediction(smiles: str, timeout: float = 45.0) -> WebTestPrediction:
    """Retrieve the current 96-hour fathead-minnow LC50 result from EPA WebTEST."""

    structure = str(smiles).strip()
    if not structure:
        raise CompToxError("A SMILES structure is required for the WebTEST prediction.")
    url = webtest_report_url(structure, endpoint="LC50")
    request = urllib.request.Request(url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=float(timeout)) as response:
            response_text = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, http.client.HTTPException, OSError) as error:
        raise CompToxError("EPA WebTEST could not be reached.") from error
    return parse_webtest_prediction(response_text, report_url=url)


def comptox_dashboard_url(dtxsid: str) -> str:
    return f"https://comptox.epa.gov/dashboard/chemical/details/{urllib.parse.quote(str(dtxsid))}"
