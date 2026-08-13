# Scientific validation record

Release: **1.2.0**

Audit date: **2026-08-13**

## Decision

The dashboard's baseline and less-inert direct calculations are faithful to the paper equations and the normalized supporting workbook. They are suitable for transparent research screening within the stated applicability domain. Reactive-toxicant prediction remains disabled. The result is not a regulatory validation or a claim of prospective field performance.

## Audited sources

- Main article: Nabi, Beck, and Achterberg (2024), DOI [10.1021/acs.jcim.4c00574](https://doi.org/10.1021/acs.jcim.4c00574).
- Narrative supporting information: `ci4c00574_si_001.pdf`.
- Data supporting information: `ci4c00574_si_002.xlsx`.
- Expected SI-workbook SHA-256: `c6a7637d78cc92b5e043e296f3f59a023743168cd8a02375419455312faf4e2b`.

The paper and SI files are held outside the public repository. The data normalizer rebuilt all five committed normalized outputs from the SI workbook byte-for-byte before this release audit.

## Source-to-code traceability

| Scientific element | Source location | Application implementation | Acceptance evidence |
|---|---|---|---|
| `Kplastic-water = Cplastic / Cwater` | Article Eq. 4 | Optional water-to-plastic conversion | 1 ng/L naphthalene with logK 3 gives `7.8021256e-6 mmol/kg` |
| `Ccrit,plastic = LC50 * Kplastic-water` | Article Eqs. 5-6 | Optional LC50/mechanistic investigation | Unit and round-trip tests |
| `TU = Cplastic / Ccrit,plastic` | Article Eq. 8 | Direct single-component calculation | Independent naphthalene hand calculation |
| `TUmixture = sum(TUi)` | Article Eqs. 9-10 | Compatible-mixture calculation | Three-component POM test |
| `RQ = TUmixture * AF` | Article Eq. 11 | Single and mixture risk screen | Algebraic equality to `Cplastic/PNECplastic,equivalent` |
| Median critical burden | Article methods/discussion and SI Tables S1-S5 | Sole operational TPM denominator | Ten phase/mode checkpoint tests |
| AF 1,000 freshwater; 10,000 marine | Article page 6502 | Preset assessment factors | Core PNEC tests |

## Independent calculation checkpoints

### Direct plastic measurement

For an illustrative 10 ng/g naphthalene measurement on PDMS, molecular weight 128.1702 g/mol:

```text
10 ng/g = 0.010 mg/kg
Cplastic = 0.010 / 128.1702 = 7.8021256e-5 mmol/kg
PDMS baseline median Ccrit = 36.5964450 mmol/kg
TU = 2.1319354e-6
PNECplastic,equivalent (AF 1000) = 0.0365964450 mmol/kg
RQ = 0.0021319354
```

This example verifies unit normalization and equation equivalence; it is not presented as an environmental benchmark concentration.

### Compatible mixture

For three POM baseline components at 0.1, 0.2, and 0.3 mmol/kg, with median `Ccrit = 19.2007415 mmol/kg` and AF 1,000:

```text
TUmixture = (0.1 + 0.2 + 0.3) / 19.2007415 = 0.0312487932
PNECplastic,equivalent = 19.2007415 / 1000 = 0.0192007415 mmol/kg
RQ = 31.2487932
```

## Reproduced data checks

- Cohorts: 115 baseline evaluation, 132 baseline validation, 73 less-inert evaluation, 128 less-inert validation, and 75 reactive evaluation records.
- Other-plastic evidence: 59 Table S6 records.
- Baseline plastic evaluation RMSE range: 0.311-0.538 log unit after rounding, matching the article abstract.
- Baseline median plastic burdens: 0.1655-51.3278 mmol/kg.
- Less-inert median plastic burdens: 0.04416-26.6227 mmol/kg.
- Reactive plastic records: retained only as out-of-domain evidence; operational calculation is locked.

## Source discrepancies and decisions

### Reactive burdens

The paper defines the regression intercept and SI columns as `-log10 Ccrit (mol/kg)`. Inverting those values and multiplying by 1,000 gives reactive plastic medians of **0.001001-0.678054 mmol/kg**. The reactive range printed in the article is exactly 1,000-fold lower. The app retains the equation- and workbook-consistent conversion, displays the discrepancy, and disables reactive prediction.

### Less-inert range

Article page 6499 prints a five-plastic range of 0.04-6.90 mmol/kg but then reports PA at 26.6 mmol/kg. The abstract and SI workbook agree with 0.04-26.6 mmol/kg. The app uses the SI-derived PA value.

## Reproduce the audit

```powershell
python -m pytest
python scripts/release_audit.py
```

If the SI workbook is present one directory above the repository, the audit also verifies its identity. A public clone without the source workbook reports that check as skipped rather than silently substituting another source.
