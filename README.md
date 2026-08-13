# Target Plastic Model Explorer

An auditable Streamlit dashboard for the Target Plastic Model (TPM) described by Nabi, Beck, and Achterberg (2024). The app turns measured chemical burdens on plastic or passive samplers into transparent single-chemical and mixture screening results while preserving model scope, units, and provenance.

Repository: [deedarnabi/target-plastic-model-explorer](https://github.com/deedarnabi/target-plastic-model-explorer)

Live dashboard: [target-plastic-model-explorer.streamlit.app](https://target-plastic-model-explorer.streamlit.app/)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21923164.svg)](https://doi.org/10.5281/zenodo.21923164)
[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://target-plastic-model-explorer.streamlit.app/)

> Research-use model. This app is not a regulatory decision system and does not replace toxic-mode assignment, ionization assessment, equilibrium assessment, or review of the underlying studies.

## Primary calculation

For a chemical measured on a validated plastic phase:

```text
TUi                  = Cplastic,i / Ccrit,plastic
TUmixture            = sum(TUi)
PNECplastic,equivalent = Ccrit,plastic / AF
RQ                   = TUmixture * AF
```

`Cplastic` and the median `Ccrit,plastic` are expressed as mmol/kg plastic. TU and RQ are dimensionless. The primary pathway does not require a chemical-specific LC50 or `Kplastic-water`; molecular weight is needed only to convert a mass-based plastic concentration to mmol/kg.

A water-column result follows a separate pathway. The app first converts the water concentration to mmol/L and then requires a defensible `Kplastic-water` to estimate the corresponding plastic burden. Water and plastic units are never treated as interchangeable.

Primary publication: [Nabi, D.; Beck, A. J.; Achterberg, E. P. *J. Chem. Inf. Model.* 2024, 64, 6492-6505](https://doi.org/10.1021/acs.jcim.4c00574).

## Dashboard workflow

- **Start assessment** - default single-chemical and compatible-mixture calculation, editable examples, unit normalization, contribution plots, PNEC equivalents, RQ, and exports.
- **Mechanistic investigation** - optional LC50 prediction and chemical-specific burden comparison using measured or predicted partition evidence.
- **Advanced field processor** - multi-sample uploads, qualifiers, nondetect substitution, metadata, and sample summaries.
- **Polymer atlas** - phase medians, chemical-level burden distributions, and warned exploratory plastics.
- **Polymer selection** - objective-specific comparisons for accuracy, enrichment, passive sampling, passive dosing, and material considerations.
- **Validation lab** - evaluation/validation filters, observed-versus-predicted plots, residuals, class summaries, and outlier diagnostics.
- **Passive dosing** - loading-series design around median critical burden with ideal exposure tables and an illustrative response plot.
- **CompTox fish** - exact identity plus separately labeled EPA TEST 96-hour fathead-minnow evidence and ECOTOX study links.
- **Evidence & methods** - source hashes, equations, limitations, unit audit, and downloads.

The operational estimator is the paper-aligned median critical burden. Baseline and less-inert calculations use the five validated phases: PDMS, polyacrylate (PA), polyoxymethylene (POM), polyethylene/LDPE (PE), and polyurethane (PU). Reactive-toxicant predictions are disabled. Table S6 plastics are hypothesis-generating evidence only.

## Optional EPA and UFZ evidence

With a personal EPA key, the app can retrieve exact CompTox identity, detailed molecular weight, logKow evidence, and the EPA TEST 96-hour fathead-minnow LC50 property. Experimental-reference and QSAR-predicted values remain separate and are displayed in mmol/L. ECOTOX links support study-level review.

CompTox evidence is optional: the direct plastic-burden calculation remains local and does not require the API. The app never writes the key to data or exports. For Abraham solute descriptors, the interface links to the [UFZ-LSER database](https://www.ufz.de/lserd/).

## Run locally

Python 3.11 or newer is recommended.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

On Windows, `START_WORKBENCH.bat` activates `.venv` when present and starts the app.

To enable CompTox, copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`, replace the example value with your personal key, and reload the app. Never commit the real secrets file.

## Reproduce and test

Place the original `ci4c00574_si_002.xlsx` one directory above the repository, then rebuild the normalized tables:

```powershell
python scripts/build_normalized_data.py
```

Install development requirements and run both automated suites:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest
python scripts/release_audit.py
```

See [SCIENTIFIC_VALIDATION.md](SCIENTIFIC_VALIDATION.md) for equation-level acceptance calculations, [DATA_PROVENANCE.md](DATA_PROVENANCE.md) for data decisions, and [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md) for publication steps.

## Deploy and archive

Release `v1.2.0` is archived at [10.5281/zenodo.21923165](https://doi.org/10.5281/zenodo.21923165). Cite the evolving software project with the all-versions concept DOI [10.5281/zenodo.21923164](https://doi.org/10.5281/zenodo.21923164).

For hosted use, deploy `app.py` from the public repository and add `COMPTOX_API_KEY` only in the hosting platform's secrets manager. The dashboard remains usable without an API key, but live CompTox retrieval is then unavailable.

## Licensing

Original source code is MIT licensed. Normalized scientific tables retain attribution to the paper's supporting information and are not relicensed by the code license. See [NOTICE](NOTICE).
