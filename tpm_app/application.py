"""Streamlit interface for scientific exploration of the Target Plastic Model."""

from __future__ import annotations

import io
import math
import os
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from . import __version__
from .comptox import (
    CompToxClient,
    CompToxEvidenceBundle,
    CompToxError,
    EPA_FATHEAD_MINNOW_LIST_URL,
    comptox_dashboard_url,
    fetch_webtest_prediction,
    webtest_report_url,
)
from .core import (
    ScientificInputError,
    abraham_log_k,
    assess_applicability,
    critical_burden_from_observation,
    exposure_to_mmol_kg,
    individual_prediction_error,
    lfer_log_k,
    passive_dosing_series,
    plastic_phase_pnec,
    predict_lc50,
    prediction_metrics,
    substitute_censored_value,
    summarize_mixture,
    toxic_unit,
    water_concentration_to_plastic_mmol_kg,
)
from .data import (
    DATA_DIR,
    burden_record,
    critical_burdens,
    dataset_manifest,
    model_registry,
    other_plastics,
    phase_log_k_column,
    validation_records,
)


ROOT = Path(__file__).resolve().parents[1]
PAPER_URL = "https://doi.org/10.1021/acs.jcim.4c00574"
EPA_API_URL = "https://comptox.epa.gov/ctx-api/docs/"
ECOTOX_URL = "https://cfpub.epa.gov/ecotox/"
UFZ_LSER_URL = "https://www.ufz.de/lserd/"


def configure_page() -> None:
    st.set_page_config(
        page_title="Target Plastic Model Explorer",
        page_icon="🧪",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(
        """
        <style>
        :root {
            --ink:#132f31; --muted:#597071; --teal:#08776f; --teal-dark:#0e4142;
            --mint:#e8f5f1; --line:#d9e7e3; --amber:#d98a20; --paper:#ffffff;
        }
        html, body, [class*="css"] { font-family:Inter,"Segoe UI",Arial,sans-serif; }
        .stApp { background:linear-gradient(180deg,#f4faf8 0%,#ffffff 25%); color:var(--ink); }
        .block-container { max-width:1500px; padding-top:2rem; padding-bottom:3rem; }
        [data-testid="stSidebar"] { background:linear-gradient(180deg,#0e4142 0%,#102f31 100%); }
        [data-testid="stSidebar"] * { color: #f6fbfa; }
        [data-testid="stSidebar"] [data-baseweb="select"] > div { background:#e7f4ef; border-color:#c5ddd6; }
        [data-testid="stSidebar"] [data-baseweb="select"] * { color:var(--ink) !important; }
        [data-testid="stSidebar"] input[role="combobox"] { color:var(--ink) !important; }
        [data-testid="stSidebar"] input[role="combobox"] + button,
        [data-testid="stSidebar"] input[role="combobox"] + button * { color:var(--ink) !important; }
        [data-testid="stMetric"] { background:var(--paper); border:1px solid var(--line); padding:1rem;
                                  border-radius:12px; box-shadow:0 5px 18px rgba(16,47,49,.045); }
        [data-testid="stMetricLabel"] { color:var(--muted); }
        .hero { position:relative; overflow:hidden; padding:2rem 2.1rem; border-radius:20px; color:white;
                background:linear-gradient(120deg,#102f31 0%,#08776f 72%,#29a88d 100%);
                box-shadow:0 16px 38px rgba(15,52,53,.16); margin-bottom:1.15rem; }
        .hero:after { content:""; position:absolute; right:-95px; top:-135px; width:360px; height:360px;
                      border:58px solid rgba(255,255,255,.08); border-radius:50%; }
        .hero h1 { position:relative; z-index:1; margin:0; font-size:clamp(2rem,3vw,2.75rem);
                   line-height:1.08; letter-spacing:-.04em; max-width:900px; }
        .hero p { position:relative; z-index:1; margin:.75rem 0 0; max-width:900px;
                  color:#e3f3ee; font-size:1.05rem; line-height:1.55; }
        .eyebrow { font-size:.76rem; font-weight:700; letter-spacing:.13em; text-transform:uppercase; color:#bde5d8; }
        .evidence-card { background:#fff; border:1px solid var(--line); border-left:5px solid var(--teal);
                         padding:1rem 1.1rem; border-radius:10px; box-shadow:0 4px 18px rgba(15,52,53,.055); }
        .warning-card { background:#fff8eb; border-left:5px solid #ef9f32; padding:.85rem 1rem; border-radius:8px; }
        .pill { display:inline-block; padding:.2rem .55rem; margin-right:.3rem; border-radius:999px;
                background:#dff3ec; color:#145f58; font-size:.78rem; font-weight:650; }
        .formula { text-align:center; font-size:1.23rem; padding:1rem; border:1px solid #d5eae4;
                   border-radius:12px; background:#edf7f4; color:#163f3d; font-family:Georgia,serif; }
        .workflow { display:grid; grid-template-columns:repeat(4,1fr); gap:.7rem; margin:1rem 0 1.3rem; }
        .workflow-step { background:#fff; border:1px solid var(--line); border-radius:12px; padding:.85rem .9rem;
                         min-height:86px; box-shadow:0 4px 14px rgba(15,52,53,.04); }
        .workflow-number { display:inline-grid; place-items:center; width:25px; height:25px; border-radius:50%;
                           color:#fff; background:var(--teal); font-size:.78rem; font-weight:750; margin-right:.35rem; }
        .workflow-step b { font-size:.93rem; color:var(--ink); }
        .workflow-step span:last-child { display:block; margin-top:.35rem; color:var(--muted); font-size:.79rem; line-height:1.35; }
        .section-kicker { color:var(--teal); font-size:.75rem; font-weight:750; letter-spacing:.1em;
                          text-transform:uppercase; margin-top:.65rem; }
        .result-banner { padding:.85rem 1rem; border-radius:10px; font-weight:650; margin:.55rem 0 .9rem; }
        .result-low { background:#e9f6f1; color:#135c52; border:1px solid #cce8df; }
        .result-high { background:#fff2e0; color:#8a4d00; border:1px solid #f3d5a9; }
        .start-copy { padding:1.2rem .8rem 1.2rem 0; }
        .start-copy h1 { margin:.3rem 0 .8rem; color:var(--ink); font-size:clamp(2.25rem,4vw,3.6rem);
                         line-height:1.03; letter-spacing:-.055em; }
        .start-copy p { color:var(--muted); font-size:1.05rem; line-height:1.55; max-width:620px; }
        .start-formula { margin-top:1.1rem; padding:.85rem 1rem; border-left:4px solid var(--teal);
                         background:#edf7f4; color:#163f3d; font-family:Georgia,serif; font-size:1.12rem; }
        .concept-caption { color:var(--muted); font-size:.78rem; margin-top:-.35rem; }
        .assessment-rail { display:flex; align-items:center; gap:.45rem; flex-wrap:wrap;
                           padding:.7rem 0 1.15rem; border-bottom:1px solid var(--line); margin-bottom:1.25rem; }
        .assessment-rail span { color:var(--muted); font-size:.81rem; font-weight:650; }
        .assessment-rail i { color:#97aaa7; font-style:normal; }
        .basis-line { padding:.72rem .9rem; border:1px solid var(--line); background:#f7fbfa;
                      border-radius:9px; color:var(--ink); margin:.2rem 0 1rem; }
        .basis-line b { color:var(--teal-dark); }
        .step-label { margin-top:1.15rem; color:var(--teal); font-size:.76rem; font-weight:750;
                      letter-spacing:.08em; text-transform:uppercase; }
        .quiet-note { color:var(--muted); font-size:.86rem; line-height:1.45; }
        [data-testid="stImage"] img { border-radius:10px; }
        @media(max-width:900px) { .workflow { grid-template-columns:repeat(2,1fr); } }
        @media(max-width:560px) { .workflow { grid-template-columns:1fr; } }
        a { color:#08766f; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, subtitle: str, eyebrow: str) -> None:
    st.markdown(
        f'<div class="hero"><div class="eyebrow">{eyebrow}</div><h1>{title}</h1><p>{subtitle}</p></div>',
        unsafe_allow_html=True,
    )


def api_key() -> str:
    try:
        value = st.secrets.get("COMPTOX_API_KEY", "")
    except Exception:
        value = ""
    return str(value or os.getenv("COMPTOX_API_KEY", "")).strip()


def phase_options(validated_only: bool = False) -> list[str]:
    registry = model_registry()
    return [
        key for key, metadata in registry["phases"].items()
        if not validated_only or metadata["validated"]
    ]


def mode_label(mode: str) -> str:
    return model_registry()["modes"][mode]["label"]


def phase_label(phase: str) -> str:
    return model_registry()["phases"][phase]["label"]


def format_scientific(value: float, digits: int = 3) -> str:
    return f"{value:.{digits}g}"


def mol_l_to_mmol_l(value: float | None) -> float | None:
    """Convert a molar concentration to the dashboard's common mmol/L display unit."""

    return None if value is None else float(value) * 1000.0


def render_workflow_strip() -> None:
    st.markdown(
        """
        <div class="workflow">
          <div class="workflow-step"><span class="workflow-number">1</span><b>Set context</b>
            <span>Select toxic mode, validated plastic phase, and assessment factor.</span></div>
          <div class="workflow-step"><span class="workflow-number">2</span><b>Identify chemicals</b>
            <span>Use a known identity or retrieve an exact CompTox record.</span></div>
          <div class="workflow-step"><span class="workflow-number">3</span><b>Enter measurements</b>
            <span>Provide plastic/passive-sampler burdens or partition-supported water data.</span></div>
          <div class="workflow-step"><span class="workflow-number">4</span><b>Interpret risk</b>
            <span>Review Cplastic, TU, PNECplastic,eq, RQ, and mixture contributions.</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def exposure_threshold_figure(
    *, exposure_mmol_kg: float, pnec_mmol_kg: float, critical_burden_mmol_kg: float
) -> go.Figure:
    """Return a compact log-scale comparison of exposure and TPM thresholds."""

    rows = pd.DataFrame(
        {
            "quantity": ["Measured / plastic-equivalent", "PNECplastic,eq", "Median critical burden"],
            "value": [exposure_mmol_kg, pnec_mmol_kg, critical_burden_mmol_kg],
            "role": ["Exposure", "Screening threshold", "Acute critical burden"],
        }
    )
    positive = rows[rows["value"] > 0].copy()
    figure = px.scatter(
        positive,
        x="value",
        y="quantity",
        color="role",
        size=[18] * len(positive),
        log_x=True,
        color_discrete_map={
            "Exposure": "#08776f",
            "Screening threshold": "#d98a20",
            "Acute critical burden": "#6a5aa8",
        },
        labels={"value": "Concentration or burden (mmol/kg plastic)", "quantity": ""},
        title="Exposure relative to plastic-phase screening thresholds",
    )
    figure.update_traces(marker=dict(line=dict(width=1.5, color="white")))
    figure.update_layout(
        height=310,
        margin=dict(l=10, r=20, t=55, b=10),
        plot_bgcolor="white",
        legend_title_text="",
        legend_orientation="h",
        legend_y=-0.28,
        xaxis=dict(showgrid=True, gridcolor="#e6efec"),
        yaxis=dict(categoryorder="array", categoryarray=rows["quantity"].tolist()[::-1]),
    )
    return figure


def risk_position_figure(risk_quotient: float, title: str) -> go.Figure:
    """Show RQ on a log scale with the RQ=1 decision line."""

    displayed = max(float(risk_quotient), 1e-8)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=[displayed],
            y=["Assessment"],
            mode="markers+text",
            text=[f"RQ {risk_quotient:.3g}"],
            textposition="top center",
            marker=dict(
                size=19,
                color="#d98a20" if risk_quotient >= 1 else "#08776f",
                line=dict(color="white", width=1.5),
            ),
            hovertemplate="Risk quotient: %{x:.4g}<extra></extra>",
        )
    )
    figure.add_vline(
        x=1,
        line_width=2,
        line_dash="dash",
        line_color="#b65b42",
        annotation_text="RQ = 1",
    )
    figure.update_xaxes(
        type="log", title="Risk quotient (log scale)", showgrid=True, gridcolor="#e6efec"
    )
    figure.update_yaxes(title="", showticklabels=False)
    figure.update_layout(
        height=260,
        margin=dict(l=10, r=25, t=55, b=10),
        title=title,
        plot_bgcolor="white",
        showlegend=False,
    )
    return figure


def development_log_k_range(mode: str, phase: str) -> tuple[float, float]:
    """Return the observed log-K range in the relevant evaluation cohort."""

    records = validation_records()
    column = phase_log_k_column(phase)
    values = records[
        (records["toxic_mode"] == mode) & (records["set_role"] == "evaluation")
    ][column].dropna()
    if values.empty:
        values = records[records["toxic_mode"] == mode][column].dropna()
    return float(values.min()), float(values.max())


def render_applicability(
    *,
    mode: str,
    phase: str,
    partition_source: str,
    log_k: float,
    ionization_status: str,
    mode_confidence: str,
    method_documented: bool,
) -> str:
    lower, upper = development_log_k_range(mode, phase)
    assessment = assess_applicability(
        mode=mode,
        phase_validated=model_registry()["phases"][phase]["validated"],
        partition_source=partition_source,
        log_k_phase_water=log_k,
        domain_min=lower,
        domain_max=upper,
        ionization_status=ionization_status,
        mode_confidence=mode_confidence,
        method_documented=method_documented,
    )
    colors = {
        "inside": ("#e7f4ef", "#0b6e69"),
        "caution": ("#fff8eb", "#b76a00"),
        "outside": ("#fff0ee", "#a53b2a"),
    }
    background, border = colors[assessment.status]
    st.markdown(
        f'<div style="background:{background};border-left:5px solid {border};padding:.85rem 1rem;border-radius:8px">'
        f'<b>Applicability: {assessment.label}</b><br>'
        f'Development-cohort log K range for {phase_label(phase)}: {lower:.3f} to {upper:.3f}.'
        f'</div>',
        unsafe_allow_html=True,
    )
    for reason in assessment.reasons:
        st.markdown(f"- {reason}")
    for warning in assessment.warnings:
        st.markdown(f"- Caution: {warning}")
    st.caption(
        "This rule-based screen checks the published model boundary and input provenance; "
        "it is not a statistical confidence interval."
    )
    return assessment.status


def partition_provenance_frame(phases: list[str] | None = None) -> pd.DataFrame:
    registry = model_registry()
    selected = phases or phase_options(True)
    rows = []
    for phase in selected:
        item = registry["partition_model_provenance"][phase]
        rows.append(
            {
                "phase": phase_label(phase),
                "method": item["method"],
                "source": item["source"],
                "temperature": item["temperature"],
                "n": item["training_n"],
                "R2": item["r_squared"],
                "SE": item["standard_error"],
                "limitations": item["notes"],
            }
        )
    return pd.DataFrame(rows)


def environmental_example_frame(phase: str, measurement_basis: str) -> pd.DataFrame:
    """Return editable environmental-scale examples with explicit provenance."""

    examples = [
        ("Naphthalene", "91-20-3", 128.1702, 10.0, 1.0),
        ("Phenanthrene", "85-01-8", 178.2288, 20.0, 0.5),
        ("Pyrene", "129-00-0", 202.2502, 5.0, 0.1),
    ]
    records = validation_records()
    rows = []
    for name, casrn, molecular_weight, plastic_value, water_value in examples:
        match = records[
            (records["name"].str.casefold() == name.casefold())
            & (records["toxic_mode"] == "baseline")
        ]
        published_log_k = (
            float(match.iloc[0][phase_log_k_column(phase)]) if not match.empty else math.nan
        )
        if measurement_basis == "Measured on plastic/passive sampler":
            concentration = plastic_value
            unit = "ng/g"
            source = "Editable environmental-scale plastic example"
        else:
            concentration = water_value
            unit = "ng/L"
            source = "Editable environmental-scale water example"
        rows.append({
            "sample_id": "Example-1",
            "chemical": name,
            "casrn": casrn,
            "molecular_weight_g_mol": molecular_weight,
            "concentration": concentration,
            "unit": unit,
            "log_k_phase_water": published_log_k,
            "partition_source": "TPM supporting record" if pd.notna(published_log_k) else "",
            "mode_confidence": "Established",
            "example_source": source,
        })
    return pd.DataFrame(rows)


def _legacy_direct_assessment_page() -> None:
    """Unified first-step workflow for single chemicals and compatible mixtures."""

    hero(
        "From measured plastic burden to ecological risk",
        "A guided Target Plastic Model workflow for one chemical or a compatible mixture. Start with the analytical measurement, calculate toxic units directly, then open EPA evidence only when deeper interpretation is needed.",
        "Target Plastic Model · primary assessment",
    )
    render_workflow_strip()
    st.markdown(
        """
        <div class="evidence-card"><b>Direct TPM pathway</b><br>
        If the analytical result is a concentration on the plastic or passive-sampler phase, no chemical-specific LC50 and no
        K<sub>plastic-water</sub> are needed: normalize the measurement to mmol/kg plastic and divide by the median critical
        plastic burden for the selected phase and toxic mode.</div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Scientific basis and equations", expanded=False):
        st.markdown(
            '<div class="formula">TU<sub>i</sub> = C<sub>plastic,i</sub> / median C<sub>plastic,mode,phase</sub><sup>crit</sup> '
            '&nbsp;&nbsp; | &nbsp;&nbsp; TU<sub>mix</sub> = &Sigma;TU<sub>i</sub> '
            '&nbsp;&nbsp; | &nbsp;&nbsp; PNEC<sub>plastic,eq</sub> = C<sup>crit</sup><sub>plastic</sub> / AF '
            '&nbsp;&nbsp; | &nbsp;&nbsp; RQ = TU &times; AF</div>',
            unsafe_allow_html=True,
        )
        concept_art = ROOT / "assets" / "source_figures" / "TOC-Art.gif"
        if concept_art.exists():
            st.image(
                str(concept_art),
                caption="Paper concept graphic: translation from target lipid to target plastic modeling.",
                width="stretch",
            )

    st.markdown('<div class="section-kicker">Step 1 · Assessment context</div>', unsafe_allow_html=True)
    st.markdown("### Define the common model basis")
    controls = st.columns(3)
    mode = controls[0].selectbox(
        "Toxic mode",
        ["baseline", "less_inert"],
        format_func=mode_label,
        key="unified_mode",
        help="Mode assignment is the decisive expert input. Mixture concentration addition is enabled only for compatible baseline toxicants.",
    )
    phase = controls[1].selectbox(
        "Validated plastic phase",
        phase_options(True),
        format_func=phase_label,
        key="unified_phase",
    )
    assessment_basis = controls[2].selectbox(
        "Assessment-factor basis",
        ["Freshwater - AF 1,000", "Marine - AF 10,000", "Custom"],
        key="unified_assessment_basis",
    )
    if assessment_basis == "Freshwater - AF 1,000":
        assessment_factor = 1000.0
    elif assessment_basis == "Marine - AF 10,000":
        assessment_factor = 10000.0
    else:
        assessment_factor = controls[2].number_input(
            "Custom AF", min_value=0.01, value=1000.0, key="unified_custom_af"
        )
    burden = burden_record(mode, phase)
    critical_burden = float(burden["critical_burden_mmol_kg"])
    pnec = plastic_phase_pnec(critical_burden, assessment_factor)
    with st.container(border=True):
        endpoint_cols = st.columns(3)
        endpoint_cols[0].metric("Median critical plastic burden", f"{critical_burden:.5g} mmol/kg")
        endpoint_cols[1].metric("PNECplastic,eq", f"{pnec:.5g} mmol/kg")
        endpoint_cols[2].metric("Assessment factor", f"{assessment_factor:,.0f}")
        st.caption(
            "These phase- and mode-specific values are fixed for the current assessment. "
            "PNECplastic,eq is the screening threshold used to derive RQ; it is not a water-column PNEC."
        )

    st.markdown('<div class="section-kicker">Steps 2–4 · Assessment workflow</div>', unsafe_allow_html=True)
    single_tab, mixture_tab = st.tabs(["Single chemical", "Mixture"])

    with single_tab:
        st.markdown("### 2. Identify the chemical")
        st.caption(
            "Search CompTox to populate identity and molecular weight, or type the chemical information manually below. "
            "EPA fish evidence is shown in mmol/L and remains optional for the direct TPM calculation."
        )
        bundle = comptox_lookup_panel(inline=True)
        if bundle:
            current_id = st.session_state.get("unified_loaded_dtxsid")
            if current_id != bundle.identity.dtxsid:
                st.session_state["unified_single_name"] = bundle.identity.preferred_name
                if bundle.identity.molecular_weight is not None:
                    st.session_state["unified_single_mw"] = float(bundle.identity.molecular_weight)
                st.session_state["unified_loaded_dtxsid"] = bundle.identity.dtxsid

        st.markdown("### 3. Enter the measured concentration")
        measurement_basis = st.radio(
            "What did the laboratory measure?",
            ["Measured on plastic/passive sampler", "Measured in the water column"],
            horizontal=True,
            key="unified_single_basis",
        )
        if measurement_basis == "Measured on plastic/passive sampler":
            st.success(
                "Direct critical-burden pathway selected: LC50 and Kplastic-water are not used."
            )
        else:
            st.warning(
                "A water-column result cannot be divided directly by a plastic critical burden. "
                "The dashboard must first calculate an equilibrium plastic-equivalent concentration using Kplastic-water."
            )

        identity = bundle.identity if bundle else None
        if "unified_single_name" not in st.session_state:
            st.session_state["unified_single_name"] = (
                identity.preferred_name if identity else "Naphthalene"
            )
        if "unified_single_mw" not in st.session_state:
            st.session_state["unified_single_mw"] = (
                float(identity.molecular_weight)
                if identity and identity.molecular_weight else 128.1702
            )
        entry = st.columns([1.2, 1, 1, 1])
        chemical_name = entry[0].text_input(
            "Chemical",
            key="unified_single_name",
        )
        molecular_weight = entry[1].number_input(
            "Molecular weight (g/mol)",
            min_value=0.0,
            format="%.4f",
            key="unified_single_mw",
            help="Used only for mass-to-molar conversion.",
        )
        if measurement_basis == "Measured on plastic/passive sampler":
            concentration = entry[2].number_input(
                "Measured concentration", min_value=0.0, value=10.0,
                format="%.6g", key="unified_single_plastic_concentration"
            )
            unit = entry[3].selectbox(
                "Plastic unit",
                ["ng/g", "ug/g", "mg/g", "ng/kg", "ug/kg", "mg/kg", "mmol/kg", "mol/kg"],
                key="unified_single_plastic_unit",
            )
            log_k = None
            try:
                plastic_exposure = exposure_to_mmol_kg(concentration, unit, molecular_weight)
            except ScientificInputError as error:
                st.error(str(error))
                plastic_exposure = None
        else:
            concentration = entry[2].number_input(
                "Water concentration", min_value=0.0, value=1.0,
                format="%.6g", key="unified_single_water_concentration"
            )
            unit = entry[3].selectbox(
                "Water unit", ["ng/L", "ug/L", "mg/L", "mmol/L", "mol/L"],
                key="unified_single_water_unit",
            )
            partition_options = ["Enter measured log K"]
            if bundle and bundle.log_kow.selected_value is not None:
                partition_options.insert(0, "Estimate from CompTox logKow")
            partition_method = st.selectbox(
                "Water-to-plastic partition input",
                partition_options,
                key="unified_single_water_partition_method",
            )
            if partition_method == "Estimate from CompTox logKow":
                lfer = model_registry()["log_kow_lfer"][phase]
                log_k = lfer_log_k(
                    float(bundle.log_kow.selected_value), lfer["intercept"], lfer["slope"]
                )
                st.info(
                    f"Estimated log K{phase_label(phase)}-water = {log_k:.3f} using {lfer['label']}. "
                    "This is a partition-dependent secondary route."
                )
            else:
                log_k = st.number_input(
                    f"Measured log K{phase_label(phase)}-water",
                    value=3.0,
                    step=0.1,
                    key="unified_single_water_log_k",
                )
            try:
                plastic_exposure = water_concentration_to_plastic_mmol_kg(
                    concentration, unit, molecular_weight, log_k
                )
            except ScientificInputError as error:
                st.error(str(error))
                plastic_exposure = None

        mode_confidence = st.selectbox(
            "Toxic-mode confidence",
            ["Established", "Provisional", "Unknown"],
            key="unified_single_mode_confidence",
        )
        if plastic_exposure is not None:
            component_tu = toxic_unit(plastic_exposure, critical_burden)
            component_rq = component_tu * assessment_factor
            st.markdown("### 4. Review the assessment")
            risk_class = "result-high" if component_rq >= 1 else "result-low"
            risk_message = (
                "RQ ≥ 1: the plastic-equivalent concentration exceeds the selected screening threshold."
                if component_rq >= 1
                else "RQ < 1: the plastic-equivalent concentration is below the selected screening threshold."
            )
            st.markdown(
                f'<div class="result-banner {risk_class}">{risk_message}</div>',
                unsafe_allow_html=True,
            )
            result_cols = st.columns(4)
            result_cols[0].metric("Cplastic used", f"{plastic_exposure:.4g} mmol/kg")
            result_cols[1].metric("TU (single chemical)", f"{component_tu:.4g}")
            result_cols[2].metric("PNECplastic,eq", f"{pnec:.4g} mmol/kg")
            result_cols[3].metric("RQ", f"{component_rq:.4g}")
            chart_cols = st.columns([1.45, 1])
            with chart_cols[0]:
                st.plotly_chart(
                    exposure_threshold_figure(
                        exposure_mmol_kg=plastic_exposure,
                        pnec_mmol_kg=pnec,
                        critical_burden_mmol_kg=critical_burden,
                    ),
                    width="stretch",
                )
            with chart_cols[1]:
                st.plotly_chart(
                    risk_position_figure(component_rq, "Risk position"),
                    width="stretch",
                )
            if mode_confidence != "Established":
                st.warning("Interpretation is provisional until the selected toxic-mode assignment is established.")
            single_result = pd.DataFrame([{
                "chemical": chemical_name,
                "casrn": identity.casrn if identity else "",
                "dtxsid": identity.dtxsid if identity else "",
                "toxic_mode": mode,
                "plastic_phase": phase,
                "measurement_basis": measurement_basis,
                "reported_concentration": concentration,
                "reported_unit": unit,
                "molecular_weight_g_mol": molecular_weight,
                "log_k_phase_water": log_k,
                "plastic_equivalent_mmol_kg": plastic_exposure,
                "median_critical_burden_mmol_kg": critical_burden,
                "toxic_unit": component_tu,
                "PNECplastic_eq_mmol_kg": pnec,
                "assessment_factor": assessment_factor,
                "risk_quotient": component_rq,
                "mode_confidence": mode_confidence,
            }])
            with st.expander("Calculation audit", expanded=False):
                audit = pd.DataFrame(
                    [
                        {"stage": "Analytical input", "value": concentration, "unit": unit},
                        {"stage": "Cplastic used", "value": plastic_exposure, "unit": "mmol/kg plastic"},
                        {"stage": "Median critical burden", "value": critical_burden, "unit": "mmol/kg plastic"},
                        {"stage": "Toxic unit", "value": component_tu, "unit": "dimensionless"},
                        {"stage": "Assessment factor", "value": assessment_factor, "unit": "dimensionless"},
                        {"stage": "Risk quotient", "value": component_rq, "unit": "dimensionless"},
                    ]
                )
                st.dataframe(audit, width="stretch", hide_index=True)
                st.caption(
                    "Direct plastic measurements use Cplastic / median Ccrit. Water measurements first use the declared "
                    "Kplastic-water to calculate a plastic-equivalent burden."
                )
            action_cols = st.columns([1, 1, 2])
            action_cols[0].download_button(
                "Download single result",
                single_result.to_csv(index=False),
                "tpm_single_direct_result.csv",
                "text/csv",
            )
            if action_cols[1].button(
                "Add to mixture",
                disabled=mode != "baseline" or mode_confidence != "Established",
                key="unified_add_single_to_mixture",
            ):
                basket = list(st.session_state.get("external_mixture_basket", []))
                basket.append({
                    "sample_id": "User-mixture-1",
                    "chemical": chemical_name,
                    "casrn": identity.casrn if identity else "",
                    "dtxsid": identity.dtxsid if identity else "",
                    "phase": phase,
                    "toxic_mode": mode,
                    "molecular_weight_g_mol": molecular_weight,
                    "reported_concentration": concentration,
                    "reported_unit": unit,
                    "exposure_mmol_kg": plastic_exposure,
                    "median_critical_burden_mmol_kg": critical_burden,
                    "experimental_critical_burden_mmol_kg": None,
                    "partition_log_k": log_k,
                    "lc50_evidence": "Not required for direct TPM result",
                })
                st.session_state["external_mixture_basket"] = basket
                st.success(f"Added {chemical_name} to the mixture basket.")
            action_cols[2].caption(
                "Mixture addition is enabled only for established baseline-mode assignments."
            )

    with mixture_tab:
        st.markdown("### 2. Define a compatible mixture")
        st.caption(
            "Use the editable example as a template or upload your own table. Concentration addition is restricted "
            "to chemicals sharing the selected plastic phase and a compatible toxic mode."
        )
        measurement_basis = st.radio(
            "Mixture measurement basis",
            ["Measured on plastic/passive sampler", "Measured in the water column"],
            horizontal=True,
            key="unified_mixture_basis",
        )
        if measurement_basis == "Measured on plastic/passive sampler":
            st.success(
                "Primary direct pathway: each measured plastic burden is divided by the same selected phase/mode median critical burden. No LC50 or Kplastic-water is used."
            )
        else:
            st.warning(
                "Secondary water-input pathway: every row needs a chemical-specific Kplastic-water before a plastic-equivalent burden and TU can be calculated."
            )
        with st.expander("About the example concentrations", expanded=False):
            if measurement_basis == "Measured on plastic/passive sampler":
                st.caption(
                    "The initial 5-20 ng/g PAH values are editable environmental-scale examples, not universal typical concentrations. "
                    "Field microplastic-associated PAHs vary strongly by site and polymer."
                )
                st.link_button(
                    "Field context for microplastic-associated PAHs",
                    "https://www.sciencedirect.com/science/article/pii/S0043135425013879",
                )
            else:
                st.caption(
                    "The initial 0.1-1 ng/L PAH values are editable order-of-magnitude examples, not site-specific defaults."
                )
                st.link_button(
                    "Field context for dissolved PAHs",
                    "https://hero.epa.gov/reference/2173956/",
                )
        if mode != "baseline":
            st.warning(
                "Component TUs can be inspected for the selected mode, but TUmix and mixture RQ are disabled because the paper's concentration-addition workflow is supported for compatible baseline toxicants."
            )

        template = environmental_example_frame(phase, measurement_basis)
        if mode != "baseline":
            template["mode_confidence"] = "Unknown"
        uploaded = st.file_uploader(
            "Upload your own mixture CSV (optional)",
            type=["csv"],
            key="unified_mixture_upload",
        )
        if uploaded is not None:
            try:
                template = pd.read_csv(uploaded)
            except Exception as error:
                st.error(f"The CSV could not be read: {error}")
        st.markdown("### 3. Enter or review the measured mixture")
        edited = st.data_editor(
            template,
            num_rows="dynamic",
            width="stretch",
            key="unified_mixture_editor",
            column_config={
                "molecular_weight_g_mol": st.column_config.NumberColumn(
                    "MW (g/mol)", min_value=0.0
                ),
                "concentration": st.column_config.NumberColumn(
                    "Measured concentration", min_value=0.0, format="%.6g"
                ),
                "unit": st.column_config.SelectboxColumn(
                    "Unit",
                    options=(
                        ["ng/g", "ug/g", "mg/g", "ng/kg", "ug/kg", "mg/kg", "mmol/kg", "mol/kg"]
                        if measurement_basis == "Measured on plastic/passive sampler"
                        else ["ng/L", "ug/L", "mg/L", "mmol/L", "mol/L"]
                    ),
                    required=True,
                ),
                "mode_confidence": st.column_config.SelectboxColumn(
                    "Mode confidence", options=["Established", "Provisional", "Unknown"], required=True
                ),
            },
        )
        if measurement_basis == "Measured on plastic/passive sampler":
            st.caption("The log K column is ignored in this direct pathway and retained only for file compatibility.")
        compatibility = st.checkbox(
            "I confirm that these rows use the selected common plastic phase and toxic mode and are scientifically compatible for concentration addition.",
            key="unified_mixture_compatibility",
        )
        required = {"sample_id", "chemical", "concentration", "unit", "mode_confidence"}
        missing = required - set(edited.columns)
        if missing:
            st.error(f"Missing required columns: {', '.join(sorted(missing))}")
        elif edited["sample_id"].dropna().astype(str).nunique() != 1:
            st.error(
                "The guided start page evaluates one mixture sample at a time. "
                "Use one sample ID here or open Advanced field processor for batch analysis."
            )
        else:
            output = edited.copy()
            exposures = []
            tus = []
            errors = []
            for index, row in output.iterrows():
                try:
                    molecular_weight = row.get("molecular_weight_g_mol", math.nan)
                    if measurement_basis == "Measured on plastic/passive sampler":
                        exposure = exposure_to_mmol_kg(
                            row["concentration"], row["unit"], molecular_weight
                        )
                    else:
                        exposure = water_concentration_to_plastic_mmol_kg(
                            row["concentration"], row["unit"], molecular_weight,
                            row.get("log_k_phase_water", math.nan),
                        )
                    exposures.append(exposure)
                    tus.append(toxic_unit(exposure, critical_burden))
                except ScientificInputError as error:
                    exposures.append(math.nan)
                    tus.append(math.nan)
                    errors.append(f"Row {index + 1}: {error}")
            output["plastic_equivalent_mmol_kg"] = exposures
            output["median_critical_burden_mmol_kg"] = critical_burden
            output["toxic_unit"] = tus
            output["PNECplastic_eq_mmol_kg"] = pnec
            output["rq_contribution"] = output["toxic_unit"] * assessment_factor
            if errors:
                st.error("\n".join(errors))
            else:
                st.markdown("### 4. Review component and mixture results")
                concise_columns = [
                    column for column in [
                        "sample_id", "chemical", "concentration", "unit",
                        "plastic_equivalent_mmol_kg", "toxic_unit", "rq_contribution"
                    ] if column in output.columns
                ]
                st.dataframe(output[concise_columns], width="stretch", hide_index=True)
                with st.expander("Full component calculation table", expanded=False):
                    st.dataframe(output, width="stretch", hide_index=True)
                if compatibility and mode == "baseline":
                    summaries = []
                    for sample_id, group in output.groupby("sample_id", dropna=False):
                        total_tu = float(group["toxic_unit"].sum())
                        summaries.append({
                            "sample_id": sample_id,
                            "components": len(group),
                            "total_plastic_equivalent_mmol_kg": group["plastic_equivalent_mmol_kg"].sum(),
                            "TU_mix": total_tu,
                            "PNECplastic_eq_mmol_kg": pnec,
                            "assessment_factor": assessment_factor,
                            "RQ_mix": total_tu * assessment_factor,
                        })
                    summary_frame = pd.DataFrame(summaries).sort_values("RQ_mix", ascending=False)
                    top = summary_frame.iloc[0]
                    risk_class = "result-high" if top["RQ_mix"] >= 1 else "result-low"
                    risk_message = (
                        "Mixture RQ ≥ 1: the summed toxic units exceed the selected screening threshold."
                        if top["RQ_mix"] >= 1
                        else "Mixture RQ < 1: the summed toxic units are below the selected screening threshold."
                    )
                    st.markdown(
                        f'<div class="result-banner {risk_class}">{risk_message}</div>',
                        unsafe_allow_html=True,
                    )
                    summary_cols = st.columns(4)
                    summary_cols[0].metric("Components", int(top["components"]))
                    summary_cols[1].metric("TUmix", f"{top['TU_mix']:.4g}")
                    summary_cols[2].metric("PNECplastic,eq", f"{pnec:.4g} mmol/kg")
                    summary_cols[3].metric("RQmix", f"{top['RQ_mix']:.4g}")
                    with st.expander("Sample-level mixture summary", expanded=False):
                        st.dataframe(summary_frame, width="stretch", hide_index=True)
                    figure = px.bar(
                        output.sort_values("toxic_unit"),
                        x="toxic_unit",
                        y="chemical",
                        orientation="h",
                        color="toxic_unit",
                        color_continuous_scale="Tealgrn",
                        title="Component contributions to TUmix",
                    )
                    figure.update_layout(
                        height=max(320, 40 * len(output)),
                        margin=dict(l=10, r=20, t=55, b=10),
                        plot_bgcolor="white",
                        coloraxis_showscale=False,
                        xaxis=dict(showgrid=True, gridcolor="#e6efec"),
                    )
                    visual_cols = st.columns([1.4, 1])
                    visual_cols[0].plotly_chart(figure, width="stretch")
                    visual_cols[1].plotly_chart(
                        risk_position_figure(float(top["RQ_mix"]), "Mixture risk position"),
                        width="stretch",
                    )
                    downloads = st.columns(2)
                    downloads[0].download_button(
                        "Download component results",
                        output.to_csv(index=False),
                        "tpm_unified_mixture_components.csv",
                        "text/csv",
                    )
                    downloads[1].download_button(
                        "Download mixture summary",
                        summary_frame.to_csv(index=False),
                        "tpm_unified_mixture_summary.csv",
                        "text/csv",
                    )
                elif not compatibility:
                    st.info("Confirm the common-phase and mode statement to calculate TUmix and RQmix.")

        if st.session_state.get("external_mixture_basket"):
            st.markdown("### Components added from the single-chemical tab")
            render_external_mixture_basket(
                phase=phase,
                assessment_factor=assessment_factor,
                median_critical_burden=critical_burden,
            )


def compact_comptox_search() -> CompToxEvidenceBundle | None:
    """Provide optional identity retrieval without turning the assessment into an evidence page."""

    key = api_key()
    with st.expander("Optional: retrieve chemical identity from EPA CompTox", expanded=False):
        st.caption(
            "Use an exact name, CAS RN, DTXSID, or InChIKey. The retrieved molecular weight can be used for "
            "mass-to-molar conversion; fish LC50 evidence remains contextual and is not required by the direct TPM pathway."
        )
        search_cols = st.columns([3, 1])
        query = search_cols[0].text_input(
            "CompTox search", key="focused_comptox_query", label_visibility="collapsed",
            placeholder="Name, CAS RN, DTXSID, or InChIKey",
        )
        retrieve = search_cols[1].button(
            "Retrieve",
            type="secondary",
            disabled=not key or not query,
            key="focused_comptox_button",
            width="stretch",
        )
        if not key:
            st.info("No CompTox API key is configured; manual identity entry remains available.")
        if retrieve:
            try:
                with st.spinner("Retrieving EPA identity and fish evidence..."):
                    bundle = CompToxClient(key).evidence_bundle(query)
                st.session_state["comptox_evidence"] = bundle
                st.session_state["comptox_identity"] = bundle.identity
            except CompToxError as error:
                st.error(str(error))

        bundle = st.session_state.get("comptox_evidence")
        if bundle:
            identity = bundle.identity
            fish = bundle.fish_lc50
            evidence_cols = st.columns(3)
            evidence_cols[0].metric(
                "Identity",
                identity.preferred_name,
                help=f"CAS RN: {identity.casrn or 'not returned'}; DTXSID: {identity.dtxsid or 'not returned'}",
            )
            evidence_cols[1].metric(
                "Molecular weight",
                f"{identity.molecular_weight:.3f} g/mol" if identity.molecular_weight else "Not available",
            )
            experimental_mmol_l = mol_l_to_mmol_l(fish.experimental_mol_l) if fish else None
            evidence_cols[2].metric(
                "Experimental fish LC50 (96 h)",
                f"{format_scientific(experimental_mmol_l)} mmol/L"
                if experimental_mmol_l is not None else "Not available",
                help="ECOTOX-derived experimental median carried by the EPA TEST property dataset.",
            )
            st.caption(
                "EPA evidence is reported in mmol/L here. Full experimental/predicted separation, applicability, "
                "and external source links remain available in the CompTox fish page."
            )

    bundle = st.session_state.get("comptox_evidence")
    if bundle:
        identity = bundle.identity
        st.markdown(
            f'<div class="basis-line"><b>CompTox identity loaded:</b> {identity.preferred_name} · '
            f'CAS {identity.casrn or "not returned"} · {identity.dtxsid or "no DTXSID"}</div>',
            unsafe_allow_html=True,
        )
    return bundle


def mixture_risk_figure(output: pd.DataFrame, total_rq: float) -> go.Figure:
    """Return a single, directly interpretable component-to-mixture RQ plot."""

    plot_data = output.copy()
    plot_data["assessment"] = "Mixture RQ"
    figure = px.bar(
        plot_data,
        x="rq_contribution",
        y="assessment",
        color="chemical",
        orientation="h",
        hover_data={
            "rq_contribution": ":.4g",
            "toxic_unit": ":.4g",
            "plastic_equivalent_mmol_kg": ":.4g",
            "assessment": False,
        },
        labels={
            "rq_contribution": "Risk-quotient contribution",
            "assessment": "",
            "chemical": "Chemical",
        },
        title="Component contributions to mixture risk",
    )
    figure.add_vline(
        x=1,
        line_width=2,
        line_dash="dash",
        line_color="#b65b42",
        annotation_text="RQ = 1",
    )
    figure.update_layout(
        barmode="stack",
        height=330,
        margin=dict(l=10, r=20, t=60, b=10),
        plot_bgcolor="white",
        legend_title_text="",
        legend_orientation="h",
        legend_y=-0.32,
        xaxis=dict(
            range=[0, max(1.08, total_rq * 1.12)],
            showgrid=True,
            gridcolor="#e6efec",
        ),
    )
    return figure


def focused_single_assessment(
    *, mode: str, phase: str, assessment_factor: float,
    critical_burden: float, pnec: float,
) -> None:
    st.markdown('<div class="step-label">Step 2 · Chemical identity</div>', unsafe_allow_html=True)
    bundle = compact_comptox_search()
    identity = bundle.identity if bundle else None
    loaded_id = identity.dtxsid if identity else None
    if loaded_id and st.session_state.get("focused_loaded_dtxsid") != loaded_id:
        st.session_state["focused_chemical_name"] = identity.preferred_name
        if identity.molecular_weight is not None:
            st.session_state["focused_molecular_weight"] = float(identity.molecular_weight)
        st.session_state["focused_loaded_dtxsid"] = loaded_id
    if "focused_chemical_name" not in st.session_state:
        st.session_state["focused_chemical_name"] = "Naphthalene"
    if "focused_molecular_weight" not in st.session_state:
        st.session_state["focused_molecular_weight"] = 128.1702

    identity_cols = st.columns([1.4, 1, 1])
    chemical_name = identity_cols[0].text_input("Chemical", key="focused_chemical_name")
    molecular_weight = identity_cols[1].number_input(
        "Molecular weight (g/mol)", min_value=0.001, format="%.4f",
        key="focused_molecular_weight",
        help="Needed only when the analytical concentration is reported on a mass basis.",
    )
    mode_confidence = identity_cols[2].selectbox(
        "Toxic-mode confidence", ["Established", "Provisional", "Unknown"],
        key="focused_mode_confidence",
    )

    st.markdown('<div class="step-label">Step 3 · Analytical measurement</div>', unsafe_allow_html=True)
    measurement_basis = st.segmented_control(
        "Measurement source",
        ["Plastic or passive sampler", "Water column"],
        default="Plastic or passive sampler",
        key="focused_single_basis",
        width="stretch",
    )
    input_cols = st.columns([1.25, 1, 1.25])
    concentration = input_cols[0].number_input(
        "Measured concentration", min_value=0.0, value=10.0, format="%.6g",
        key="focused_single_concentration",
    )
    log_k = None
    partition_method = "Not required"
    if measurement_basis == "Plastic or passive sampler":
        unit = input_cols[1].selectbox(
            "Reported unit",
            ["ng/g", "ug/g", "mg/g", "ng/kg", "ug/kg", "mg/kg", "mmol/kg", "mol/kg"],
            key="focused_single_plastic_unit",
        )
        input_cols[2].markdown(
            '<div class="quiet-note" style="padding-top:1.8rem"><b>Direct TPM route.</b><br>'
            'No LC50 or K<sub>plastic-water</sub> enters the TU calculation.</div>',
            unsafe_allow_html=True,
        )
    else:
        unit = input_cols[1].selectbox(
            "Reported unit", ["ng/L", "ug/L", "mg/L", "mmol/L", "mol/L"],
            key="focused_single_water_unit",
        )
        partition_options = ["Measured log Kplastic-water"]
        if bundle and bundle.log_kow.selected_value is not None:
            partition_options.append("Estimate from CompTox logKow")
        partition_method = input_cols[2].selectbox(
            "Partition conversion", partition_options, key="focused_single_partition_method"
        )
        if partition_method == "Estimate from CompTox logKow":
            lfer = model_registry()["log_kow_lfer"][phase]
            log_k = lfer_log_k(
                float(bundle.log_kow.selected_value), lfer["intercept"], lfer["slope"]
            )
            st.caption(
                f"Estimated log K{phase_label(phase)}-water = {log_k:.3f} using {lfer['label']}. "
                "This is a secondary, partition-dependent route."
            )
        else:
            log_k = st.number_input(
                f"Measured log K{phase_label(phase)}-water", value=3.0, step=0.1,
                key="focused_single_log_k",
            )

    signature = repr(
        (mode, phase, assessment_factor, measurement_basis, chemical_name, molecular_weight,
         concentration, unit, log_k, mode_confidence)
    )
    calculate = st.button(
        "Calculate single-chemical risk", type="primary",
        key="focused_single_calculate", width="stretch",
    )
    if calculate:
        try:
            if measurement_basis == "Plastic or passive sampler":
                plastic_exposure = exposure_to_mmol_kg(concentration, unit, molecular_weight)
            else:
                plastic_exposure = water_concentration_to_plastic_mmol_kg(
                    concentration, unit, molecular_weight, log_k
                )
            component_tu = toxic_unit(plastic_exposure, critical_burden)
            st.session_state["focused_single_result"] = {
                "signature": signature,
                "chemical": chemical_name,
                "casrn": identity.casrn if identity else "",
                "dtxsid": identity.dtxsid if identity else "",
                "measurement_basis": measurement_basis,
                "reported_concentration": concentration,
                "reported_unit": unit,
                "molecular_weight_g_mol": molecular_weight,
                "log_k_phase_water": log_k,
                "partition_method": partition_method,
                "plastic_equivalent_mmol_kg": plastic_exposure,
                "median_critical_burden_mmol_kg": critical_burden,
                "toxic_unit": component_tu,
                "PNECplastic_eq_mmol_kg": pnec,
                "assessment_factor": assessment_factor,
                "risk_quotient": component_tu * assessment_factor,
                "mode_confidence": mode_confidence,
                "toxic_mode": mode,
                "plastic_phase": phase,
            }
        except ScientificInputError as error:
            st.session_state.pop("focused_single_result", None)
            st.error(str(error))

    result = st.session_state.get("focused_single_result")
    if result and result["signature"] != signature:
        st.info("Inputs have changed. Recalculate to update the assessment.")
        return
    if not result:
        return

    st.markdown('<div class="step-label">Step 4 · Risk result</div>', unsafe_allow_html=True)
    rq = float(result["risk_quotient"])
    risk_class = "result-high" if rq >= 1 else "result-low"
    risk_text = (
        "RQ ≥ 1 · The plastic-equivalent concentration exceeds the selected screening threshold."
        if rq >= 1
        else "RQ < 1 · The plastic-equivalent concentration is below the selected screening threshold."
    )
    st.markdown(f'<div class="result-banner {risk_class}">{risk_text}</div>', unsafe_allow_html=True)
    result_cols = st.columns(3)
    result_cols[0].metric("Cplastic used", f"{result['plastic_equivalent_mmol_kg']:.4g} mmol/kg")
    result_cols[1].metric("Toxic unit", f"{result['toxic_unit']:.4g}")
    result_cols[2].metric("Risk quotient", f"{rq:.4g}")
    st.plotly_chart(
        exposure_threshold_figure(
            exposure_mmol_kg=float(result["plastic_equivalent_mmol_kg"]),
            pnec_mmol_kg=pnec,
            critical_burden_mmol_kg=critical_burden,
        ),
        width="stretch",
    )
    if mode_confidence != "Established":
        st.warning("Interpretation remains provisional until the toxic-mode assignment is established.")
    export_row = {key: value for key, value in result.items() if key != "signature"}
    action_cols = st.columns([1, 2])
    action_cols[0].download_button(
        "Download result", pd.DataFrame([export_row]).to_csv(index=False),
        "tpm_single_assessment.csv", "text/csv",
    )
    with st.expander("Calculation audit", expanded=False):
        st.dataframe(
            pd.DataFrame([
                {"stage": "Reported concentration", "value": concentration, "unit": unit},
                {"stage": "Cplastic used", "value": result["plastic_equivalent_mmol_kg"], "unit": "mmol/kg plastic"},
                {"stage": "Median critical burden", "value": critical_burden, "unit": "mmol/kg plastic"},
                {"stage": "Toxic unit", "value": result["toxic_unit"], "unit": "dimensionless"},
                {"stage": "PNECplastic,eq", "value": pnec, "unit": "mmol/kg plastic"},
                {"stage": "Risk quotient", "value": rq, "unit": "dimensionless"},
            ]),
            width="stretch", hide_index=True,
        )


def focused_mixture_assessment(
    *, mode: str, phase: str, assessment_factor: float,
    critical_burden: float, pnec: float,
) -> None:
    st.markdown('<div class="step-label">Step 2 · Compatible mixture</div>', unsafe_allow_html=True)
    st.caption(
        "Enter chemicals measured on one common plastic phase. The included PAHs are editable examples, not universal environmental concentrations."
    )
    measurement_basis = st.segmented_control(
        "Measurement source",
        ["Plastic or passive sampler", "Water column"],
        default="Plastic or passive sampler",
        key="focused_mixture_basis",
        width="stretch",
    )
    if measurement_basis == "Plastic or passive sampler":
        data_basis = "Measured on plastic/passive sampler"
    else:
        data_basis = "Measured in the water column"
        st.warning("Every water-column row requires a chemical-specific log Kplastic-water conversion.")
    template = environmental_example_frame(phase, data_basis)
    if mode != "baseline":
        template["mode_confidence"] = "Unknown"
        st.warning("Mixture concentration addition is enabled only for compatible baseline toxicants.")

    st.markdown('<div class="step-label">Step 3 · Analytical measurements</div>', unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "Upload mixture CSV (optional)", type=["csv"], key="focused_mixture_upload"
    )
    if uploaded is not None:
        try:
            template = pd.read_csv(uploaded)
        except Exception as error:
            st.error(f"The CSV could not be read: {error}")
    editor_columns = [
        "sample_id", "chemical", "casrn", "molecular_weight_g_mol",
        "concentration", "unit", "mode_confidence",
    ]
    if measurement_basis == "Water column":
        editor_columns.insert(6, "log_k_phase_water")
    editor_columns = [column for column in editor_columns if column in template.columns]
    edited = st.data_editor(
        template,
        column_order=editor_columns,
        num_rows="dynamic",
        width="stretch",
        hide_index=True,
        key=f"focused_mixture_editor_{'plastic' if measurement_basis.startswith('Plastic') else 'water'}",
        column_config={
            "sample_id": "Sample",
            "chemical": "Chemical",
            "casrn": "CAS RN",
            "molecular_weight_g_mol": st.column_config.NumberColumn("MW (g/mol)", min_value=0.001),
            "concentration": st.column_config.NumberColumn("Measured value", min_value=0.0, format="%.6g"),
            "unit": st.column_config.SelectboxColumn(
                "Unit",
                options=(
                    ["ng/g", "ug/g", "mg/g", "ng/kg", "ug/kg", "mg/kg", "mmol/kg", "mol/kg"]
                    if measurement_basis == "Plastic or passive sampler"
                    else ["ng/L", "ug/L", "mg/L", "mmol/L", "mol/L"]
                ),
                required=True,
            ),
            "log_k_phase_water": st.column_config.NumberColumn("log Kplastic-water", format="%.3f"),
            "mode_confidence": st.column_config.SelectboxColumn(
                "Mode confidence", options=["Established", "Provisional", "Unknown"], required=True
            ),
        },
    )
    compatibility = st.checkbox(
        "I confirm a common plastic phase and compatible baseline toxic mode for all rows.",
        key="focused_mixture_compatibility",
    )
    data_signature = edited.to_json(orient="split", default_handler=str)
    signature = repr((mode, phase, assessment_factor, measurement_basis, compatibility, data_signature))
    calculate = st.button(
        "Calculate mixture risk",
        type="primary",
        key="focused_mixture_calculate",
        width="stretch",
        disabled=not compatibility or mode != "baseline",
    )
    if calculate:
        required = {"sample_id", "chemical", "concentration", "unit", "molecular_weight_g_mol"}
        missing = required - set(edited.columns)
        if missing:
            st.error(f"Missing required columns: {', '.join(sorted(missing))}")
        elif edited["sample_id"].dropna().astype(str).nunique() != 1:
            st.error(
                "The guided start page evaluates one mixture sample at a time. "
                "Use one sample ID here or open Advanced field processor for batch analysis."
            )
        else:
            output = edited.copy()
            exposures: list[float] = []
            errors: list[str] = []
            for index, row in output.iterrows():
                try:
                    if measurement_basis == "Plastic or passive sampler":
                        exposure = exposure_to_mmol_kg(
                            row["concentration"], row["unit"], row["molecular_weight_g_mol"]
                        )
                    else:
                        exposure = water_concentration_to_plastic_mmol_kg(
                            row["concentration"], row["unit"], row["molecular_weight_g_mol"],
                            row.get("log_k_phase_water", math.nan),
                        )
                    exposures.append(exposure)
                except ScientificInputError as error:
                    exposures.append(math.nan)
                    errors.append(f"Row {index + 1}: {error}")
            if errors:
                st.session_state.pop("focused_mixture_result", None)
                st.error("\n".join(errors))
            else:
                output["plastic_equivalent_mmol_kg"] = exposures
                output["median_critical_burden_mmol_kg"] = critical_burden
                output["toxic_unit"] = output["plastic_equivalent_mmol_kg"] / critical_burden
                output["rq_contribution"] = output["toxic_unit"] * assessment_factor
                total_tu = float(output["toxic_unit"].sum())
                st.session_state["focused_mixture_result"] = {
                    "signature": signature,
                    "rows": output.to_dict(orient="records"),
                    "total_tu": total_tu,
                    "total_rq": total_tu * assessment_factor,
                }

    result = st.session_state.get("focused_mixture_result")
    if result and result["signature"] != signature:
        st.info("Mixture inputs have changed. Recalculate to update the result.")
        return
    if not result:
        return
    output = pd.DataFrame(result["rows"])
    total_rq = float(result["total_rq"])
    st.markdown('<div class="step-label">Step 4 · Mixture risk result</div>', unsafe_allow_html=True)
    risk_class = "result-high" if total_rq >= 1 else "result-low"
    risk_text = (
        "Mixture RQ ≥ 1 · Summed toxic units exceed the selected screening threshold."
        if total_rq >= 1
        else "Mixture RQ < 1 · Summed toxic units are below the selected screening threshold."
    )
    st.markdown(f'<div class="result-banner {risk_class}">{risk_text}</div>', unsafe_allow_html=True)
    metrics = st.columns(3)
    metrics[0].metric("Components", len(output))
    metrics[1].metric("Mixture toxic units", f"{result['total_tu']:.4g}")
    metrics[2].metric("Mixture risk quotient", f"{total_rq:.4g}")
    st.plotly_chart(mixture_risk_figure(output, total_rq), width="stretch")
    concise = output[[
        column for column in [
            "chemical", "plastic_equivalent_mmol_kg", "toxic_unit", "rq_contribution"
        ] if column in output.columns
    ]]
    st.dataframe(concise, width="stretch", hide_index=True)
    with st.expander("Full mixture calculation and downloads", expanded=False):
        st.dataframe(output, width="stretch", hide_index=True)
        summary = pd.DataFrame([{
            "components": len(output),
            "median_critical_burden_mmol_kg": critical_burden,
            "PNECplastic_eq_mmol_kg": pnec,
            "assessment_factor": assessment_factor,
            "TU_mix": result["total_tu"],
            "RQ_mix": total_rq,
        }])
        downloads = st.columns(2)
        downloads[0].download_button(
            "Download components", output.to_csv(index=False),
            "tpm_mixture_components.csv", "text/csv",
        )
        downloads[1].download_button(
            "Download summary", summary.to_csv(index=False),
            "tpm_mixture_summary.csv", "text/csv",
        )


def direct_assessment_page() -> None:
    """Focused first-page assessment with one visible path at a time."""

    intro, art = st.columns([0.9, 1.1], gap="large", vertical_alignment="center")
    with intro:
        st.markdown(
            """
            <div class="start-copy">
              <div class="section-kicker">Target Plastic Model</div>
              <h1>Measure on plastic.<br>Screen toxicity directly.</h1>
              <p>Convert one chemical or a compatible mixture from an analytical plastic burden to toxic units and ecological risk. Chemical-specific LC50 and Kplastic-water are not required for the primary pathway.</p>
              <div class="start-formula">TU<sub>i</sub> = C<sub>plastic,i</sub> / median C<sub>plastic</sub><sup>crit</sup>
              &nbsp;&nbsp; · &nbsp;&nbsp; RQ = &Sigma;TU × AF</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with art:
        concept_art = ROOT / "assets" / "tpm-concept-art.png"
        if concept_art.exists():
            st.image(str(concept_art), width="stretch")
            st.markdown(
                '<div class="concept-caption">Conceptual basis: mixture toxicity assessment from critical plastic burdens without chemical-specific LC50 values. The burden range shown in the schematic is illustrative; calculations use the selected phase- and toxic-mode-specific SI median.</div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <div class="assessment-rail">
          <span>1 · Context</span><i>→</i><span>2 · Chemicals</span><i>→</i>
          <span>3 · Measurements</span><i>→</i><span>4 · TU and RQ</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("## New assessment")
    context_cols = st.columns(3)
    mode = context_cols[0].selectbox(
        "Toxic mode", ["baseline", "less_inert"], format_func=mode_label,
        key="focused_mode",
        help="Toxic-mode assignment remains an expert input.",
    )
    phase = context_cols[1].selectbox(
        "Validated plastic phase", phase_options(True), format_func=phase_label,
        key="focused_phase",
    )
    af_basis = context_cols[2].selectbox(
        "Assessment factor",
        ["Freshwater · 1,000", "Marine · 10,000", "Custom"],
        key="focused_af_basis",
    )
    if af_basis == "Freshwater · 1,000":
        assessment_factor = 1000.0
    elif af_basis == "Marine · 10,000":
        assessment_factor = 10000.0
    else:
        assessment_factor = context_cols[2].number_input(
            "Custom assessment factor", min_value=0.01, value=1000.0,
            key="focused_custom_af",
        )
    burden = burden_record(mode, phase)
    critical_burden = float(burden["critical_burden_mmol_kg"])
    pnec = plastic_phase_pnec(critical_burden, assessment_factor)
    st.markdown(
        f'<div class="basis-line"><b>Active basis:</b> {mode_label(mode)} · {phase_label(phase)} · '
        f'median C<sup>crit</sup><sub>plastic</sub> {critical_burden:.4g} mmol/kg plastic · '
        f'PNEC<sub>plastic,eq</sub> {pnec:.4g} mmol/kg plastic · AF {assessment_factor:,.0f}</div>',
        unsafe_allow_html=True,
    )
    assessment_type = st.segmented_control(
        "Assessment type", ["Single chemical", "Mixture"],
        default="Single chemical", key="focused_assessment_type", width="stretch",
    )
    if assessment_type == "Mixture":
        focused_mixture_assessment(
            mode=mode, phase=phase, assessment_factor=assessment_factor,
            critical_burden=critical_burden, pnec=pnec,
        )
    else:
        focused_single_assessment(
            mode=mode, phase=phase, assessment_factor=assessment_factor,
            critical_burden=critical_burden, pnec=pnec,
        )

    with st.expander("Scientific boundary of the direct pathway", expanded=False):
        st.markdown(
            "The direct TPM calculation applies to concentrations measured on the selected plastic or passive-sampler phase. "
            "A water-column concentration must first be translated to a plastic-equivalent burden using an explicit, "
            "chemical-specific Kplastic-water. Concentration addition is restricted to scientifically compatible baseline toxicants."
        )
        st.link_button("Read the peer-reviewed paper", PAPER_URL)


def overview_page() -> None:
    hero(
        "Target Plastic Model Explorer",
        "A transparent research dashboard for translating plastic–water partitioning into acute fish toxicity estimates, mixture toxic units, and model evidence.",
        "Paper-connected scientific workbench",
    )
    manifest = dataset_manifest()
    burdens = critical_burdens()
    st.markdown(
        """
        <div class="evidence-card"><b>Primary TPM hypothesis: toxicity can be screened directly from the plastic measurement.</b><br>
        For a chemical assigned to the appropriate toxic mode and measured on a validated plastic phase, the analyst divides the
        measured plastic burden by the phase- and mode-specific median critical plastic burden. A chemical-specific LC50 and
        plastic-water partition coefficient are <b>not required</b> for this primary toxic-unit calculation.</div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="formula">TU<sub>i</sub> = C<sub>plastic,i</sub> / median C<sub>plastic,mode,phase</sub><sup>crit</sup> &nbsp;&nbsp; | &nbsp;&nbsp; '
        '&Sigma;TU = &Sigma;TU<sub>i</sub> &nbsp;&nbsp; | &nbsp;&nbsp; RQ = &Sigma;TU &times; AF</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Start with Direct toxicity in the sidebar. Use Single chemical or CompTox fish only when a deeper LC50, partitioning, or evidence comparison is needed."
    )
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Published records", f"{sum(item['rows'] for item in manifest['datasets'].values()):,}")
    col2.metric("Validated plastics", "5")
    col3.metric("Toxicity modes", "3", help="Reactive mode is evidence-only")
    col4.metric("Release", f"v{__version__}")

    st.markdown("### What the dashboard makes usable")
    left, right = st.columns([1.15, 1])
    with left:
        st.markdown(
            """
            <div class="evidence-card"><b>From a paper equation to an auditable workflow</b><br>
            The direct workflow converts measured plastic-associated concentrations to toxic units using the published
            median critical burden. Optional deeper modules can investigate LC50 prediction, partitioning,
            applicability, and external evidence without making those inputs prerequisites.</div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown("")
        st.markdown(
            """
            <div class="formula">Primary: TU = C<sub>plastic</sub> / median C<sub>plastic</sub><sup>crit</sup><br>
            <span style="font-size:.82em">Optional mechanistic extension: −log<sub>10</sub> LC50 = log<sub>10</sub> K<sub>plastic–water</sub> + (−log<sub>10</sub> C<sub>crit</sub>)</span></div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("**Evidence boundaries**")
        st.markdown(
            """
            - Prediction is enabled for **baseline** and **less-inert** modes only.
            - PDMS, PA, POM, PE/LDPE, and PU are the validated plastic phases.
            - Reactive-toxicant and other-plastic results remain visible for scientific review, not calculation.
            - Mixture addition is conditional on a common phase, toxic mode, and equilibrium assumption.
            """
        )

    baseline = burdens[(burdens["toxic_mode"] == "baseline") & burdens["phase"].isin(phase_options(True))].copy()
    baseline["phase_label"] = baseline["phase"].map(phase_label)
    figure = px.bar(
        baseline,
        x="phase_label",
        y="critical_burden_mmol_kg",
        color="rmse_validation_log_unit",
        color_continuous_scale=[[0, "#b9dfd2"], [1, "#0b6e69"]],
        labels={
            "phase_label": "Validated plastic phase",
            "critical_burden_mmol_kg": "Median critical burden (mmol/kg)",
            "rmse_validation_log_unit": "Validation RMSE",
        },
        title="Baseline median critical burdens and external-validation error",
    )
    figure.update_layout(height=420, margin=dict(l=10, r=10, t=55, b=10), plot_bgcolor="white")
    st.plotly_chart(figure, width="stretch")

    st.markdown(
        f"Read the [peer-reviewed paper]({PAPER_URL}) or open **Evidence & methods** for provenance, limitations, downloads, and the unit audit."
    )


def _legacy_comptox_lookup_panel() -> None:
    with st.expander("EPA CompTox identity and fish-toxicity bridge", expanded=False):
        st.caption(
            "CompTox is optional. The API key stays in Streamlit secrets and is never written to the dataset. "
            "Identity is retrieved by exact match; WebTEST and ECOTOX open as clearly labeled external evidence."
        )
        key = api_key()
        query = st.text_input("Name, CAS RN, DTXSID, or InChIKey", key="comptox_query")
        if not key:
            st.info("No API key is configured. Manual inputs and the published dataset remain fully available.")
            st.link_button("Request/read about EPA CTX API access", "https://www.epa.gov/comptox-tools/computational-toxicology-and-exposure-apis-about")
        if st.button("Retrieve exact identity", disabled=not key or not query, type="secondary"):
            try:
                with st.spinner("Querying EPA CompTox…"):
                    identity = CompToxClient(key).exact_identity(query)
                st.session_state["comptox_identity"] = identity
            except CompToxError as error:
                st.error(str(error))
        identity = st.session_state.get("comptox_identity")
        if identity:
            cols = st.columns(4)
            cols[0].metric("Preferred name", identity.preferred_name)
            cols[1].metric("DTXSID", identity.dtxsid or "—")
            cols[2].metric("CAS RN", identity.casrn or "—")
            cols[3].metric("Molecular weight", f"{identity.molecular_weight:.3f} g/mol" if identity.molecular_weight else "—")
            st.code(identity.smiles or "No structure returned", language=None)
            links = st.columns(3)
            links[0].link_button("CompTox chemical page", comptox_dashboard_url(identity.dtxsid))
            links[1].link_button(
                "WebTEST 96 h fathead minnow",
                webtest_report_url(identity.smiles),
                disabled=not identity.smiles,
            )
            links[2].link_button("Search experimental fish studies in ECOTOX", ECOTOX_URL)
            st.caption("WebTEST is a QSAR prediction; ECOTOX contains study-level ecotoxicity records. Neither is silently substituted for the paper's curated LC50 values.")


def render_comptox_evidence(bundle: CompToxEvidenceBundle) -> None:
    """Render a compact EPA evidence summary in the dashboard's common molar units."""

    identity = bundle.identity
    molecular_formula = (
        identity.raw.get("molFormula")
        or identity.raw.get("molecularFormula")
        or identity.raw.get("formula")
    )
    identity_cols = st.columns([1.2, 1, 1, 1, 1])
    identity_cols[0].metric("Chemical", identity.preferred_name)
    identity_cols[1].metric("CAS RN", identity.casrn or "-")
    identity_cols[2].metric("DTXSID", identity.dtxsid or "-")
    identity_cols[3].metric("Formula", molecular_formula or "-")
    identity_cols[4].metric(
        "Molecular weight",
        f"{identity.molecular_weight:.3f} g/mol" if identity.molecular_weight else "-",
    )

    fish = bundle.fish_lc50
    experimental_mmol_l = mol_l_to_mmol_l(fish.experimental_mol_l) if fish else None
    predicted_mmol_l = mol_l_to_mmol_l(fish.predicted_mol_l) if fish else None
    evidence_rows = []
    if experimental_mmol_l is not None:
        evidence_rows.append(
            {
                "Evidence": "ECOTOX-derived experimental median",
                "LC50_mmol_L": experimental_mmol_l,
                "Status": "Experimental reference via EPA TEST dataset",
            }
        )
    if predicted_mmol_l is not None:
        evidence_rows.append(
            {
                "Evidence": "EPA TEST consensus prediction",
                "LC50_mmol_L": predicted_mmol_l,
                "Status": fish.applicability_conclusion or "Applicability not reported",
            }
        )

    fish_cols = st.columns(3)
    fish_cols[0].metric(
        "ECOTOX-derived experimental 96 h LC50",
        f"{format_scientific(experimental_mmol_l)} mmol/L" if experimental_mmol_l is not None else "Not available",
        help="EPA TEST's experimental value is the median of its filtered freshwater laboratory 96-hour fathead-minnow LC50 dataset derived from ECOTOX. Review study-level records in ECOTOX before assessment-grade use.",
    )
    fish_cols[1].metric(
        "EPA TEST predicted LC50",
        f"{format_scientific(predicted_mmol_l)} mmol/L" if predicted_mmol_l is not None else "Not available",
    )
    fish_cols[2].metric(
        "TEST applicability",
        fish.applicability_conclusion if fish and fish.applicability_conclusion else "Not available",
    )

    if evidence_rows:
        evidence_frame = pd.DataFrame(evidence_rows)
        evidence_figure = px.bar(
            evidence_frame,
            x="LC50_mmol_L",
            y="Evidence",
            orientation="h",
            color="Evidence",
            log_x=True,
            text_auto=".3g",
            color_discrete_sequence=["#08776f", "#6a5aa8"],
            labels={"LC50_mmol_L": "LC50 (mmol/L)", "Evidence": ""},
            title="EPA fish evidence in a common molar unit",
        )
        evidence_figure.update_layout(
            height=280,
            margin=dict(l=10, r=20, t=55, b=10),
            plot_bgcolor="white",
            showlegend=False,
            xaxis=dict(showgrid=True, gridcolor="#e6efec"),
        )
        st.plotly_chart(evidence_figure, width="stretch")

    log_kow = bundle.log_kow
    if log_kow.selected_value is not None:
        count = (
            log_kow.experimental_count
            if log_kow.selected_basis.startswith("experimental")
            else log_kow.predicted_count
        )
        range_text = ""
        if log_kow.experimental_min is not None and log_kow.experimental_max is not None:
            range_text = f"; experimental range {log_kow.experimental_min:.3g}-{log_kow.experimental_max:.3g}"
        st.info(
            f"CompTox logKow for optional partition screening: **{log_kow.selected_value:.3f}** "
            f"({log_kow.selected_basis}; n={count}{range_text})."
        )
    else:
        st.warning("CompTox returned no usable logKow summary for automatic partition screening.")
    with st.expander("Evidence detail and original units", expanded=False):
        if evidence_rows:
            detail_rows = []
            if experimental_mmol_l is not None:
                detail_rows.append({
                    "record": "Experimental median",
                    "LC50_mmol_L": experimental_mmol_l,
                    "negative_log10_mol_L": fish.experimental_neglog_mol_l,
                })
            if predicted_mmol_l is not None:
                detail_rows.append({
                    "record": "TEST prediction",
                    "LC50_mmol_L": predicted_mmol_l,
                    "negative_log10_mol_L": fish.predicted_neglog_mol_l,
                })
            st.dataframe(pd.DataFrame(detail_rows), width="stretch", hide_index=True)
        st.caption(f"Canonical structure: {identity.smiles or 'not returned'}")
        if fish and fish.applicability_reasoning:
            st.caption(f"EPA TEST applicability note: {fish.applicability_reasoning}")


def comptox_lookup_panel(
    expanded: bool = False, *, inline: bool = False
) -> CompToxEvidenceBundle | None:
    panel = st.container(border=True) if inline else st.expander(
        "Optional EPA CompTox evidence workspace", expanded=expanded
    )
    with panel:
        if inline:
            st.markdown("**EPA CompTox identity and fish evidence**")
        st.caption(
            "Search an exact substance to retrieve identity, molecular weight, logKow, and EPA TEST 96-hour "
            "fathead-minnow evidence. Fish LC50 is displayed in mmol/L; the API key remains in Streamlit secrets."
        )
        key = api_key()
        query = st.text_input("Name, CAS RN, DTXSID, or InChIKey", key="comptox_query")
        if not key:
            st.info("No API key is configured. Manual inputs and the published dataset remain fully available.")
            st.link_button(
                "EPA CTX API access information",
                "https://www.epa.gov/comptox-tools/computational-toxicology-and-exposure-apis-about",
            )
        if st.button(
            "Retrieve identity + fish LC50 + logKow",
            disabled=not key or not query,
            type="secondary",
            key="comptox_evidence_button",
        ):
            try:
                with st.spinner("Retrieving EPA CompTox evidence..."):
                    bundle = CompToxClient(key).evidence_bundle(query)
                st.session_state["comptox_evidence"] = bundle
                st.session_state["comptox_identity"] = bundle.identity
                if bundle.log_kow.selected_value is not None:
                    st.session_state["single_partition_input"] = "CompTox logKow screening"
            except CompToxError as error:
                st.error(str(error))
        bundle = st.session_state.get("comptox_evidence")
        if bundle:
            render_comptox_evidence(bundle)
            with st.expander("External evidence links and provenance", expanded=False):
                st.code(bundle.identity.smiles or "No structure returned", language=None)
                links = st.columns(4)
                links[0].link_button(
                    "CompTox chemical page", comptox_dashboard_url(bundle.identity.dtxsid)
                )
                links[1].link_button(
                    "Current WebTEST result",
                    webtest_report_url(bundle.identity.smiles),
                    disabled=not bundle.identity.smiles,
                )
                links[2].link_button("Search ECOTOX studies", ECOTOX_URL)
                links[3].link_button("UFZ-LSER descriptors", UFZ_LSER_URL)
                st.caption(
                    "The TEST experimental field is an EPA property reference, not a substitute for study-level ECOTOX review. "
                    "Experimental and predicted values remain separately labeled throughout the dashboard."
                )
        return bundle


def _legacy_single_chemical_page() -> None:
    hero(
        "Single-chemical calculator",
        "Predict acute fish LC50 with a validated plastic phase, a declared toxic mode, and fully visible model inputs.",
        "TPM calculator",
    )
    comptox_lookup_panel()

    mode_col, phase_col, source_col = st.columns([1, 1, 1.35])
    mode = mode_col.selectbox(
        "Toxic mode",
        ["baseline", "less_inert", "reactive"],
        format_func=mode_label,
        help="Mode assignment is a scientific input, not an output of this app.",
    )
    phase = phase_col.selectbox("Plastic phase", phase_options(True), format_func=phase_label)
    input_source = source_col.radio(
        "Partition input",
        ["Published compound", "Measured log K", "Abraham descriptors"],
        horizontal=True,
    )

    mode_info = model_registry()["modes"][mode]
    if mode == "reactive":
        st.markdown(
            '<div class="warning-card"><b>Evidence-only mode.</b> Reactive-toxicant prediction is disabled because a partition-controlled critical burden does not represent specific reactivity.</div>',
            unsafe_allow_html=True,
        )

    records = validation_records()
    available = records[records["toxic_mode"] == mode].copy()
    descriptor_values = None
    observed = None
    compound_name = "Manual chemical"
    if input_source == "Published compound":
        available["selector"] = available.apply(
            lambda row: f"{row['name']} · {row['casrn']} · {row['set_label']}", axis=1
        )
        selected_label = st.selectbox("Published record", available["selector"].tolist())
        selected = available.loc[available["selector"] == selected_label].iloc[0]
        compound_name = str(selected["name"])
        mw = float(selected["molecular_weight_g_mol"])
        log_k = selected[phase_log_k_column(phase)]
        observed = float(selected["experimental_neglog_lc50_mol_l"])
        st.caption(f"CAS RN {selected['casrn']} · {selected['chemical_class']} · source cohort: {selected['set_label']}")
    else:
        identity = st.session_state.get("comptox_identity")
        default_mw = float(identity.molecular_weight) if identity and identity.molecular_weight else 100.0
        compound_name = identity.preferred_name if identity else "Manual chemical"
        mw = st.number_input("Molecular weight (g/mol)", min_value=0.001, value=default_mw, step=1.0, format="%.4f")
        if input_source == "Measured log K":
            log_k = st.number_input(f"Measured log₁₀ K{phase_label(phase)}–water", value=3.0, step=0.1)
        else:
            coefficients = model_registry()["abraham_coefficients"][phase]
            st.caption("Enter E, S, A, B, V, and L solute descriptors. Coefficients are versioned in the model registry.")
            cols = st.columns(6)
            descriptor_values = {
                key: cols[index].number_input(key.upper(), value=0.0, step=0.05, key=f"descriptor_{key}")
                for index, key in enumerate(("e", "s", "a", "b", "v", "l"))
            }
            log_k = abraham_log_k(descriptor_values, coefficients)
            st.info(f"Calculated log₁₀ K{phase_label(phase)}–water = **{log_k:.3f}**")

    burden = burden_record(mode, phase)
    result_columns = st.columns([1, 1, 1])
    result_columns[0].metric("Median critical burden", f"{burden['critical_burden_mmol_kg']:.4g} mmol/kg")
    result_columns[1].metric("Partition coefficient", f"log K = {float(log_k):.3f}" if pd.notna(log_k) else "Unavailable")
    result_columns[2].metric("Evidence status", mode_info["calculator_status"].replace("_", " ").title())

    if pd.isna(log_k):
        st.error("This published record has no usable partition coefficient for the selected phase.")
        return
    if mode == "reactive":
        st.caption("The stored reactive critical-burden distribution remains available in Polymer atlas for source verification.")
        return
    try:
        prediction = predict_lc50(
            phase,
            mode,
            float(log_k),
            float(burden["neglog_critical_burden_mol_kg"]),
            float(mw),
        )
    except ScientificInputError as error:
        st.error(str(error))
        return

    st.markdown("### Prediction")
    left, middle, right = st.columns(3)
    left.metric(
        "Predicted pLC50", f"{prediction.predicted_neglog_lc50_mol_l:.3f}",
        help="pLC50 = -log10 of LC50 expressed in mol/L.",
    )
    middle.metric(
        "Predicted LC50",
        f"{format_scientific(mol_l_to_mmol_l(prediction.predicted_lc50_mol_l))} mmol/L",
    )
    rmse = float(burden["rmse_validation_log_unit"])
    cohort_factor = 10**rmse
    selected_error = None
    if observed is not None:
        selected_error = individual_prediction_error(observed, prediction.predicted_neglog_lc50_mol_l)
        observed_mmol_l = 10 ** (-observed) * 1000
        right.metric(
            "Selected-record difference",
            f"factor {selected_error['fold_difference']:.2f}",
            help="Chemical-specific fold difference between this prediction and the published observed LC50.",
        )
        st.markdown(
            f"**Published observation:** {observed:.3f} −log₁₀(mol/L) ({format_scientific(observed_mmol_l)} mmol/L). "
            f"Record-specific error: {selected_error['log_error']:+.3f} log unit (predicted − observed)."
        )
    else:
        right.metric("Chemical-specific error", "Not available", help="An observed LC50 is required to calculate an individual prediction error.")

    with st.expander("Model-level validation context", expanded=False):
        st.markdown(
            f"For **{mode_label(mode)} with {phase_label(phase)}**, the independent validation cohort contains "
            f"**{int(burden['n_validation'])} chemicals** and has RMSE **{rmse:.3f} log unit** "
            f"(equivalent to a cohort-level factor of **{cohort_factor:.2f}**)."
        )
        st.caption(
            "This cohort statistic is intentionally the same for every chemical when the toxic mode and plastic phase are unchanged. "
            "It describes historical model performance; it is not a chemical-specific error or a calibrated confidence interval."
        )

    result_frame = pd.DataFrame([{
        "chemical": compound_name,
        "mode": mode,
        "phase": phase,
        "molecular_weight_g_mol": mw,
        "log_k_phase_water": log_k,
        "neglog_critical_burden_mol_kg": burden["neglog_critical_burden_mol_kg"],
        "predicted_neglog_lc50_mol_l": prediction.predicted_neglog_lc50_mol_l,
        "predicted_lc50_mmol_l": mol_l_to_mmol_l(prediction.predicted_lc50_mol_l),
        "selected_record_error_log_unit": selected_error["log_error"] if selected_error else None,
        "selected_record_fold_difference": selected_error["fold_difference"] if selected_error else None,
        "cohort_validation_n": int(burden["n_validation"]),
        "cohort_validation_rmse_log_unit": rmse,
        "cohort_validation_factor": cohort_factor,
        "model_version": __version__,
        "paper_doi": "10.1021/acs.jcim.4c00574",
    }])
    st.download_button("Download prediction CSV", result_frame.to_csv(index=False), "tpm_prediction.csv", "text/csv")


def _v11_single_chemical_page() -> None:
    hero(
        "Single-chemical calculator",
        "Predict acute fish LC50 with the median critical-burden TPM and a visible applicability-domain assessment.",
        "TPM calculator",
    )
    comptox_lookup_panel()

    mode_col, phase_col, source_col = st.columns([1, 1, 1.55])
    mode = mode_col.selectbox(
        "Toxic mode",
        ["baseline", "less_inert", "reactive"],
        format_func=mode_label,
        help="Mode assignment is a scientific input, not an output of this app.",
    )
    phase = phase_col.selectbox("Plastic phase", phase_options(True), format_func=phase_label)
    input_source = source_col.selectbox(
        "Partition input",
        [
            "Published compound",
            "Measured log K",
            "log Kow LFER",
            "Abraham descriptors",
            "Other predicted log K",
        ],
    )

    if mode == "reactive":
        st.markdown(
            '<div class="warning-card"><b>Evidence-only mode.</b> Reactive-toxicant prediction is disabled because a partition-controlled critical burden does not represent specific reactivity.</div>',
            unsafe_allow_html=True,
        )

    records = validation_records()
    available = records[records["toxic_mode"] == mode].copy()
    observed = None
    compound_name = "Manual chemical"
    method_reference = ""
    method_documented = True
    ionization_status = "Neutral"
    mode_confidence = "Established"

    if input_source == "Published compound":
        available["selector"] = available.apply(
            lambda row: f"{row['name']} | {row['casrn']} | {row['set_label']}", axis=1
        )
        selected_label = st.selectbox("Published record", available["selector"].tolist())
        selected = available.loc[available["selector"] == selected_label].iloc[0]
        compound_name = str(selected["name"])
        mw = float(selected["molecular_weight_g_mol"])
        log_k = selected[phase_log_k_column(phase)]
        observed = float(selected["experimental_neglog_lc50_mol_l"])
        mode_confidence = "Established" if selected["set_role"] == "evaluation" else "Provisional"
        method_reference = "Target Plastic Model supporting dataset"
        st.caption(
            f"CAS RN {selected['casrn']} | {selected['chemical_class']} | source cohort: {selected['set_label']}"
        )
    else:
        identity = st.session_state.get("comptox_identity")
        default_mw = float(identity.molecular_weight) if identity and identity.molecular_weight else 100.0
        compound_name = identity.preferred_name if identity else "Manual chemical"
        mw = st.number_input(
            "Molecular weight (g/mol)", min_value=0.001, value=default_mw, step=1.0, format="%.4f"
        )
        domain_cols = st.columns(2)
        ionization_status = domain_cols[0].selectbox(
            "Chemical state at relevant pH",
            ["Neutral", "Partly ionized", "Predominantly ionized", "Unknown"],
        )
        mode_confidence = domain_cols[1].selectbox(
            "Toxic-mode confidence", ["Established", "Provisional", "Unknown"]
        )
        if input_source == "Measured log K":
            log_k = st.number_input(
                f"Measured log10 K{phase_label(phase)}-water", value=3.0, step=0.1
            )
            method_reference = st.text_input(
                "Measurement source or study ID", value="User-supplied measurement"
            )
        elif input_source == "log Kow LFER":
            st.caption(
                "Enter a documented one-parameter equation: log Kplastic-water = intercept + slope x log Kow."
            )
            lfer_cols = st.columns(3)
            log_kow = lfer_cols[0].number_input("log Kow", value=3.0, step=0.1)
            intercept = lfer_cols[1].number_input("LFER intercept", value=0.0, step=0.1)
            slope = lfer_cols[2].number_input("LFER slope", value=1.0, step=0.1)
            method_reference = st.text_input("LFER source or equation identifier")
            method_documented = bool(method_reference.strip())
            log_k = lfer_log_k(log_kow, intercept, slope)
            st.info(f"Calculated log10 K{phase_label(phase)}-water = **{log_k:.3f}**")
        elif input_source == "Abraham descriptors":
            coefficients = model_registry()["abraham_coefficients"][phase]
            st.caption("Enter E, S, A, B, V, and L solute descriptors. The equation source is shown below.")
            st.link_button("Find descriptors in the UFZ-LSER database", UFZ_LSER_URL)
            cols = st.columns(6)
            descriptor_values = {
                key: cols[index].number_input(key.upper(), value=0.0, step=0.05, key=f"descriptor_{key}")
                for index, key in enumerate(("e", "s", "a", "b", "v", "l"))
            }
            log_k = abraham_log_k(descriptor_values, coefficients)
            method_reference = model_registry()["partition_model_provenance"][phase]["source"]
            st.info(f"Calculated log10 K{phase_label(phase)}-water = **{log_k:.3f}**")
        else:
            log_k = st.number_input(
                f"Predicted log10 K{phase_label(phase)}-water", value=3.0, step=0.1
            )
            method_reference = st.text_input("Prediction method and source")
            method_documented = bool(method_reference.strip())

    burden = burden_record(mode, phase)
    result_columns = st.columns(3)
    result_columns[0].metric(
        "Median critical burden", f"{burden['critical_burden_mmol_kg']:.4g} mmol/kg"
    )
    result_columns[1].metric(
        "Partition coefficient", f"log K = {float(log_k):.3f}" if pd.notna(log_k) else "Unavailable"
    )
    result_columns[2].metric(
        "Evidence status",
        model_registry()["modes"][mode]["calculator_status"].replace("_", " ").title(),
    )

    if pd.isna(log_k):
        st.error("This published record has no usable partition coefficient for the selected phase.")
        return

    st.markdown("### Applicability domain")
    applicability_status = render_applicability(
        mode=mode,
        phase=phase,
        partition_source=input_source,
        log_k=float(log_k),
        ionization_status=ionization_status,
        mode_confidence=mode_confidence,
        method_documented=method_documented,
    )
    if mode == "reactive":
        st.caption(
            "The stored reactive critical-burden distribution remains available in Polymer atlas for source verification."
        )
        return
    if applicability_status == "outside":
        st.warning(
            "The numerical result below is an extrapolation and should not be treated as an in-domain TPM prediction."
        )

    try:
        prediction = predict_lc50(
            phase,
            mode,
            float(log_k),
            float(burden["neglog_critical_burden_mol_kg"]),
            float(mw),
        )
    except ScientificInputError as error:
        st.error(str(error))
        return

    st.markdown("### Prediction")
    left, middle, right = st.columns(3)
    left.metric(
        "Predicted pLC50", f"{prediction.predicted_neglog_lc50_mol_l:.3f}",
        help="pLC50 = -log10 of LC50 expressed in mol/L.",
    )
    middle.metric(
        "Predicted LC50",
        f"{format_scientific(mol_l_to_mmol_l(prediction.predicted_lc50_mol_l))} mmol/L",
    )
    rmse = float(burden["rmse_validation_log_unit"])
    cohort_factor = 10**rmse
    selected_error = None
    if observed is not None:
        selected_error = individual_prediction_error(observed, prediction.predicted_neglog_lc50_mol_l)
        observed_mmol_l = 10 ** (-observed) * 1000
        right.metric(
            "Selected-record difference",
            f"factor {selected_error['fold_difference']:.2f}",
            help="Chemical-specific fold difference between this prediction and the published observed LC50.",
        )
        st.markdown(
            f"**Published observation:** {observed:.3f} -log10(mol/L) ({format_scientific(observed_mmol_l)} mmol/L). "
            f"Record-specific error: {selected_error['log_error']:+.3f} log unit (predicted - observed)."
        )
    else:
        right.metric(
            "Chemical-specific error",
            "Not available",
            help="An observed LC50 is required to calculate an individual prediction error.",
        )

    with st.expander("Model validation and partition-equation provenance", expanded=False):
        st.markdown(
            f"For **{mode_label(mode)} with {phase_label(phase)}**, the independent validation cohort contains "
            f"**{int(burden['n_validation'])} chemicals** and has RMSE **{rmse:.3f} log unit** "
            f"(cohort-level factor **{cohort_factor:.2f}**)."
        )
        st.dataframe(partition_provenance_frame([phase]), width="stretch", hide_index=True)
        st.caption(
            "Historical RMSE is not a chemical-specific error or a calibrated confidence interval. "
            f"Selected partition source: {input_source}; method record: {method_reference or 'not supplied'}."
        )

    result_frame = pd.DataFrame(
        [{
            "chemical": compound_name,
            "mode": mode,
            "phase": phase,
            "molecular_weight_g_mol": mw,
            "partition_input_type": input_source,
            "partition_method_reference": method_reference,
            "log_k_phase_water": log_k,
            "ionization_status": ionization_status,
            "mode_confidence": mode_confidence,
            "applicability_status": applicability_status,
            "neglog_critical_burden_mol_kg": burden["neglog_critical_burden_mol_kg"],
            "predicted_neglog_lc50_mol_l": prediction.predicted_neglog_lc50_mol_l,
            "predicted_lc50_mmol_l": mol_l_to_mmol_l(prediction.predicted_lc50_mol_l),
            "selected_record_error_log_unit": selected_error["log_error"] if selected_error else None,
            "selected_record_fold_difference": selected_error["fold_difference"] if selected_error else None,
            "cohort_validation_n": int(burden["n_validation"]),
            "cohort_validation_rmse_log_unit": rmse,
            "cohort_validation_factor": cohort_factor,
            "model_version": __version__,
            "paper_doi": "10.1021/acs.jcim.4c00574",
        }]
    )
    st.download_button(
        "Download prediction CSV", result_frame.to_csv(index=False), "tpm_prediction.csv", "text/csv"
    )


def render_external_plastic_screen(
    *,
    bundle: CompToxEvidenceBundle,
    mode: str,
    phase: str,
    molecular_weight: float,
    log_k: float,
    median_critical_burden: float,
) -> dict[str, float] | None:
    """Calculate a transparent plastic measurement screen and optional mixture-basket row."""

    fish = bundle.fish_lc50
    chemical_burden = None
    if fish and fish.experimental_neglog_mol_l is not None:
        chemical_burden = critical_burden_from_observation(
            fish.experimental_neglog_mol_l, log_k
        )["critical_burden_mmol_kg"]

    st.markdown("### Plastic-burden risk screen")
    st.caption(
        "The paper's mode-specific median critical burden remains the primary TPM denominator. "
        "When an EPA TEST experimental reference is available, a chemical-specific burden is shown as a secondary benchmark, not as a model recalibration."
    )
    burden_cols = st.columns(3)
    burden_cols[0].metric(
        "Primary: TPM median Ccrit", f"{median_critical_burden:.4g} mmol/kg"
    )
    if chemical_burden is not None:
        burden_cols[1].metric(
            "Secondary: EPA-derived Ccrit", f"{chemical_burden:.4g} mmol/kg"
        )
        ratio = chemical_burden / median_critical_burden
        burden_cols[2].metric("EPA-derived / median Ccrit", f"{ratio:.3g} x")
    else:
        burden_cols[1].metric("Secondary: EPA-derived Ccrit", "Not available")
        burden_cols[2].metric("EPA-derived / median Ccrit", "-")

    key_suffix = f"{bundle.identity.dtxsid}_{phase}_{mode}"
    inputs = st.columns([1.1, 1, 1, 1.2])
    sample_id = inputs[0].text_input(
        "Sample ID", value="Sample-1", key=f"external_sample_{key_suffix}"
    )
    concentration = inputs[1].number_input(
        "Measured on plastic", min_value=0.0, value=1.0, format="%.6g",
        key=f"external_concentration_{key_suffix}",
    )
    unit = inputs[2].selectbox(
        "Unit",
        ["mg/kg", "ug/kg", "ng/kg", "mmol/kg", "mol/kg", "mg/g", "ug/g", "ng/g"],
        key=f"external_unit_{key_suffix}",
    )
    assessment_basis = inputs[3].selectbox(
        "Assessment factor",
        ["Freshwater - 1,000", "Marine - 10,000", "Custom"],
        key=f"external_af_basis_{key_suffix}",
    )
    if assessment_basis == "Freshwater - 1,000":
        assessment_factor = 1000.0
    elif assessment_basis == "Marine - 10,000":
        assessment_factor = 10000.0
    else:
        assessment_factor = st.number_input(
            "Custom assessment factor", min_value=0.01, value=1000.0,
            key=f"external_af_{key_suffix}",
        )
    try:
        exposure = exposure_to_mmol_kg(concentration, unit, molecular_weight)
        median_tu = toxic_unit(exposure, median_critical_burden)
        median_pnec = plastic_phase_pnec(median_critical_burden, assessment_factor)
    except ScientificInputError as error:
        st.error(str(error))
        return None

    rows = [{
        "basis": "Primary TPM median",
        "critical_burden_mmol_kg": median_critical_burden,
        "PNECplastic_eq_mmol_kg": median_pnec,
        "measured_burden_mmol_kg": exposure,
        "toxic_unit": median_tu,
        "risk_quotient": median_tu * assessment_factor,
    }]
    if chemical_burden is not None:
        chemical_tu = toxic_unit(exposure, chemical_burden)
        rows.append({
            "basis": "Secondary EPA TEST experimental benchmark",
            "critical_burden_mmol_kg": chemical_burden,
            "PNECplastic_eq_mmol_kg": plastic_phase_pnec(
                chemical_burden, assessment_factor
            ),
            "measured_burden_mmol_kg": exposure,
            "toxic_unit": chemical_tu,
            "risk_quotient": chemical_tu * assessment_factor,
        })
    risk_frame = pd.DataFrame(rows)
    st.dataframe(risk_frame, width="stretch", hide_index=True)
    primary_rq = rows[0]["risk_quotient"]
    if primary_rq >= 1:
        st.warning(
            "Primary TPM RQ is at or above 1. This is a preliminary screening flag, not a regulatory conclusion."
        )
    else:
        st.success("Primary TPM RQ is below 1 for the entered plastic concentration and AF.")

    can_add = mode == "baseline"
    if st.button(
        "Add this component to mixture basket",
        disabled=not can_add,
        key=f"add_external_basket_{key_suffix}",
    ):
        basket = list(st.session_state.get("external_mixture_basket", []))
        basket.append({
            "sample_id": sample_id,
            "chemical": bundle.identity.preferred_name,
            "casrn": bundle.identity.casrn or "",
            "dtxsid": bundle.identity.dtxsid,
            "phase": phase,
            "toxic_mode": mode,
            "molecular_weight_g_mol": molecular_weight,
            "reported_concentration": concentration,
            "reported_unit": unit,
            "exposure_mmol_kg": exposure,
            "median_critical_burden_mmol_kg": median_critical_burden,
            "experimental_critical_burden_mmol_kg": chemical_burden,
            "partition_log_k": log_k,
            "lc50_evidence": (
                "EPA TEST experimental reference"
                if chemical_burden is not None else "No experimental 96 h TEST value"
            ),
        })
        st.session_state["external_mixture_basket"] = basket
        st.success(f"Added {bundle.identity.preferred_name} to sample {sample_id}.")
    if not can_add:
        st.caption(
            "The mixture basket is restricted to baseline toxicants because concentration addition is the paper-supported mixture use."
        )
    return {
        "exposure_mmol_kg": exposure,
        "median_tu": median_tu,
        "median_rq": median_tu * assessment_factor,
        "experimental_critical_burden_mmol_kg": chemical_burden,
    }


def single_chemical_page() -> None:
    hero(
        "Optional mechanistic investigation",
        "Predict or compare fish LC50 using partitioning evidence after the direct critical-burden screen. This deeper workflow is not required for routine toxic-unit calculation from measured plastic concentrations.",
        "Secondary TPM workflow",
    )
    st.info(
        "For the paper's primary analytical shortcut—TU = measured Cplastic / median Ccrit—use Direct toxicity. "
        "This page requests partition information only because it investigates LC50 prediction or a chemical-specific experimental burden."
    )
    bundle = comptox_lookup_panel(expanded=False)

    mode_col, phase_col, source_col = st.columns([1, 1, 1.55])
    mode = mode_col.selectbox(
        "Toxic mode",
        ["baseline", "less_inert", "reactive"],
        format_func=mode_label,
        help="Mode assignment is a scientific input, not an output of CompTox or this app.",
    )
    phase = phase_col.selectbox("Plastic phase", phase_options(True), format_func=phase_label)
    input_source = source_col.selectbox(
        "Partition input",
        [
            "Published compound",
            "CompTox logKow screening",
            "Measured log K",
            "log Kow LFER",
            "Abraham descriptors",
            "Other predicted log K",
        ],
        key="single_partition_input",
    )

    if mode == "reactive":
        st.markdown(
            '<div class="warning-card"><b>Evidence-only mode.</b> Reactive-toxicant prediction is disabled because a partition-controlled critical burden does not represent specific reactivity.</div>',
            unsafe_allow_html=True,
        )

    records = validation_records()
    available = records[records["toxic_mode"] == mode].copy()
    observed = None
    observed_label = ""
    compound_name = "Manual chemical"
    method_reference = ""
    method_documented = True
    ionization_status = "Neutral"
    mode_confidence = "Established"
    external_bundle = None
    lfer_metadata = None

    if input_source == "Published compound":
        available["selector"] = available.apply(
            lambda row: f"{row['name']} | {row['casrn']} | {row['set_label']}", axis=1
        )
        selected_label = st.selectbox("Published record", available["selector"].tolist())
        selected = available.loc[available["selector"] == selected_label].iloc[0]
        compound_name = str(selected["name"])
        mw = float(selected["molecular_weight_g_mol"])
        log_k = selected[phase_log_k_column(phase)]
        observed = float(selected["experimental_neglog_lc50_mol_l"])
        observed_label = "TPM supporting-dataset observation"
        mode_confidence = "Established" if selected["set_role"] == "evaluation" else "Provisional"
        method_reference = "Target Plastic Model supporting dataset"
        st.caption(
            f"CAS RN {selected['casrn']} | {selected['chemical_class']} | source cohort: {selected['set_label']}"
        )
    else:
        identity = bundle.identity if bundle else st.session_state.get("comptox_identity")
        default_mw = float(identity.molecular_weight) if identity and identity.molecular_weight else 100.0
        compound_name = identity.preferred_name if identity else "Manual chemical"
        mw = st.number_input(
            "Molecular weight (g/mol)", min_value=0.001, value=default_mw, step=1.0, format="%.4f"
        )
        domain_cols = st.columns(2)
        ionization_status = domain_cols[0].selectbox(
            "Chemical state at relevant pH",
            ["Neutral", "Partly ionized", "Predominantly ionized", "Unknown"],
        )
        mode_confidence = domain_cols[1].selectbox(
            "Toxic-mode confidence", ["Established", "Provisional", "Unknown"]
        )
        if input_source == "CompTox logKow screening":
            if not bundle or bundle.log_kow.selected_value is None:
                st.error("Retrieve a CompTox chemical with usable logKow evidence first.")
                return
            external_bundle = bundle
            log_kow = float(bundle.log_kow.selected_value)
            lfer_metadata = model_registry()["log_kow_lfer"][phase]
            log_k = lfer_log_k(
                log_kow, lfer_metadata["intercept"], lfer_metadata["slope"]
            )
            method_reference = lfer_metadata["source"]
            fish = bundle.fish_lc50
            if fish and fish.experimental_neglog_mol_l is not None:
                observed = fish.experimental_neglog_mol_l
                observed_label = "EPA TEST experimental reference"
            status_label = (
                "Published one-parameter equation"
                if lfer_metadata["status"] == "published_screening"
                else "Dashboard-derived SI screening regression"
            )
            st.markdown(
                f"**{lfer_metadata['label']}**  \n"
                f"log K = {lfer_metadata['intercept']:.3f} + {lfer_metadata['slope']:.3f} x logKow = **{log_k:.3f}**  \n"
                f"Evidence tier: **{status_label}**; n={lfer_metadata['training_n']}."
            )
            if not (lfer_metadata["log_kow_min"] <= log_kow <= lfer_metadata["log_kow_max"]):
                st.warning(
                    f"CompTox logKow {log_kow:.3f} is outside this LFER's training range "
                    f"({lfer_metadata['log_kow_min']:.2f} to {lfer_metadata['log_kow_max']:.2f})."
                )
            st.caption(lfer_metadata["notes"])
        elif input_source == "Measured log K":
            log_k = st.number_input(
                f"Measured log10 K{phase_label(phase)}-water", value=3.0, step=0.1
            )
            method_reference = st.text_input(
                "Measurement source or study ID", value="User-supplied measurement"
            )
        elif input_source == "log Kow LFER":
            default_lfer = model_registry()["log_kow_lfer"][phase]
            st.caption(
                "Document the one-parameter equation: log Kplastic-water = intercept + slope x logKow."
            )
            lfer_cols = st.columns(3)
            default_log_kow = (
                float(bundle.log_kow.selected_value)
                if bundle and bundle.log_kow.selected_value is not None else 3.0
            )
            log_kow = lfer_cols[0].number_input("logKow", value=default_log_kow, step=0.1)
            intercept = lfer_cols[1].number_input(
                "LFER intercept", value=float(default_lfer["intercept"]), step=0.01
            )
            slope = lfer_cols[2].number_input(
                "LFER slope", value=float(default_lfer["slope"]), step=0.01
            )
            method_reference = st.text_input(
                "LFER source or equation identifier", value=default_lfer["source"]
            )
            method_documented = bool(method_reference.strip())
            log_k = lfer_log_k(log_kow, intercept, slope)
            st.info(f"Calculated log10 K{phase_label(phase)}-water = **{log_k:.3f}**")
        elif input_source == "Abraham descriptors":
            coefficients = model_registry()["abraham_coefficients"][phase]
            st.caption("Enter E, S, A, B, V, and L solute descriptors. The equation source is shown below.")
            st.link_button("Find descriptors in the UFZ-LSER database", UFZ_LSER_URL)
            cols = st.columns(6)
            descriptor_values = {
                key: cols[index].number_input(
                    key.upper(), value=0.0, step=0.05, key=f"descriptor_{key}"
                )
                for index, key in enumerate(("e", "s", "a", "b", "v", "l"))
            }
            log_k = abraham_log_k(descriptor_values, coefficients)
            method_reference = model_registry()["partition_model_provenance"][phase]["source"]
            st.info(f"Calculated log10 K{phase_label(phase)}-water = **{log_k:.3f}**")
        else:
            log_k = st.number_input(
                f"Predicted log10 K{phase_label(phase)}-water", value=3.0, step=0.1
            )
            method_reference = st.text_input("Prediction method and source")
            method_documented = bool(method_reference.strip())

    burden = burden_record(mode, phase)
    result_columns = st.columns(3)
    result_columns[0].metric(
        "Median critical burden", f"{burden['critical_burden_mmol_kg']:.4g} mmol/kg"
    )
    result_columns[1].metric(
        "Partition coefficient", f"log K = {float(log_k):.3f}" if pd.notna(log_k) else "Unavailable"
    )
    result_columns[2].metric(
        "Evidence status",
        model_registry()["modes"][mode]["calculator_status"].replace("_", " ").title(),
    )
    if pd.isna(log_k):
        st.error("No usable partition coefficient is available for the selected phase.")
        return

    st.markdown("### Applicability domain")
    applicability_status = render_applicability(
        mode=mode,
        phase=phase,
        partition_source=input_source,
        log_k=float(log_k),
        ionization_status=ionization_status,
        mode_confidence=mode_confidence,
        method_documented=method_documented,
    )
    if mode == "reactive":
        st.caption("Reactive critical-burden distributions remain available in Polymer atlas for evidence review.")
        return
    if applicability_status == "outside":
        st.warning("The numerical result below is an extrapolation and should not be treated as in-domain.")

    try:
        prediction = predict_lc50(
            phase,
            mode,
            float(log_k),
            float(burden["neglog_critical_burden_mol_kg"]),
            float(mw),
        )
    except ScientificInputError as error:
        st.error(str(error))
        return

    st.markdown("### Prediction and empirical comparison")
    left, middle, right = st.columns(3)
    left.metric(
        "TPM predicted pLC50", f"{prediction.predicted_neglog_lc50_mol_l:.3f}",
        help="pLC50 = -log10 of LC50 expressed in mol/L.",
    )
    middle.metric(
        "TPM predicted LC50",
        f"{format_scientific(mol_l_to_mmol_l(prediction.predicted_lc50_mol_l))} mmol/L",
    )
    rmse = float(burden["rmse_validation_log_unit"])
    cohort_factor = 10**rmse
    selected_error = None
    if observed is not None:
        selected_error = individual_prediction_error(observed, prediction.predicted_neglog_lc50_mol_l)
        observed_mmol_l = 10 ** (-observed) * 1000
        right.metric(
            "Chemical-specific difference",
            f"factor {selected_error['fold_difference']:.2f}",
            help="Specific difference between the TPM prediction and the displayed experimental reference.",
        )
        st.markdown(
            f"**{observed_label}:** {observed:.3f} -log10(mol/L) "
            f"({format_scientific(observed_mmol_l)} mmol/L). Prediction error: "
            f"{selected_error['log_error']:+.3f} log unit (predicted - observed)."
        )
    else:
        right.metric("Chemical-specific difference", "No experimental value")
    if external_bundle and external_bundle.fish_lc50 and external_bundle.fish_lc50.predicted_mol_l is not None:
        st.caption(
            f"EPA TEST QSAR prediction (kept separate): "
            f"{format_scientific(mol_l_to_mmol_l(external_bundle.fish_lc50.predicted_mol_l))} mmol/L; "
            f"applicability: {external_bundle.fish_lc50.applicability_conclusion or 'not reported'}."
        )

    with st.expander("Model validation and partition-equation provenance", expanded=False):
        st.markdown(
            f"For **{mode_label(mode)} with {phase_label(phase)}**, the independent validation cohort contains "
            f"**{int(burden['n_validation'])} chemicals** and has RMSE **{rmse:.3f} log unit** "
            f"(cohort-level factor **{cohort_factor:.2f}**)."
        )
        if lfer_metadata:
            st.json(lfer_metadata)
        else:
            st.dataframe(partition_provenance_frame([phase]), width="stretch", hide_index=True)
        st.caption(
            "Historical cohort RMSE is not a chemical-specific error. "
            f"Selected partition source: {input_source}; method record: {method_reference or 'not supplied'}."
        )

    risk_result = None
    if external_bundle:
        risk_result = render_external_plastic_screen(
            bundle=external_bundle,
            mode=mode,
            phase=phase,
            molecular_weight=float(mw),
            log_k=float(log_k),
            median_critical_burden=float(burden["critical_burden_mmol_kg"]),
        )

    fish = external_bundle.fish_lc50 if external_bundle else None
    result_frame = pd.DataFrame([{
        "chemical": compound_name,
        "dtxsid": external_bundle.identity.dtxsid if external_bundle else None,
        "mode": mode,
        "phase": phase,
        "molecular_weight_g_mol": mw,
        "partition_input_type": input_source,
        "partition_method_reference": method_reference,
        "log_k_phase_water": log_k,
        "ionization_status": ionization_status,
        "mode_confidence": mode_confidence,
        "applicability_status": applicability_status,
        "median_critical_burden_mmol_kg": burden["critical_burden_mmol_kg"],
        "epa_experimental_lc50_mmol_l": (
            mol_l_to_mmol_l(fish.experimental_mol_l) if fish else None
        ),
        "epa_predicted_lc50_mmol_l": (
            mol_l_to_mmol_l(fish.predicted_mol_l) if fish else None
        ),
        "experimental_critical_burden_mmol_kg": (
            risk_result["experimental_critical_burden_mmol_kg"] if risk_result else None
        ),
        "predicted_neglog_lc50_mol_l": prediction.predicted_neglog_lc50_mol_l,
        "predicted_lc50_mmol_l": mol_l_to_mmol_l(prediction.predicted_lc50_mol_l),
        "chemical_specific_error_log_unit": selected_error["log_error"] if selected_error else None,
        "chemical_specific_fold_difference": selected_error["fold_difference"] if selected_error else None,
        "cohort_validation_n": int(burden["n_validation"]),
        "cohort_validation_rmse_log_unit": rmse,
        "model_version": __version__,
        "paper_doi": "10.1021/acs.jcim.4c00574",
    }])
    st.download_button(
        "Download integrated assessment CSV",
        result_frame.to_csv(index=False),
        "tpm_comptox_assessment.csv",
        "text/csv",
    )


def _legacy_mixture_page() -> None:
    hero(
        "Mixture toxic-unit screen",
        "Convert measured plastic-phase concentrations to a common molar basis, calculate component toxic units, and inspect mixture contribution transparently.",
        "Conditional concentration addition",
    )
    mode_col, phase_col, factor_col = st.columns(3)
    mode = mode_col.selectbox(
        "Toxic mode",
        ["baseline"],
        format_func=mode_label,
        key="mixture_mode",
        disabled=True,
        help="Equations 9–11 in the paper apply concentration addition to baseline toxicants.",
    )
    phase = phase_col.selectbox("Validated plastic phase", phase_options(True), format_func=phase_label, key="mixture_phase")
    assessment_basis = factor_col.selectbox(
        "Assessment-factor basis",
        ["Freshwater — AF 1,000", "Marine — AF 10,000", "Custom"],
        help="The paper cites typical REACH screening factors of 1,000 for freshwater and 10,000 for marine conditions.",
    )
    if assessment_basis == "Freshwater — AF 1,000":
        assessment_factor = 1000.0
        assessment_scenario = "freshwater"
    elif assessment_basis == "Marine — AF 10,000":
        assessment_factor = 10000.0
        assessment_scenario = "marine"
    else:
        assessment_factor = factor_col.number_input(
            "Custom assessment factor",
            min_value=0.01,
            value=1000.0,
            step=10.0,
            help="Use a custom value only with a documented regulatory or scientific justification.",
        )
        assessment_scenario = "custom"

    burden = burden_record(mode, phase)
    critical_burden = float(burden["critical_burden_mmol_kg"])
    pnec_plastic = plastic_phase_pnec(critical_burden, assessment_factor)
    st.markdown("### PNEC basis")
    basis_cols = st.columns(3)
    basis_cols[0].metric("Median critical plastic burden", f"{critical_burden:.5g} mmol/kg")
    basis_cols[1].metric("Assessment factor (AF)", f"{assessment_factor:,.0f}")
    basis_cols[2].metric(
        "Plastic-phase PNEC equivalent",
        f"{pnec_plastic:.5g} mmol/kg",
        help="Derived for this screening workflow as Ccrit,plastic / AF.",
    )
    st.markdown(
        '<div class="formula">ΣTU = Σ(C<sub>plastic,i</sub> / C<sub>plastic</sub><sup>crit</sup>) &nbsp;&nbsp;·&nbsp;&nbsp; '
        'PNEC<sub>plastic,eq</sub> = C<sub>plastic</sub><sup>crit</sup> / AF &nbsp;&nbsp;·&nbsp;&nbsp; '
        'RQ = ΣTU × AF</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "The displayed PNEC is a plastic-phase screening equivalent in mmol/kg plastic, not a measured water-column PNEC. "
        "It is the threshold mathematically consistent with equation 11 for the selected critical burden and AF."
    )
    with st.expander("Assessment-factor interpretation and cited basis", expanded=False):
        st.markdown(
            """
            - **Freshwater:** AF 1,000, the paper's cited typical screening value when deriving a PNEC from acute toxicity evidence.
            - **Marine:** AF 10,000, the paper's cited typical marine screening value.
            - **Custom:** use when the available evidence and applicable framework justify another factor.

            Assessment factors are conservative uncertainty-management choices, not measured chemical properties. Chapman et al. emphasize that their magnitude also reflects risk-management policy and data adequacy.

            **References:** ECHA Chapter R.10 (2008); Chapman, Fairbrother & Brown (1998), DOI 10.1002/etc.5620170112; Backhaus & Faust (2012), DOI 10.1021/es2034125; Faure et al. (2015), DOI 10.1071/EN14218.
            """
        )
    uploaded = st.file_uploader("Upload mixture CSV (optional)", type=["csv"])
    template = pd.DataFrame(
        [
            {"chemical": "Component A", "casrn": "", "molecular_weight_g_mol": 100.0, "concentration": 1.0, "unit": "mg/kg"},
            {"chemical": "Component B", "casrn": "", "molecular_weight_g_mol": 150.0, "concentration": 0.5, "unit": "mg/kg"},
        ]
    )
    if uploaded is not None:
        try:
            template = pd.read_csv(uploaded)
        except Exception as error:
            st.error(f"The CSV could not be read: {error}")
    edited = st.data_editor(
        template,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "molecular_weight_g_mol": st.column_config.NumberColumn("MW (g/mol)", min_value=0.001, format="%.4f"),
            "concentration": st.column_config.NumberColumn("Concentration", min_value=0.0, format="%.6g"),
            "unit": st.column_config.SelectboxColumn("Unit", options=["mmol/kg", "mol/kg", "mg/kg", "ug/kg", "ng/kg", "mg/g", "ug/g", "ng/g"], required=True),
        },
        key="mixture_editor",
    )
    equilibrium = st.checkbox(
        "I confirm that concentration addition is appropriate: all components are baseline toxicants, values refer to the same plastic phase, and an equilibrium or defensibly comparable state is represented."
    )
    if not equilibrium:
        st.info(
            f"Plastic-phase PNEC equivalent: **{pnec_plastic:.5g} mmol/kg**. "
            "Confirm the scientific compatibility statement to calculate ΣTU and RQ."
        )
        return
    required = {"chemical", "molecular_weight_g_mol", "concentration", "unit"}
    missing = required - set(edited.columns)
    if missing:
        st.error(f"Missing required columns: {', '.join(sorted(missing))}")
        return
    output = edited.copy()
    errors: list[str] = []
    converted: list[float] = []
    tus: list[float] = []
    for index, row in output.iterrows():
        try:
            mmol = exposure_to_mmol_kg(row["concentration"], row["unit"], row["molecular_weight_g_mol"])
            converted.append(mmol)
            tus.append(toxic_unit(mmol, burden["critical_burden_mmol_kg"]))
        except ScientificInputError as error:
            converted.append(math.nan)
            tus.append(math.nan)
            errors.append(f"Row {index + 1}: {error}")
    if errors:
        st.error("\n".join(errors))
        return
    output["exposure_mmol_kg"] = converted
    output["critical_burden_mmol_kg"] = critical_burden
    output["toxic_unit"] = tus
    output["rq_contribution"] = output["toxic_unit"] * assessment_factor
    summary = summarize_mixture(tus, assessment_factor, critical_burden)
    total_exposure = sum(converted)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total plastic burden", f"{total_exposure:.4g} mmol/kg")
    col2.metric("Σ toxic units", f"{summary['sum_tu']:.4g}")
    col3.metric("PNECplastic,eq", f"{summary['pnec_plastic_mmol_kg']:.4g} mmol/kg")
    col4.metric(
        "Risk quotient (RQ)",
        f"{summary['risk_quotient']:.4g}",
        help="Equation 11: RQ = ΣTU × assessment factor.",
    )
    if summary["risk_quotient"] < 1:
        st.success(
            "RQ < 1: the summed plastic-phase burden is below the derived screening PNEC equivalent for the selected AF."
        )
    else:
        st.warning(
            "RQ ≥ 1: the summed plastic-phase burden equals or exceeds the derived screening PNEC equivalent. "
            "This is a preliminary screening flag, not a regulatory conclusion."
        )
    chart = output.sort_values("toxic_unit", ascending=True)
    figure = px.bar(chart, x="toxic_unit", y="chemical", orientation="h", color="toxic_unit", color_continuous_scale="Tealgrn", title="Component contributions to ΣTU")
    figure.update_layout(height=max(340, 42 * len(output)), margin=dict(l=10, r=10, t=55, b=10), plot_bgcolor="white")
    st.plotly_chart(figure, width="stretch")
    st.dataframe(output, width="stretch", hide_index=True)
    output["assessment_scenario"] = assessment_scenario
    output["assessment_factor"] = assessment_factor
    output["pnec_plastic_equivalent_mmol_kg"] = summary["pnec_plastic_mmol_kg"]
    output["mixture_sum_tu"] = summary["sum_tu"]
    output["mixture_risk_quotient"] = summary["risk_quotient"]
    st.download_button("Download mixture results CSV", output.to_csv(index=False), "tpm_mixture_results.csv", "text/csv")


def render_direct_component_screen(
    *, phase: str, assessment_factor: float, median_critical_burden: float
) -> None:
    """Primary TPM screen from a measured plastic concentration without LC50 or K."""

    st.markdown("### Quick direct toxic-unit screen")
    st.markdown(
        """
        <div class="evidence-card"><b>Required:</b> measured plastic-associated concentration, validated plastic phase,
        and a defensible baseline-toxicant assignment.<br>
        <b>Not required:</b> chemical-specific fish LC50 or plastic-water partition coefficient.
        Molecular weight is needed only when converting a mass-based concentration to mmol/kg.</div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("Optional CompTox identity and molecular-weight lookup", expanded=False):
        st.caption(
            "This lookup requests identity information only. It does not request LC50 or partition data and does not change the median critical burden."
        )
        query = st.text_input(
            "Name, CAS RN, DTXSID, or InChIKey", key="direct_comptox_query"
        )
        key = api_key()
        if st.button(
            "Retrieve identity and molecular weight",
            disabled=not key or not query,
            key="direct_identity_button",
        ):
            try:
                with st.spinner("Resolving exact CompTox identity..."):
                    identity = CompToxClient(key).exact_identity(query)
                st.session_state["direct_comptox_identity"] = identity
                st.session_state["direct_component_name"] = identity.preferred_name
                if identity.molecular_weight is not None:
                    st.session_state["direct_component_mw"] = float(identity.molecular_weight)
            except CompToxError as error:
                st.error(str(error))
        identity = st.session_state.get("direct_comptox_identity")
        if identity:
            identity_cols = st.columns(4)
            identity_cols[0].metric("Name", identity.preferred_name)
            identity_cols[1].metric("CAS RN", identity.casrn or "-")
            identity_cols[2].metric("DTXSID", identity.dtxsid or "-")
            identity_cols[3].metric(
                "Molecular weight",
                f"{identity.molecular_weight:.3f} g/mol" if identity.molecular_weight else "-",
            )
        elif not key:
            st.info("No API key detected. Enter the chemical name and molecular weight manually below.")

    identity = st.session_state.get("direct_comptox_identity")
    input_cols = st.columns([1.2, 1, 1, 1])
    sample_id = input_cols[0].text_input(
        "Sample ID", value="Sample-1", key="direct_component_sample"
    )
    chemical_name = input_cols[1].text_input(
        "Chemical",
        value=identity.preferred_name if identity else "Measured chemical",
        key="direct_component_name",
    )
    concentration = input_cols[2].number_input(
        "Measured on plastic",
        min_value=0.0,
        value=1.0,
        format="%.6g",
        key="direct_component_concentration",
    )
    unit = input_cols[3].selectbox(
        "Unit",
        ["mmol/kg", "mol/kg", "mg/kg", "ug/kg", "ng/kg", "mg/g", "ug/g", "ng/g"],
        key="direct_component_unit",
    )
    details = st.columns([1, 1.2, 2])
    default_mw = float(identity.molecular_weight) if identity and identity.molecular_weight else 0.0
    molecular_weight = details[0].number_input(
        "Molecular weight (g/mol)",
        min_value=0.0,
        value=default_mw,
        step=1.0,
        format="%.4f",
        key="direct_component_mw",
        help="Not used for mmol/kg or mol/kg inputs.",
    )
    mode_confidence = details[1].selectbox(
        "Baseline-mode confidence",
        ["Established", "Provisional", "Unknown"],
        key="direct_component_mode_confidence",
    )
    details[2].caption(
        f"Selected endpoint constant: baseline {phase_label(phase)} median critical burden = "
        f"{median_critical_burden:.5g} mmol/kg plastic."
    )

    try:
        exposure = exposure_to_mmol_kg(concentration, unit, molecular_weight)
        component_tu = toxic_unit(exposure, median_critical_burden)
        component_pnec = plastic_phase_pnec(median_critical_burden, assessment_factor)
        component_rq = component_tu * assessment_factor
    except ScientificInputError as error:
        st.error(str(error))
        return

    results = st.columns(4)
    results[0].metric("Normalized Cplastic", f"{exposure:.4g} mmol/kg")
    results[1].metric("Toxic unit", f"{component_tu:.4g}")
    results[2].metric("PNECplastic,eq", f"{component_pnec:.4g} mmol/kg")
    results[3].metric("Risk quotient", f"{component_rq:.4g}")
    if mode_confidence != "Established":
        st.warning(
            "The arithmetic is shown, but the result should not be combined into a mixture until the baseline-toxicant assignment is established."
        )
    if st.button(
        "Add direct result to mixture basket",
        disabled=mode_confidence != "Established",
        key="add_direct_component",
    ):
        basket = list(st.session_state.get("external_mixture_basket", []))
        basket.append({
            "sample_id": sample_id,
            "chemical": chemical_name,
            "casrn": identity.casrn if identity and identity.casrn else "",
            "dtxsid": identity.dtxsid if identity else "",
            "phase": phase,
            "toxic_mode": "baseline",
            "molecular_weight_g_mol": molecular_weight if molecular_weight > 0 else None,
            "reported_concentration": concentration,
            "reported_unit": unit,
            "exposure_mmol_kg": exposure,
            "median_critical_burden_mmol_kg": median_critical_burden,
            "experimental_critical_burden_mmol_kg": None,
            "partition_log_k": None,
            "lc50_evidence": "Not required - direct median critical-burden pathway",
        })
        st.session_state["external_mixture_basket"] = basket
        st.success(f"Added {chemical_name} to {sample_id} using the direct TPM pathway.")


def render_external_mixture_basket(
    *, phase: str, assessment_factor: float, median_critical_burden: float
) -> None:
    """Summarize direct and evidence-assisted components added to the basket."""

    basket = list(st.session_state.get("external_mixture_basket", []))
    if not basket:
        with st.expander("Direct critical-burden mixture basket", expanded=False):
            st.caption(
                "Add measured chemicals with the quick direct screen above. The primary mixture calculation needs no LC50 or partition coefficient."
            )
        return

    st.markdown("### Direct critical-burden mixture basket")
    frame = pd.DataFrame(basket)
    compatible = frame[
        (frame["phase"] == phase) & (frame["toxic_mode"] == "baseline")
    ].copy()
    excluded = len(frame) - len(compatible)
    if excluded:
        st.warning(
            f"{excluded} basket row(s) are not shown because they do not match baseline mode and the selected {phase_label(phase)} phase."
        )
    if compatible.empty:
        st.info("No basket components match the current baseline/phase selection.")
        if st.button("Clear mixture basket", key="clear_external_basket_empty"):
            st.session_state["external_mixture_basket"] = []
            st.rerun()
        return

    compatible["primary_toxic_unit"] = (
        compatible["exposure_mmol_kg"] / median_critical_burden
    )
    compatible["primary_rq_contribution"] = (
        compatible["primary_toxic_unit"] * assessment_factor
    )
    compatible["secondary_toxic_unit"] = compatible.apply(
        lambda row: (
            row["exposure_mmol_kg"] / row["experimental_critical_burden_mmol_kg"]
            if pd.notna(row["experimental_critical_burden_mmol_kg"])
            and row["experimental_critical_burden_mmol_kg"] > 0
            else math.nan
        ),
        axis=1,
    )
    compatible["secondary_rq_contribution"] = (
        compatible["secondary_toxic_unit"] * assessment_factor
    )
    st.dataframe(
        compatible[
            [
                "sample_id",
                "chemical",
                "casrn",
                "dtxsid",
                "reported_concentration",
                "reported_unit",
                "exposure_mmol_kg",
                "median_critical_burden_mmol_kg",
                "experimental_critical_burden_mmol_kg",
                "primary_toxic_unit",
                "secondary_toxic_unit",
            ]
        ],
        width="stretch",
        hide_index=True,
    )
    confirmed = st.checkbox(
        "I confirm these basket components are baseline toxicants measured on the same selected plastic phase and are compatible for concentration addition.",
        key="external_basket_compatibility",
    )
    if confirmed:
        summaries = []
        for sample_id, group in compatible.groupby("sample_id", dropna=False):
            complete_external = group["secondary_toxic_unit"].notna().all()
            primary_sum_tu = float(group["primary_toxic_unit"].sum())
            summaries.append({
                "sample_id": sample_id,
                "components": len(group),
                "primary_TPM_sum_TU": primary_sum_tu,
                "primary_TPM_RQ": primary_sum_tu * assessment_factor,
                "primary_PNECplastic_eq_mmol_kg": plastic_phase_pnec(
                    median_critical_burden, assessment_factor
                ),
                "secondary_EPA_sum_TU": (
                    float(group["secondary_toxic_unit"].sum()) if complete_external else math.nan
                ),
                "secondary_EPA_RQ": (
                    float(group["secondary_toxic_unit"].sum()) * assessment_factor
                    if complete_external else math.nan
                ),
                "secondary_route_complete": complete_external,
            })
        summary_frame = pd.DataFrame(summaries)
        st.dataframe(summary_frame, width="stretch", hide_index=True)
        st.caption(
            "Primary RQ uses the paper's median baseline critical burden for every component. "
            "The optional secondary RQ is reported only when every component also has an EPA experimental reference and a chemical-specific partition estimate."
        )
        st.download_button(
            "Download direct mixture CSV",
            compatible.to_csv(index=False),
            "tpm_comptox_mixture_components.csv",
            "text/csv",
        )
    controls = st.columns([1, 4])
    if controls[0].button("Clear basket", key="clear_external_basket"):
        st.session_state["external_mixture_basket"] = []
        st.rerun()
    controls[1].caption(
        "The basket is session-only; the API key and raw API responses are not written to exports."
    )


def mixture_page() -> None:
    hero(
        "Direct toxicity from plastic measurements",
        "Use the median critical plastic burden as a new material- and mode-specific endpoint: calculate TU directly from measured sampler or environmental-plastic concentrations, without chemical-specific LC50 or Kplastic-water inputs.",
        "Primary TPM workflow",
    )
    st.markdown(
        """
        <div class="evidence-card"><b>The central analytical shortcut</b><br>
        Once the toxic mode and plastic phase are appropriate, the median critical plastic burden is the denominator.
        Measure C<sub>plastic</sub>, normalize it to mmol/kg plastic, divide by C<sub>plastic</sub><sup>crit</sup>, and add
        component toxic units for a compatible baseline-toxicant mixture.</div>
        """,
        unsafe_allow_html=True,
    )
    mode_col, phase_col, factor_col = st.columns(3)
    mode = mode_col.selectbox(
        "Toxic mode",
        ["baseline"],
        format_func=mode_label,
        key="mixture_mode_v11",
        disabled=True,
        help="The TPM mixture equations apply concentration addition to baseline toxicants.",
    )
    phase = phase_col.selectbox(
        "Validated plastic phase", phase_options(True), format_func=phase_label, key="mixture_phase_v11"
    )
    assessment_basis = factor_col.selectbox(
        "Assessment-factor basis",
        ["Freshwater - AF 1,000", "Marine - AF 10,000", "Custom"],
        help="The paper discusses typical REACH screening factors of 1,000 and 10,000.",
    )
    if assessment_basis == "Freshwater - AF 1,000":
        assessment_factor = 1000.0
        assessment_scenario = "freshwater"
    elif assessment_basis == "Marine - AF 10,000":
        assessment_factor = 10000.0
        assessment_scenario = "marine"
    else:
        assessment_factor = factor_col.number_input(
            "Custom assessment factor", min_value=0.01, value=1000.0, step=10.0
        )
        assessment_scenario = "custom"

    burden = burden_record(mode, phase)
    critical_burden = float(burden["critical_burden_mmol_kg"])
    pnec_plastic = plastic_phase_pnec(critical_burden, assessment_factor)
    basis_cols = st.columns(3)
    basis_cols[0].metric("Median critical plastic burden", f"{critical_burden:.5g} mmol/kg")
    basis_cols[1].metric("Assessment factor (AF)", f"{assessment_factor:,.0f}")
    basis_cols[2].metric("PNECplastic,eq", f"{pnec_plastic:.5g} mmol/kg")
    st.markdown(
        '<div class="formula">ΣTU = Σ(C<sub>plastic,i</sub> / C<sub>plastic</sub><sup>crit</sup>) &nbsp;·&nbsp; '
        'PNEC<sub>plastic,eq</sub> = C<sub>plastic</sub><sup>crit</sup> / AF &nbsp;·&nbsp; '
        'RQ = ΣTU × AF</div>',
        unsafe_allow_html=True,
    )
    st.caption(
        "PNECplastic,eq is the plastic-phase screening equivalent used by this TPM workflow. "
        "Neither LC50 nor Kplastic-water enters this direct calculation."
    )
    with st.expander("Critical plastic burden endpoint table", expanded=False):
        endpoint_table = critical_burdens()
        endpoint_table = endpoint_table[
            endpoint_table["phase"].isin(phase_options(True))
            & endpoint_table["toxic_mode"].isin(["baseline", "less_inert"])
        ].copy()
        endpoint_table["plastic_phase"] = endpoint_table["phase"].map(phase_label)
        endpoint_table["mode"] = endpoint_table["toxic_mode"].map(mode_label)
        st.dataframe(
            endpoint_table[
                [
                    "mode",
                    "plastic_phase",
                    "critical_burden_mmol_kg",
                    "n_evaluation",
                    "n_validation",
                    "rmse_validation_log_unit",
                    "calculator_status",
                ]
            ],
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "These phase- and mode-specific medians are the reusable TPM endpoints. The mixture implementation remains restricted to compatible baseline toxicants; less-inert values are shown for endpoint transparency and single-component interpretation."
        )
        st.download_button(
            "Download critical-burden endpoints",
            endpoint_table.to_csv(index=False),
            "tpm_critical_burden_endpoints.csv",
            "text/csv",
        )
    render_direct_component_screen(
        phase=phase,
        assessment_factor=assessment_factor,
        median_critical_burden=critical_burden,
    )
    render_external_mixture_basket(
        phase=phase,
        assessment_factor=assessment_factor,
        median_critical_burden=critical_burden,
    )
    with st.expander("Scientific compatibility and assessment-factor basis"):
        st.markdown(
            "Concentration addition requires baseline toxicants, a common polymer phase, compatible concentration data, "
            "and a scientifically defensible interpretation of the measured plastic burden. Assessment factors are "
            "screening choices rather than chemical properties."
        )
        st.markdown(
            "**References:** ECHA Chapter R.10 (2008); Chapman, Fairbrother & Brown (1998); "
            "Backhaus & Faust (2012); Faure et al. (2015)."
        )

    uploaded = st.file_uploader("Upload field-mixture CSV (optional)", type=["csv"], key="field_mixture_upload")
    template = pd.DataFrame(
        [
            {
                "sample_id": "Site-A-01",
                "site": "Site A",
                "sample_date": "2026-08-08",
                "replicate": "R1",
                "chemical": "Component A",
                "casrn": "",
                "molecular_weight_g_mol": 100.0,
                "concentration": 1.0,
                "unit": "mg/kg",
                "qualifier": "=",
                "detection_limit": 0.1,
                "mode_confidence": "Established",
                "result_source": "Measured",
            },
            {
                "sample_id": "Site-A-01",
                "site": "Site A",
                "sample_date": "2026-08-08",
                "replicate": "R1",
                "chemical": "Component B",
                "casrn": "",
                "molecular_weight_g_mol": 150.0,
                "concentration": 0.5,
                "unit": "mg/kg",
                "qualifier": "=",
                "detection_limit": 0.05,
                "mode_confidence": "Established",
                "result_source": "Measured",
            },
        ]
    )
    if uploaded is not None:
        try:
            template = pd.read_csv(uploaded)
        except Exception as error:
            st.error(f"The CSV could not be read: {error}")

    nondetect_method = st.selectbox(
        "Nondetect substitution",
        ["Zero", "Half detection limit", "Detection limit"],
        help="The selected substitution is recorded in every exported result.",
    )
    edited = st.data_editor(
        template,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "molecular_weight_g_mol": st.column_config.NumberColumn(
                "MW (g/mol)",
                min_value=0.0,
                help="Required only for mass-based concentration units; ignored for mmol/kg and mol/kg.",
            ),
            "concentration": st.column_config.NumberColumn("Reported concentration", min_value=0.0),
            "detection_limit": st.column_config.NumberColumn("Detection limit", min_value=0.0),
            "unit": st.column_config.SelectboxColumn(
                "Unit",
                options=["mmol/kg", "mol/kg", "mg/kg", "ug/kg", "ng/kg", "mg/g", "ug/g", "ng/g"],
                required=True,
            ),
            "qualifier": st.column_config.SelectboxColumn("Qualifier", options=["=", "<", "ND"], required=True),
            "mode_confidence": st.column_config.SelectboxColumn(
                "Baseline-mode confidence", options=["Established", "Provisional", "Unknown"], required=True
            ),
            "result_source": st.column_config.SelectboxColumn(
                "Result source", options=["Measured", "Estimated", "Unknown"], required=True
            ),
        },
        key="field_mixture_editor",
    )
    st.caption(
        "The field processor deliberately does not require film thickness or kinetic parameters. "
        "Molecular weight is used only to convert mass-based measurements; it is not required for mmol/kg or mol/kg inputs. "
        "Add only metadata that are available and appropriate for the study."
    )

    compatibility = st.checkbox(
        "I confirm that the components are treated as baseline toxicants, refer to the same selected plastic phase, and are scientifically compatible for concentration addition.",
        key="field_mixture_compatibility",
    )
    if not compatibility:
        st.info(
            f"PNECplastic,eq: **{pnec_plastic:.5g} mmol/kg**. Confirm compatibility to calculate ΣTU and RQ."
        )
        return

    required = {
        "sample_id",
        "chemical",
        "concentration",
        "unit",
        "qualifier",
    }
    missing = required - set(edited.columns)
    if missing:
        st.error(f"Missing required columns: {', '.join(sorted(missing))}")
        return

    output = edited.copy()
    errors: list[str] = []
    effective_values: list[float] = []
    converted: list[float] = []
    tus: list[float] = []
    for index, row in output.iterrows():
        try:
            detection_limit = row.get("detection_limit")
            if pd.isna(detection_limit):
                detection_limit = None
            effective = substitute_censored_value(
                row["concentration"], row["qualifier"], detection_limit, nondetect_method
            )
            mmol = exposure_to_mmol_kg(
                effective, row["unit"], row.get("molecular_weight_g_mol", math.nan)
            )
            effective_values.append(effective)
            converted.append(mmol)
            tus.append(toxic_unit(mmol, critical_burden))
        except ScientificInputError as error:
            effective_values.append(math.nan)
            converted.append(math.nan)
            tus.append(math.nan)
            errors.append(f"Row {index + 1}: {error}")
    if errors:
        st.error("\n".join(errors))
        return

    output["effective_concentration"] = effective_values
    output["nondetect_method"] = nondetect_method
    output["exposure_mmol_kg"] = converted
    output["critical_burden_mmol_kg"] = critical_burden
    output["toxic_unit"] = tus
    output["rq_contribution"] = output["toxic_unit"] * assessment_factor
    output["assessment_scenario"] = assessment_scenario
    output["assessment_factor"] = assessment_factor
    output["pnec_plastic_equivalent_mmol_kg"] = pnec_plastic

    summaries = []
    for sample_id, group in output.groupby("sample_id", dropna=False):
        summary = summarize_mixture(group["toxic_unit"].tolist(), assessment_factor, critical_burden)
        summaries.append(
            {
                "sample_id": sample_id,
                "site": group["site"].iloc[0] if "site" in group else "",
                "sample_date": group["sample_date"].iloc[0] if "sample_date" in group else "",
                "replicate": group["replicate"].iloc[0] if "replicate" in group else "",
                "components": len(group),
                "total_burden_mmol_kg": group["exposure_mmol_kg"].sum(),
                "sum_tu": summary["sum_tu"],
                "PNECplastic_eq_mmol_kg": summary["pnec_plastic_mmol_kg"],
                "RQ": summary["risk_quotient"],
            }
        )
    summary_frame = pd.DataFrame(summaries).sort_values("RQ", ascending=False)

    st.markdown("### Sample-level results")
    st.dataframe(summary_frame, width="stretch", hide_index=True)
    if (summary_frame["RQ"] >= 1).any():
        st.warning("One or more samples have RQ ≥ 1 in this preliminary TPM screening workflow.")
    else:
        st.success("All calculated sample RQ values are below 1 in this preliminary TPM screening workflow.")

    chart = output.copy()
    chart["component"] = chart["sample_id"].astype(str) + " | " + chart["chemical"].astype(str)
    figure = px.bar(
        chart.sort_values("toxic_unit"),
        x="toxic_unit",
        y="component",
        orientation="h",
        color="chemical",
        title="Component contributions to sample ΣTU",
    )
    figure.update_layout(height=max(380, 38 * len(chart)), margin=dict(l=10, r=10, t=55, b=10))
    st.plotly_chart(figure, width="stretch")
    with st.expander("Component-level audit table"):
        st.dataframe(output, width="stretch", hide_index=True)
    downloads = st.columns(2)
    downloads[0].download_button(
        "Download component results CSV", output.to_csv(index=False), "tpm_field_mixture_components.csv", "text/csv"
    )
    downloads[1].download_button(
        "Download sample summary CSV", summary_frame.to_csv(index=False), "tpm_field_mixture_summary.csv", "text/csv"
    )


def atlas_page() -> None:
    hero(
        "Polymer and critical-burden atlas",
        "Explore mode-specific critical burdens, validation error, and the boundary between validated and exploratory plastic phases.",
        "Evidence landscape",
    )
    burdens = critical_burdens().copy()
    mode = st.radio("Toxic mode", ["baseline", "less_inert", "reactive"], format_func=mode_label, horizontal=True)
    selected = burdens[burdens["toxic_mode"] == mode].copy()
    selected["phase_label"] = selected["phase"].map(phase_label)
    selected["status"] = selected["calculator_status"].str.replace("_", " ").str.title()
    figure = px.bar(
        selected,
        x="phase_label",
        y="critical_burden_mmol_kg",
        color="evidence_tier",
        log_y=True,
        text="critical_burden_mmol_kg",
        color_discrete_map={"paper_validated": "#0b6e69", "reference": "#79b6a6", "out_of_domain": "#ef9f32"},
        labels={"phase_label": "Phase", "critical_burden_mmol_kg": "Median critical burden (mmol/kg)", "evidence_tier": "Evidence tier"},
        title=f"{mode_label(mode)} — median critical burden on a logarithmic scale",
    )
    figure.update_traces(texttemplate="%{text:.3g}", textposition="outside")
    figure.update_layout(height=470, margin=dict(l=10, r=10, t=55, b=10), plot_bgcolor="white")
    st.plotly_chart(figure, width="stretch")
    display_columns = ["phase", "critical_burden_mmol_kg", "n_evaluation", "rmse_evaluation_log_unit", "n_validation", "rmse_validation_log_unit", "status"]
    st.dataframe(selected[display_columns], width="stretch", hide_index=True)

    st.markdown("### Critical-burden distribution explorer")
    explorer_cols = st.columns([1, 2])
    explorer_phase = explorer_cols[0].selectbox(
        "Distribution phase", phase_options(True), format_func=phase_label, key="burden_distribution_phase"
    )
    development = validation_records()
    development = development[
        (development["toxic_mode"] == mode) & (development["set_role"] == "evaluation")
    ].copy()
    k_column = phase_log_k_column(explorer_phase)
    development = development.dropna(
        subset=["experimental_neglog_lc50_mol_l", k_column]
    ).copy()
    available_classes = sorted(development["chemical_class"].dropna().unique())
    selected_classes = explorer_cols[1].multiselect(
        "Chemical classes", available_classes, placeholder="All classes"
    )
    if selected_classes:
        development = development[development["chemical_class"].isin(selected_classes)].copy()
    burdens_calculated = development.apply(
        lambda row: critical_burden_from_observation(
            row["experimental_neglog_lc50_mol_l"], row[k_column]
        ),
        axis=1,
        result_type="expand",
    )
    development = pd.concat([development.reset_index(drop=True), burdens_calculated.reset_index(drop=True)], axis=1)
    cohort_median = float(burden_record(mode, explorer_phase)["critical_burden_mmol_kg"])
    q05, q25, q50, q75, q95 = development["critical_burden_mmol_kg"].quantile(
        [0.05, 0.25, 0.50, 0.75, 0.95]
    )
    stat_cols = st.columns(6)
    stat_cols[0].metric("n", len(development))
    stat_cols[1].metric("5th percentile", f"{q05:.3g}")
    stat_cols[2].metric("Q1", f"{q25:.3g}")
    stat_cols[3].metric("Median", f"{q50:.3g}")
    stat_cols[4].metric("Q3", f"{q75:.3g}")
    stat_cols[5].metric("95th percentile", f"{q95:.3g}")

    burden_figure = px.strip(
        development,
        x="critical_burden_mmol_kg",
        y="chemical_class",
        color="chemical_class",
        log_x=True,
        hover_data=["name", "casrn", "experimental_neglog_lc50_mol_l"],
        labels={
            "critical_burden_mmol_kg": "Chemical-level calculated burden (mmol/kg)",
            "chemical_class": "Chemical class",
        },
        title=f"{mode_label(mode)} burden distribution for {phase_label(explorer_phase)}",
    )
    burden_figure.add_vline(
        x=cohort_median,
        line_dash="dash",
        line_color="#0f3435",
        annotation_text="TPM cohort median",
    )
    burden_figure.update_layout(
        height=max(430, 30 * max(1, development["chemical_class"].nunique())),
        showlegend=False,
        margin=dict(l=10, r=10, t=55, b=10),
    )
    st.plotly_chart(burden_figure, width="stretch")
    iqr = q75 - q25
    outliers = development[
        (development["critical_burden_mmol_kg"] < max(0.0, q25 - 1.5 * iqr))
        | (development["critical_burden_mmol_kg"] > q75 + 1.5 * iqr)
    ][["name", "casrn", "chemical_class", "critical_burden_mmol_kg"]].sort_values(
        "critical_burden_mmol_kg"
    )
    with st.expander(f"Inspect {len(outliers)} IQR-flagged records"):
        st.dataframe(outliers, width="stretch", hide_index=True)
    st.caption(
        "Each point is LC50_i × Kplastic-water,i for one evaluation chemical. "
        "The dashed line is the cohort median used by the operational TPM; it is not a separate chemical-specific threshold."
    )
    st.download_button(
        "Download filtered burden distribution",
        development.to_csv(index=False),
        "tpm_critical_burden_distribution.csv",
        "text/csv",
    )
    if mode == "reactive":
        st.markdown(
            '<div class="warning-card"><b>Unit and domain note.</b> The supplementary workbook stores these burdens as −log₁₀(mol/kg). Converting those values gives the displayed mmol/kg values. Reactive predictions remain disabled because the mechanism is not adequately represented by equilibrium partitioning.</div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Exploratory other-plastic evidence")
    exploratory = other_plastics()
    counts = exploratory.groupby("plastic", as_index=False).agg(records=("name", "size"), median_neglog_burden=("neglog_critical_burden_mol_kg", "median"))
    st.dataframe(counts, width="stretch", hide_index=True)
    with st.expander("Browse Table S6 records"):
        plastic = st.selectbox("Exploratory plastic", sorted(exploratory["plastic"].unique()))
        st.dataframe(exploratory[exploratory["plastic"] == plastic], width="stretch", hide_index=True)
    st.warning(
        "Hypothesis-generating evidence only: HDPE, polypropylene, polystyrene, PVC, and UHMWPE have sparse, "
        "chemically uneven datasets and are intentionally excluded from the calculator. Their displayed burdens "
        "should not be interpreted as equivalently validated TPM parameters."
    )


def _legacy_validation_page() -> None:
    hero(
        "Validation laboratory",
        "Reproduce paper-aligned predictions, compare methods, and inspect performance without hiding individual compounds.",
        "Model diagnostics",
    )
    records = validation_records()
    controls = st.columns(3)
    mode = controls[0].selectbox("Toxic mode", ["baseline", "less_inert", "reactive"], format_func=mode_label, key="validation_mode")
    role_options = sorted(records.loc[records["toxic_mode"] == mode, "set_role"].unique())
    role = controls[1].selectbox("Cohort", role_options, format_func=str.title)
    phase = controls[2].selectbox("Phase", phase_options(), format_func=phase_label, key="validation_phase")
    selected = records[(records["toxic_mode"] == mode) & (records["set_role"] == role)].copy()
    burden = burden_record(mode, phase)
    k_column = phase_log_k_column(phase)
    selected["TPM"] = selected[k_column] + float(burden["neglog_critical_burden_mol_kg"])
    method_columns = {
        "TPM median": "TPM",
        "ASM": "prediction_asm_neglog_lc50",
        "ECOSAR": "prediction_ecosar_neglog_lc50",
        "Baseline model": "prediction_bl_neglog_lc50",
        "Lipid model": "prediction_lim_neglog_lc50",
    }
    method_label = st.selectbox("Prediction series", list(method_columns))
    prediction_column = method_columns[method_label]
    clean = selected.dropna(subset=["experimental_neglog_lc50_mol_l", prediction_column]).copy()
    metrics = prediction_metrics(clean["experimental_neglog_lc50_mol_l"], clean[prediction_column])
    cols = st.columns(5)
    cols[0].metric("n", int(metrics["n"]))
    cols[1].metric("RMSE", f"{metrics['rmse']:.3f}")
    cols[2].metric("MAE", f"{metrics['mae']:.3f}")
    cols[3].metric("Within factor 2", f"{metrics['within_factor_2_pct']:.1f}%")
    cols[4].metric("Within factor 10", f"{metrics['within_factor_10_pct']:.1f}%")
    if mode == "reactive" and method_label == "TPM median":
        st.warning("This is a retrospective evidence diagnostic, not a supported reactive-toxicant prediction mode.")
    lower = min(clean["experimental_neglog_lc50_mol_l"].min(), clean[prediction_column].min()) - 0.4
    upper = max(clean["experimental_neglog_lc50_mol_l"].max(), clean[prediction_column].max()) + 0.4
    figure = px.scatter(
        clean,
        x="experimental_neglog_lc50_mol_l",
        y=prediction_column,
        color="chemical_class",
        hover_data=["name", "casrn", "set_label"],
        labels={"experimental_neglog_lc50_mol_l": "Observed pLC50", prediction_column: f"{method_label} predicted pLC50", "chemical_class": "Chemical class"},
        title=f"{method_label}: {mode_label(mode)}, {role} cohort, {phase_label(phase)} phase",
    )
    figure.add_trace(go.Scatter(x=[lower, upper], y=[lower, upper], mode="lines", name="1:1", line=dict(color="#173b3a", dash="dash")))
    figure.add_trace(go.Scatter(x=[lower, upper], y=[lower + 1, upper + 1], mode="lines", name="factor 10", line=dict(color="#ef9f32", dash="dot"), showlegend=False))
    figure.add_trace(go.Scatter(x=[lower, upper], y=[lower - 1, upper - 1], mode="lines", line=dict(color="#ef9f32", dash="dot"), showlegend=False))
    figure.update_xaxes(range=[lower, upper])
    figure.update_yaxes(range=[lower, upper], scaleanchor="x", scaleratio=1)
    figure.update_layout(height=610, margin=dict(l=10, r=10, t=60, b=10), plot_bgcolor="white")
    st.plotly_chart(figure, width="stretch")
    clean["prediction_error_log_unit"] = clean[prediction_column] - clean["experimental_neglog_lc50_mol_l"]
    display = clean[["name", "casrn", "chemical_class", "experimental_neglog_lc50_mol_l", prediction_column, "prediction_error_log_unit"]]
    st.dataframe(display, width="stretch", hide_index=True)
    st.download_button("Download filtered validation table", clean.to_csv(index=False), "tpm_validation_view.csv", "text/csv")


def validation_page() -> None:
    hero(
        "Validation laboratory",
        "Filter the paper cohorts, inspect median-TPM residuals, compare reference models, and identify where performance changes across chemical space.",
        "Model diagnostics",
    )
    records = validation_records()
    controls = st.columns(4)
    mode = controls[0].selectbox(
        "Toxic mode", ["baseline", "less_inert", "reactive"], format_func=mode_label, key="validation_mode_v11"
    )
    role_options = sorted(records.loc[records["toxic_mode"] == mode, "set_role"].unique())
    role = controls[1].selectbox("Cohort", role_options, format_func=str.title, key="validation_role_v11")
    phase = controls[2].selectbox(
        "Phase", phase_options(), format_func=phase_label, key="validation_phase_v11"
    )
    method_label = controls[3].selectbox(
        "Prediction series",
        ["TPM median", "ASM", "ECOSAR", "Baseline model", "Lipid model"],
        key="validation_method_v11",
    )

    selected = records[(records["toxic_mode"] == mode) & (records["set_role"] == role)].copy()
    burden = burden_record(mode, phase)
    k_column = phase_log_k_column(phase)
    selected["TPM"] = selected[k_column] + float(burden["neglog_critical_burden_mol_kg"])
    method_columns = {
        "TPM median": "TPM",
        "ASM": "prediction_asm_neglog_lc50",
        "ECOSAR": "prediction_ecosar_neglog_lc50",
        "Baseline model": "prediction_bl_neglog_lc50",
        "Lipid model": "prediction_lim_neglog_lc50",
    }
    prediction_column = method_columns[method_label]

    st.markdown("### Filters")
    filter_cols = st.columns(2)
    log_values = selected["log_kow_epi"].dropna()
    log_bounds = (float(log_values.min()), float(log_values.max()))
    log_range = filter_cols[0].slider(
        "log Kow range",
        min_value=log_bounds[0],
        max_value=log_bounds[1],
        value=log_bounds,
        step=0.1,
        key="validation_logkow_range",
    )
    observed_values = selected["experimental_neglog_lc50_mol_l"].dropna()
    observed_bounds = (float(observed_values.min()), float(observed_values.max()))
    observed_range = filter_cols[1].slider(
        "Observed -log10 LC50 range",
        min_value=observed_bounds[0],
        max_value=observed_bounds[1],
        value=observed_bounds,
        step=0.1,
        key="validation_observed_range",
    )
    filter_cols_2 = st.columns(3)
    chemical_classes = filter_cols_2[0].multiselect(
        "Chemical classes",
        sorted(selected["chemical_class"].dropna().unique()),
        placeholder="All classes",
    )
    ecosar_classes = filter_cols_2[1].multiselect(
        "ECOSAR classes",
        sorted(selected["ecosar_class"].dropna().unique()),
        placeholder="All ECOSAR classes",
    )
    descriptor_sources = filter_cols_2[2].multiselect(
        "Descriptor-data sources",
        sorted(selected["literature"].dropna().unique()),
        placeholder="All sources",
    )
    selected = selected[
        selected["log_kow_epi"].between(*log_range, inclusive="both")
        & selected["experimental_neglog_lc50_mol_l"].between(*observed_range, inclusive="both")
    ].copy()
    if chemical_classes:
        selected = selected[selected["chemical_class"].isin(chemical_classes)]
    if ecosar_classes:
        selected = selected[selected["ecosar_class"].isin(ecosar_classes)]
    if descriptor_sources:
        selected = selected[selected["literature"].isin(descriptor_sources)]

    clean = selected.dropna(
        subset=["experimental_neglog_lc50_mol_l", prediction_column, "log_kow_epi"]
    ).copy()
    if clean.empty:
        st.warning("No records remain after the selected filters.")
        return
    clean["prediction_error_log_unit"] = (
        clean[prediction_column] - clean["experimental_neglog_lc50_mol_l"]
    )
    clean["absolute_error_log_unit"] = clean["prediction_error_log_unit"].abs()
    clean["fold_difference"] = 10 ** clean["absolute_error_log_unit"]
    clean["log_kow_group"] = pd.cut(
        clean["log_kow_epi"],
        bins=[-math.inf, 0, 3, math.inf],
        labels=["log Kow < 0", "0 to 3", "log Kow > 3"],
    )
    metrics = prediction_metrics(
        clean["experimental_neglog_lc50_mol_l"], clean[prediction_column]
    )
    metric_cols = st.columns(7)
    metric_cols[0].metric("n", int(metrics["n"]))
    metric_cols[1].metric("RMSE", f"{metrics['rmse']:.3f}")
    metric_cols[2].metric("MAE", f"{metrics['mae']:.3f}")
    metric_cols[3].metric("Bias", f"{metrics['bias']:+.3f}")
    metric_cols[4].metric("Within factor 2", f"{metrics['within_factor_2_pct']:.1f}%")
    metric_cols[5].metric("Within factor 5", f"{metrics['within_factor_5_pct']:.1f}%")
    metric_cols[6].metric("Within factor 10", f"{metrics['within_factor_10_pct']:.1f}%")
    if mode == "reactive" and method_label == "TPM median":
        st.warning("This is a retrospective evidence diagnostic, not a supported reactive-toxicant prediction mode.")

    scatter_tab, residual_tab, class_tab, outlier_tab = st.tabs(
        ["Observed vs predicted", "Residual diagnostics", "Chemical classes", "Outliers and records"]
    )
    lower = min(clean["experimental_neglog_lc50_mol_l"].min(), clean[prediction_column].min()) - 0.4
    upper = max(clean["experimental_neglog_lc50_mol_l"].max(), clean[prediction_column].max()) + 0.4
    with scatter_tab:
        figure = px.scatter(
            clean,
            x="experimental_neglog_lc50_mol_l",
            y=prediction_column,
            color="chemical_class",
            symbol="log_kow_group",
            hover_data=["name", "casrn", "set_label", "log_kow_epi", "prediction_error_log_unit"],
            labels={
                "experimental_neglog_lc50_mol_l": "Observed pLC50",
                prediction_column: f"{method_label} predicted pLC50",
                "chemical_class": "Chemical class",
            },
            title=f"{method_label}: {mode_label(mode)}, {role}, {phase_label(phase)}",
        )
        figure.add_trace(
            go.Scatter(x=[lower, upper], y=[lower, upper], mode="lines", name="1:1", line=dict(color="#173b3a", dash="dash"))
        )
        for offset, name, show in [
            (math.log10(2), "factor 2", True),
            (-math.log10(2), "factor 2", False),
            (1.0, "factor 10", True),
            (-1.0, "factor 10", False),
        ]:
            figure.add_trace(
                go.Scatter(
                    x=[lower, upper],
                    y=[lower + offset, upper + offset],
                    mode="lines",
                    name=name,
                    showlegend=show,
                    line=dict(color="#ef9f32" if abs(offset) == 1 else "#79b6a6", dash="dot"),
                )
            )
        figure.update_xaxes(range=[lower, upper])
        figure.update_yaxes(range=[lower, upper], scaleanchor="x", scaleratio=1)
        figure.update_layout(height=650, margin=dict(l=10, r=10, t=60, b=10))
        st.plotly_chart(figure, width="stretch")

    with residual_tab:
        residual_cols = st.columns([1.25, 1])
        residual_figure = px.scatter(
            clean,
            x="log_kow_epi",
            y="prediction_error_log_unit",
            color="chemical_class",
            hover_data=["name", "casrn", "fold_difference"],
            labels={
                "log_kow_epi": "log Kow",
                "prediction_error_log_unit": "Prediction - observation (log unit)",
            },
            title="Residual versus hydrophobicity",
        )
        residual_figure.add_hline(y=0, line_dash="dash", line_color="#173b3a")
        residual_figure.add_hrect(y0=-math.log10(2), y1=math.log10(2), fillcolor="#dff3ec", opacity=0.35, line_width=0)
        residual_cols[0].plotly_chart(residual_figure, width="stretch")
        histogram = px.histogram(
            clean,
            x="prediction_error_log_unit",
            color="log_kow_group",
            marginal="box",
            title="Residual distribution",
        )
        residual_cols[1].plotly_chart(histogram, width="stretch")
        hydrophobicity_summary = (
            clean.groupby("log_kow_group", observed=False)
            .apply(
                lambda group: pd.Series(
                    prediction_metrics(
                        group["experimental_neglog_lc50_mol_l"], group[prediction_column]
                    )
                ),
                include_groups=False,
            )
            .reset_index()
        )
        st.dataframe(hydrophobicity_summary, width="stretch", hide_index=True)

    with class_tab:
        class_figure = px.box(
            clean,
            x="chemical_class",
            y="prediction_error_log_unit",
            color="chemical_class",
            points="outliers",
            hover_data=["name", "casrn"],
            title="Residuals by chemical class",
        )
        class_figure.add_hline(y=0, line_dash="dash", line_color="#173b3a")
        class_figure.update_layout(showlegend=False, height=560)
        st.plotly_chart(class_figure, width="stretch")
        class_summary = (
            clean.groupby("chemical_class")
            .agg(
                n=("name", "size"),
                mean_error=("prediction_error_log_unit", "mean"),
                median_absolute_error=("absolute_error_log_unit", "median"),
                max_fold_difference=("fold_difference", "max"),
            )
            .sort_values("median_absolute_error", ascending=False)
            .reset_index()
        )
        st.dataframe(class_summary, width="stretch", hide_index=True)

    with outlier_tab:
        display = clean[
            [
                "name",
                "casrn",
                "chemical_class",
                "ecosar_class",
                "log_kow_epi",
                "experimental_neglog_lc50_mol_l",
                prediction_column,
                "prediction_error_log_unit",
                "absolute_error_log_unit",
                "fold_difference",
                "set_label",
            ]
        ].sort_values("absolute_error_log_unit", ascending=False)
        st.dataframe(display, width="stretch", hide_index=True)

    st.caption(
        "The TPM series always uses the paper-recommended median critical burden. "
        "Partition coefficients in these published cohorts are the source-workbook values; this page does not relabel them as user measurements."
    )
    st.download_button(
        "Download filtered validation table", clean.to_csv(index=False), "tpm_validation_view.csv", "text/csv"
    )


def polymer_selection_page() -> None:
    hero(
        "Polymer-selection assistant",
        "Compare the five validated plastic phases for a declared scientific objective without conflating predictive accuracy, enrichment, and practical use.",
        "Decision support",
    )
    controls = st.columns(2)
    mode = controls[0].selectbox(
        "Toxic mode", ["baseline", "less_inert"], format_func=mode_label, key="polymer_assistant_mode"
    )
    objective = controls[1].selectbox(
        "Primary objective",
        [
            "Lowest TPM validation error",
            "Highest chemical-specific enrichment",
            "Passive-sampling comparison",
            "Passive-dosing comparison",
            "Qualitative equilibration considerations",
        ],
    )
    records = validation_records()
    candidates = records[records["toxic_mode"] == mode].copy()
    candidates["selector"] = candidates.apply(
        lambda row: f"{row['name']} | {row['casrn']} | {row['set_label']}", axis=1
    )
    selected_label = st.selectbox("Reference chemical", candidates["selector"].tolist())
    chemical = candidates.loc[candidates["selector"] == selected_label].iloc[0]

    rows = []
    registry = model_registry()
    for phase in phase_options(True):
        burden = burden_record(mode, phase)
        log_k = chemical[phase_log_k_column(phase)]
        provenance = registry["partition_model_provenance"][phase]
        guidance = registry["polymer_guidance"][phase]
        rows.append(
            {
                "phase_key": phase,
                "phase": phase_label(phase),
                "validation_rmse_log_unit": burden["rmse_validation_log_unit"],
                "evaluation_rmse_log_unit": burden["rmse_evaluation_log_unit"],
                "chemical_log_k": log_k,
                "median_critical_burden_mmol_kg": burden["critical_burden_mmol_kg"],
                "partition_method": provenance["method"],
                "partition_source": provenance["source"],
                "passive_sampling": guidance["passive_sampling"],
                "passive_dosing": guidance["passive_dosing"],
                "practical_note": guidance["practical_note"],
            }
        )
    comparison = pd.DataFrame(rows)
    best_accuracy = comparison.loc[comparison["validation_rmse_log_unit"].idxmin()]
    best_enrichment = comparison.loc[comparison["chemical_log_k"].idxmax()]

    if objective == "Lowest TPM validation error":
        comparison = comparison.sort_values("validation_rmse_log_unit")
        st.success(
            f"For {mode_label(mode)}, **{best_accuracy['phase']}** has the lowest full-cohort validation RMSE "
            f"({best_accuracy['validation_rmse_log_unit']:.3f} log unit)."
        )
    elif objective == "Highest chemical-specific enrichment":
        comparison = comparison.sort_values("chemical_log_k", ascending=False)
        st.success(
            f"For **{chemical['name']}**, the largest available paper-dataset log K is for "
            f"**{best_enrichment['phase']}** ({best_enrichment['chemical_log_k']:.3f})."
        )
    elif objective == "Passive-sampling comparison":
        comparison = comparison.sort_values(["chemical_log_k", "validation_rmse_log_unit"], ascending=[False, True])
        st.info(
            "Use the chemical-specific log K to judge enrichment, then inspect material practicality and validation error separately. "
            "The assistant does not collapse these distinct criteria into an undocumented score."
        )
    elif objective == "Passive-dosing comparison":
        comparison = comparison.sort_values("validation_rmse_log_unit")
        st.info(
            "PDMS has a strong practical history as a donor phase, whereas PA and POM provide the strongest baseline TPM accuracy. "
            "The final choice should match the available material, loading method, and measured partition data."
        )
    else:
        comparison = comparison.sort_values("phase")
        st.warning(
            "This view provides qualitative material caveats only. It does not estimate equilibration time or assign a field-confidence score."
        )

    summary_cols = st.columns(3)
    summary_cols[0].metric("Reference chemical", str(chemical["name"]))
    summary_cols[1].metric("Lowest validation RMSE", f"{best_accuracy['phase']} · {best_accuracy['validation_rmse_log_unit']:.3f}")
    summary_cols[2].metric("Highest log K", f"{best_enrichment['phase']} · {best_enrichment['chemical_log_k']:.3f}")

    figure = px.scatter(
        comparison,
        x="chemical_log_k",
        y="validation_rmse_log_unit",
        size="median_critical_burden_mmol_kg",
        color="phase",
        text="phase",
        hover_data=["evaluation_rmse_log_unit", "partition_method", "practical_note"],
        labels={
            "chemical_log_k": f"log K for {chemical['name']}",
            "validation_rmse_log_unit": "Validation RMSE (log unit)",
            "median_critical_burden_mmol_kg": "Median Ccrit (mmol/kg)",
        },
        title="Separate view of enrichment and predictive performance",
    )
    figure.update_traces(textposition="top center")
    figure.update_layout(height=500, margin=dict(l=10, r=10, t=55, b=10))
    st.plotly_chart(figure, width="stretch")

    display_columns = [
        "phase",
        "chemical_log_k",
        "validation_rmse_log_unit",
        "median_critical_burden_mmol_kg",
        "passive_sampling",
        "passive_dosing",
        "practical_note",
    ]
    st.dataframe(comparison[display_columns], width="stretch", hide_index=True)
    with st.expander("Partition-equation provenance"):
        st.dataframe(partition_provenance_frame(), width="stretch", hide_index=True)
    st.download_button(
        "Download polymer comparison", comparison.to_csv(index=False), "tpm_polymer_selection.csv", "text/csv"
    )


def passive_dosing_page() -> None:
    hero(
        "Passive-dosing experiment designer",
        "Create a logarithmic polymer-loading series around the median critical burden and visualize the expected TPM exposure range.",
        "Experimental design",
    )
    controls = st.columns(3)
    mode = controls[0].selectbox(
        "Toxic mode", ["baseline", "less_inert"], format_func=mode_label, key="dosing_mode"
    )
    phase = controls[1].selectbox(
        "Validated plastic phase", phase_options(True), format_func=phase_label, key="dosing_phase"
    )
    partition_source = controls[2].selectbox(
        "Partition input", ["Published compound", "Measured log K"], key="dosing_partition_source"
    )

    records = validation_records()
    available = records[records["toxic_mode"] == mode].copy()
    if partition_source == "Published compound":
        available["selector"] = available.apply(
            lambda row: f"{row['name']} | {row['casrn']} | {row['set_label']}", axis=1
        )
        label = st.selectbox("Reference chemical", available["selector"].tolist(), key="dosing_chemical")
        chemical = available.loc[available["selector"] == label].iloc[0]
        chemical_name = str(chemical["name"])
        molecular_weight = float(chemical["molecular_weight_g_mol"])
        log_k = float(chemical[phase_log_k_column(phase)])
    else:
        manual_cols = st.columns(3)
        chemical_name = manual_cols[0].text_input("Chemical name", value="Manual chemical")
        molecular_weight = manual_cols[1].number_input(
            "Molecular weight (g/mol)", min_value=0.001, value=100.0, step=1.0
        )
        log_k = manual_cols[2].number_input("Measured log Kplastic-water", value=3.0, step=0.1)

    burden = burden_record(mode, phase)
    design_cols = st.columns(5)
    polymer_mass_g = design_cols[0].number_input("Polymer mass (g)", min_value=0.001, value=1.0, step=0.1)
    minimum_fraction = design_cols[1].number_input(
        "Minimum Ccrit fraction", min_value=0.0001, value=0.01, format="%.4f"
    )
    maximum_fraction = design_cols[2].number_input(
        "Maximum Ccrit fraction", min_value=0.001, value=3.0, format="%.3f"
    )
    number_of_doses = design_cols[3].number_input(
        "Dose levels", min_value=3, max_value=20, value=8, step=1
    )
    hill_slope = design_cols[4].number_input(
        "Illustrative Hill slope", min_value=0.1, max_value=5.0, value=1.0, step=0.1
    )
    try:
        design = pd.DataFrame(
            passive_dosing_series(
                critical_burden_mmol_kg=float(burden["critical_burden_mmol_kg"]),
                log_k_phase_water=log_k,
                molecular_weight_g_mol=molecular_weight,
                polymer_mass_g=polymer_mass_g,
                minimum_fraction=minimum_fraction,
                maximum_fraction=maximum_fraction,
                number_of_doses=int(number_of_doses),
                hill_slope=hill_slope,
            )
        )
    except ScientificInputError as error:
        st.error(str(error))
        return
    design["chemical"] = chemical_name
    design["mode"] = mode
    design["phase"] = phase
    design["log_k_phase_water"] = log_k
    design["median_critical_burden_mmol_kg"] = burden["critical_burden_mmol_kg"]
    design["chemical_loaded_mmol"] = (
        design["polymer_burden_mmol_kg"] * polymer_mass_g / 1000.0
    )
    design = design.drop(
        columns=["chemical_loaded_mg", "ideal_water_concentration_mg_l"],
        errors="ignore",
    )

    metrics = st.columns(4)
    metrics[0].metric("Median Ccrit", f"{burden['critical_burden_mmol_kg']:.4g} mmol/kg")
    metrics[1].metric("log Kplastic-water", f"{log_k:.3f}")
    predicted = predict_lc50(
        phase, mode, log_k, float(burden["neglog_critical_burden_mol_kg"]), molecular_weight
    )
    metrics[2].metric(
        "TPM LC50", f"{mol_l_to_mmol_l(predicted.predicted_lc50_mol_l):.4g} mmol/L"
    )
    metrics[3].metric("Designed levels", len(design))

    dose_figure = px.line(
        design,
        x="fraction_of_critical_burden",
        y="illustrative_response_pct",
        markers=True,
        log_x=True,
        hover_data=["polymer_burden_mmol_kg", "chemical_loaded_mmol", "ideal_water_concentration_mmol_l"],
        labels={
            "fraction_of_critical_burden": "Polymer burden / median Ccrit",
            "illustrative_response_pct": "Illustrative response (%)",
        },
        title="Dose versus illustrative response",
    )
    dose_figure.add_vline(x=1.0, line_dash="dash", annotation_text="Median Ccrit / TPM LC50")
    dose_figure.add_hline(y=50.0, line_dash="dot")
    dose_figure.update_layout(height=500)
    st.plotly_chart(dose_figure, width="stretch")

    exposure_figure = px.line(
        design,
        x="polymer_burden_mmol_kg",
        y="ideal_water_concentration_mmol_l",
        markers=True,
        log_x=True,
        log_y=True,
        labels={
            "polymer_burden_mmol_kg": "Polymer loading (mmol/kg)",
            "ideal_water_concentration_mmol_l": "Ideal equilibrium water concentration (mmol/L)",
        },
        title="Designed polymer loading and corresponding ideal water concentration",
    )
    st.plotly_chart(exposure_figure, width="stretch")
    st.dataframe(design, width="stretch", hide_index=True)
    st.warning(
        "The response curve is an experimental-design illustration anchored to 50% response at the median TPM critical burden. "
        "It is not fitted biological response data. Ideal water concentrations assume the entered partition coefficient applies; "
        "loading recovery and exposure stability must be verified experimentally."
    )
    st.download_button(
        "Download passive-dosing design", design.to_csv(index=False), "tpm_passive_dosing_design.csv", "text/csv"
    )


def _v11_comptox_fish_page() -> None:
    hero(
        "CompTox fish evidence",
        "Resolve chemical identity and retrieve fish-only acute evidence without mixing predicted and experimental values.",
        "EPA evidence bridge",
    )
    st.info(
        "Current scope: fish acute toxicity only. The direct numerical prediction is the EPA WebTEST consensus "
        "96-hour fathead-minnow LC50; experimental studies remain linked to EPA ECOTOX for endpoint-level review."
    )
    key = api_key()
    query = st.text_input("Name, CAS RN, DTXSID, or InChIKey", key="fish_comptox_query")
    if not key:
        st.warning("Configure a free EPA CTX API key to resolve an exact CompTox identity.")
        st.link_button(
            "EPA CTX API access information",
            "https://www.epa.gov/comptox-tools/computational-toxicology-and-exposure-apis-about",
        )
    else:
        st.success("CompTox API key detected. The key remains in local Streamlit secrets and is not displayed or exported.")
    if st.button("Resolve exact CompTox identity", disabled=not key or not query, key="fish_identity_button"):
        try:
            with st.spinner("Querying EPA CompTox..."):
                st.session_state["fish_comptox_identity"] = CompToxClient(key).exact_identity(query)
                st.session_state.pop("fish_webtest_prediction", None)
        except CompToxError as error:
            st.error(str(error))

    identity = st.session_state.get("fish_comptox_identity")
    if not identity:
        st.caption(
            "Without an API key, the paper dataset and the external EPA fish resources below remain available."
        )
        links = st.columns(2)
        links[0].link_button("EPA fathead-minnow acute toxicity list", EPA_FATHEAD_MINNOW_LIST_URL)
        links[1].link_button("Search experimental fish studies in ECOTOX", ECOTOX_URL)
        return

    identity_cols = st.columns(4)
    identity_cols[0].metric("Preferred name", identity.preferred_name)
    identity_cols[1].metric("DTXSID", identity.dtxsid or "-")
    identity_cols[2].metric("CAS RN", identity.casrn or "-")
    identity_cols[3].metric(
        "Molecular weight", f"{identity.molecular_weight:.3f} g/mol" if identity.molecular_weight else "-"
    )
    st.code(identity.smiles or "No structure returned", language=None)

    if st.button(
        "Retrieve direct WebTEST 96 h fish LC50",
        disabled=not identity.smiles,
        key="fish_webtest_button",
    ):
        try:
            with st.spinner("Retrieving the EPA WebTEST report..."):
                st.session_state["fish_webtest_prediction"] = fetch_webtest_prediction(identity.smiles)
        except CompToxError as error:
            st.error(str(error))
    prediction = st.session_state.get("fish_webtest_prediction")
    if prediction:
        prediction_cols = st.columns(3)
        prediction_cols[0].metric("Endpoint", "Fathead minnow LC50 (96 h)")
        prediction_cols[1].metric(
            "Predicted pLC50", f"{prediction.predicted_neglog_mol_l:.3f}",
            help="pLC50 = -log10 of LC50 expressed in mol/L.",
        )
        prediction_cols[2].metric(
            "Predicted LC50",
            f"{format_scientific(mol_l_to_mmol_l(prediction.predicted_mol_l))} mmol/L",
        )
        st.caption("Evidence type: EPA WebTEST consensus QSAR prediction—not an experimental observation.")
        st.link_button("Open full WebTEST report", prediction.report_url)

    st.markdown("### Paper-dataset fish observations")
    published = validation_records()
    matches = published[
        (published["casrn"].astype(str) == str(identity.casrn))
        | (published["name"].str.casefold() == identity.preferred_name.casefold())
    ].copy()
    if matches.empty:
        st.info("No exact identity match was found in the TPM paper cohorts.")
    else:
        matches["experimental_lc50_mmol_l"] = (
            10 ** (-matches["experimental_neglog_lc50_mol_l"]) * 1000
        )
        st.dataframe(
            matches[
                [
                    "name",
                    "casrn",
                    "set_label",
                    "toxic_mode",
                    "experimental_neglog_lc50_mol_l",
                    "experimental_lc50_mmol_l",
                    "literature",
                ]
            ],
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "These are curated fish LC50 values from the TPM supporting dataset. They are not relabeled as CompTox or WebTEST records."
        )

    links = st.columns(4)
    links[0].link_button("CompTox chemical page", comptox_dashboard_url(identity.dtxsid))
    links[1].link_button("EPA fathead-minnow list", EPA_FATHEAD_MINNOW_LIST_URL)
    links[2].link_button("Search ECOTOX fish studies", ECOTOX_URL)
    links[3].link_button(
        "Open WebTEST report", webtest_report_url(identity.smiles), disabled=not identity.smiles
    )
    st.caption(
        "When reviewing ECOTOX, retain only fish LC50 studies with the intended acute duration—preferably 96 hours—and preserve species, "
        "test conditions, measured/nominal exposure, units, qualifiers, and the original citation."
    )


def comptox_fish_page() -> None:
    hero(
        "CompTox fish evidence workspace",
        "Retrieve a chemical outside the TPM paper cohort and translate EPA 96-hour fish and logKow evidence into phase-specific TPM screening quantities.",
        "EPA evidence + TPM interpretation",
    )
    st.info(
        "Scope is deliberately restricted to the 96-hour fathead-minnow LC50 property used by EPA TEST. "
        "Experimental references, QSAR predictions, and study-level ECOTOX evidence are not merged or relabeled."
    )
    key = api_key()
    query = st.text_input("Name, CAS RN, DTXSID, or InChIKey", key="fish_comptox_query_v12")
    if not key:
        st.warning("Configure an EPA CTX API key to use the integrated evidence retrieval.")
        st.link_button(
            "EPA CTX API access information",
            "https://www.epa.gov/comptox-tools/computational-toxicology-and-exposure-apis-about",
        )
    if st.button(
        "Retrieve integrated fish evidence",
        disabled=not key or not query,
        key="fish_evidence_button_v12",
    ):
        try:
            with st.spinner("Retrieving identity and EPA property evidence..."):
                bundle = CompToxClient(key).evidence_bundle(query)
            st.session_state["fish_comptox_evidence"] = bundle
            st.session_state["comptox_evidence"] = bundle
            st.session_state["comptox_identity"] = bundle.identity
            if bundle.log_kow.selected_value is not None:
                st.session_state["single_partition_input"] = "CompTox logKow screening"
        except CompToxError as error:
            st.error(str(error))

    bundle = st.session_state.get("fish_comptox_evidence")
    if not bundle:
        st.caption("Search a substance to populate the evidence and TPM translation tables.")
        links = st.columns(3)
        links[0].link_button("EPA fathead-minnow list", EPA_FATHEAD_MINNOW_LIST_URL)
        links[1].link_button("Search ECOTOX fish studies", ECOTOX_URL)
        links[2].link_button("UFZ-LSER descriptors", UFZ_LSER_URL)
        return

    render_comptox_evidence(bundle)
    st.success(
        "This chemical is now available in Single chemical; that page will default to CompTox logKow screening."
    )

    st.markdown("### Phase-specific TPM translation")
    mode = st.selectbox(
        "Declared toxic mode",
        ["baseline", "less_inert"],
        format_func=mode_label,
        key="fish_translation_mode",
        help="This classification remains an expert input.",
    )
    if bundle.log_kow.selected_value is None:
        st.warning("No phase table can be calculated because CompTox returned no usable logKow value.")
    elif bundle.identity.molecular_weight is None:
        st.warning("No phase table can be calculated because molecular weight was not returned.")
    else:
        translation_rows = []
        for phase in phase_options(True):
            lfer = model_registry()["log_kow_lfer"][phase]
            log_kow = float(bundle.log_kow.selected_value)
            log_k = lfer_log_k(log_kow, lfer["intercept"], lfer["slope"])
            burden = burden_record(mode, phase)
            prediction = predict_lc50(
                phase,
                mode,
                log_k,
                float(burden["neglog_critical_burden_mol_kg"]),
                float(bundle.identity.molecular_weight),
            )
            fish = bundle.fish_lc50
            external_burden = None
            if fish and fish.experimental_neglog_mol_l is not None:
                external_burden = critical_burden_from_observation(
                    fish.experimental_neglog_mol_l, log_k
                )["critical_burden_mmol_kg"]
            translation_rows.append({
                "phase": phase_label(phase),
                "logKow": log_kow,
                "estimated_logKplastic_water": log_k,
                "partition_method": lfer["label"],
                "partition_evidence_tier": lfer["status"],
                "LFER_in_domain": lfer["log_kow_min"] <= log_kow <= lfer["log_kow_max"],
                "TPM_median_Ccrit_mmol_kg": burden["critical_burden_mmol_kg"],
                "EPA_experimental_Ccrit_mmol_kg": external_burden,
                "TPM_predicted_LC50_mmol_L": mol_l_to_mmol_l(prediction.predicted_lc50_mol_l),
                "EPA_experimental_LC50_mmol_L": (
                    mol_l_to_mmol_l(fish.experimental_mol_l) if fish else None
                ),
                "EPA_TEST_predicted_LC50_mmol_L": (
                    mol_l_to_mmol_l(fish.predicted_mol_l) if fish else None
                ),
            })
        translation = pd.DataFrame(translation_rows)
        st.dataframe(translation, width="stretch", hide_index=True)
        figure = px.scatter(
            translation,
            x="TPM_median_Ccrit_mmol_kg",
            y="EPA_experimental_Ccrit_mmol_kg",
            text="phase",
            log_x=True,
            log_y=True,
            labels={
                "TPM_median_Ccrit_mmol_kg": "TPM median Ccrit (mmol/kg)",
                "EPA_experimental_Ccrit_mmol_kg": "Chemical-specific EPA-derived Ccrit (mmol/kg)",
            },
            title="Median TPM burden versus chemical-specific experimental benchmark",
        )
        finite_values = translation["TPM_median_Ccrit_mmol_kg"].dropna().tolist()
        finite_values += translation["EPA_experimental_Ccrit_mmol_kg"].dropna().tolist()
        if finite_values:
            lower = min(finite_values)
            upper = max(finite_values)
            figure.add_shape(
                type="line", x0=lower, y0=lower, x1=upper, y1=upper,
                line=dict(color="#7b8b88", dash="dash"),
            )
        figure.update_traces(textposition="top center")
        figure.update_layout(height=470)
        st.plotly_chart(figure, width="stretch")
        st.caption(
            "PE uses the published Khawar & Nabi logKow LFER. PDMS, PA, POM, and PU use transparent one-parameter regressions fitted to paired logKow and ASM-derived K values in the TPM supporting data; those four are screening fallbacks, not published TPM equations."
        )
        st.download_button(
            "Download phase translation CSV",
            translation.to_csv(index=False),
            "tpm_comptox_phase_translation.csv",
            "text/csv",
        )

    st.markdown("### Match to the TPM paper cohort")
    published = validation_records()
    matches = published[
        (published["casrn"].astype(str) == str(bundle.identity.casrn))
        | (published["name"].str.casefold() == bundle.identity.preferred_name.casefold())
    ].copy()
    if matches.empty:
        st.info(
            "No exact match exists in the TPM paper cohort. The integrated workflow above is therefore an external screening application, not an extension of the validation dataset."
        )
    else:
        matches["experimental_lc50_mmol_l"] = (
            10 ** (-matches["experimental_neglog_lc50_mol_l"]) * 1000
        )
        st.dataframe(
            matches[
                [
                    "name", "casrn", "set_label", "toxic_mode",
                    "experimental_neglog_lc50_mol_l", "experimental_lc50_mmol_l", "literature",
                ]
            ],
            width="stretch",
            hide_index=True,
        )

    with st.expander("External records for expert review", expanded=False):
        links = st.columns(4)
        links[0].link_button("CompTox chemical page", comptox_dashboard_url(bundle.identity.dtxsid))
        links[1].link_button(
            "Current WebTEST result",
            webtest_report_url(bundle.identity.smiles),
            disabled=not bundle.identity.smiles,
        )
        links[2].link_button("Search ECOTOX studies", ECOTOX_URL)
        links[3].link_button("UFZ-LSER descriptors", UFZ_LSER_URL)
        st.caption(
            "For an assessment-grade experimental value, verify species, 96-hour duration, endpoint, measured versus nominal exposure, units, qualifiers, and original citation in the study-level record."
        )


def evidence_page() -> None:
    hero(
        "Evidence, methods, and provenance",
        "The dashboard is designed as a research companion to the paper—not a black-box toxicity oracle.",
        "Reproducibility record",
    )
    manifest = dataset_manifest()
    registry = model_registry()
    st.markdown("### Scientific interpretation")
    st.markdown(
        "The TPM maps an equilibrium partition coefficient to acute fish toxicity using a mode- and phase-specific median critical burden. "
        "The recommended estimator is the paper's median critical-burden formulation; displayed validation RMSE is empirical model error, not a probabilistic confidence interval."
    )
    st.markdown('<div class="formula">C<sub>crit</sub> = LC50 × K<sub>phase–water</sub> &nbsp;&nbsp;⇔&nbsp;&nbsp; −log LC50 = log K<sub>phase–water</sub> − log C<sub>crit</sub></div>', unsafe_allow_html=True)

    tabs = st.tabs(
        ["Scope", "Data provenance", "Partition equations", "CompTox bridge", "Unit audit", "Downloads"]
    )
    with tabs[0]:
        for item in registry["scientific_limits"]:
            st.markdown(f"- {item}")
        st.markdown(f"Primary source: [Nabi, Beck & Achterberg (2024)]({PAPER_URL}).")
    with tabs[1]:
        st.json(manifest)
        st.code(f"SHA-256  {manifest['source']['sha256']}", language=None)
        st.caption("The original ACS PDFs and workbook are not bundled into the app repository. The local normalization script reads the author's source workbook and emits compact, versioned tables.")
    with tabs[2]:
        st.dataframe(partition_provenance_frame(), width="stretch", hide_index=True)
        st.link_button("Open the UFZ-LSER descriptor database", UFZ_LSER_URL)
        st.caption(
            "Missing n, R2, or standard-error entries mean that the statistic was not recorded in the archived equation table; "
            "the dashboard does not manufacture a replacement value."
        )
    with tabs[3]:
        st.markdown(
            """
            - **CTX Chemical API:** exact identity, detailed molecular weight, logKow summaries, and the EPA TEST property record; requires a free personal API key.
            - **EPA TEST 96-hour fish property:** experimental-reference and predicted LC50 fields are retained separately, together with TEST applicability-domain information.
            - **WebTEST:** the current JSON service provides the structure-based 96-hour fathead-minnow consensus result.
            - **ECOTOX:** study-level experimental ecotoxicity evidence, including fish endpoints and test conditions.

            The app keeps these evidence types separate. A TEST experimental field is not presented as a fully reviewed ECOTOX study, and external records are never silently merged into the TPM validation set. The paper median remains the primary burden estimator.
            """
        )
        st.link_button("EPA CTX API documentation", EPA_API_URL)
    with tabs[4]:
        st.markdown(
            "**Dashboard reporting convention:** water-phase LC50 and equilibrium concentrations are displayed as "
            "**mmol/L**; plastic-phase concentrations, PNECs, and critical burdens are displayed as "
            "**mmol/kg plastic**. Analysts may enter reported mass units, but the calculation layer converts them "
            "to the corresponding molar basis using molecular weight before any comparison. Where pLC50 is shown, "
            "it retains its conventional definition, -log10 of LC50 expressed in mol/L."
        )
        st.markdown(
            "The supplementary workbook stores reactive critical burdens on a **−log₁₀(mol/kg)** basis. "
            "The dashboard converts mol/kg to mmol/kg by multiplying by 1000. The resulting five reactive plastic medians span "
            "approximately **0.001001–0.678054 mmol/kg**. This differs by a factor of 1000 from treating the logged values as if their inverse were already mmol/kg. "
            "Reactive calculations remain disabled regardless of this correction because they are mechanistically out of domain."
        )
    with tabs[5]:
        for filename, label in [
            ("validation_records.csv", "Normalized validation records"),
            ("critical_burdens.csv", "Critical-burden registry"),
            ("other_plastics.csv", "Exploratory other-plastic records"),
            ("model_registry.json", "Model registry"),
            ("dataset_manifest.json", "Dataset manifest"),
        ]:
            path = DATA_DIR / filename
            st.download_button(label, path.read_bytes(), filename, mime="application/json" if filename.endswith("json") else "text/csv")


def about_sidebar() -> None:
    st.sidebar.markdown("## TPM Explorer")
    st.sidebar.caption("Scientific dashboard · v" + __version__)
    st.sidebar.markdown("---")


def run() -> None:
    configure_page()
    about_sidebar()
    workspaces = {
        "Assessment": {
            "Start assessment": direct_assessment_page,
            "Advanced field processor": mixture_page,
        },
        "Model science": {
            "Overview": overview_page,
            "Mechanistic investigation": single_chemical_page,
            "Polymer atlas": atlas_page,
            "Polymer selection": polymer_selection_page,
            "Validation lab": validation_page,
        },
        "Experiment design": {
            "Passive dosing": passive_dosing_page,
        },
        "Evidence": {
            "CompTox fish": comptox_fish_page,
            "Evidence & methods": evidence_page,
        },
    }
    workspace = st.sidebar.selectbox("Workspace", list(workspaces), key="navigation_workspace")
    pages = workspaces[workspace]
    page = st.sidebar.radio("Navigate", list(pages), key=f"navigation_page_{workspace}")
    st.sidebar.markdown("---")
    st.sidebar.markdown('<span class="pill">DOI-linked</span><span class="pill">auditable</span>', unsafe_allow_html=True)
    st.sidebar.caption("Research-use predictions. Toxic mode, equilibrium, ionization, and chemical identity remain expert judgments.")
    pages[page]()
    st.markdown("---")
    st.caption(
        f"Target Plastic Model Explorer · Code release v{__version__} · Nabi, Beck & Achterberg (2024) · Not a regulatory decision system"
    )
