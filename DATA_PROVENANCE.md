# Data provenance and scientific decisions

## Primary source

Nabi, D.; Beck, A. J.; Achterberg, E. P. "Assessing Aquatic Baseline Toxicity of Plastic-Associated Chemicals: Development and Validation of the Target Plastic Model." *Journal of Chemical Information and Modeling* **2024**, 64, 6492-6505. DOI: [10.1021/acs.jcim.4c00574](https://doi.org/10.1021/acs.jcim.4c00574).

Local normalization source: `ci4c00574_si_002.xlsx`. Its expected SHA-256 is recorded in `data/dataset_manifest.json`. The original workbook and PDFs are not copied into the repository.

## Cohort map

| Source sheet | Dashboard cohort | Records | Role |
|---|---|---:|---|
| Table S1 | Baseline evaluation | 115 | Derivation |
| Table S2 | Baseline validation | 132 | External validation |
| Table S3 | Less-inert evaluation | 73 | Derivation |
| Table S4 | Less-inert validation | 128 | External validation |
| Table S5 | Reactive toxicants | 75 | Evidence only |
| Table S6 | Other plastics | 59 | Exploratory evidence only |

The normalizer excludes styled empty cells and copies cached source values into a stable schema. It does not impute missing values or alter chemical identity records.

## Critical burdens

For every mode and phase, the app takes the median of the source `-log10 Ccrit` column and computes:

```text
Ccrit (mol/kg)  = 10^[-median(-log10 Ccrit)]
Ccrit (mmol/kg) = Ccrit (mol/kg) * 1000
```

The median is the sole operational estimator. Chemical-level calculated burdens remain visible in the distribution explorer, but the calculator does not silently substitute them for the cohort median.

## Partition inputs and applicability domain

The optional mechanistic investigation distinguishes paper-dataset values, measured log K values, documented one-parameter logKow LFER estimates, Abraham-solvation estimates, and other documented estimates. Exports preserve the selected input type and the method/source text.

The applicability result is a transparent rule-based screen. It checks toxic mode, validated phase, neutral/ionized status, toxic-mode confidence, whether log K lies within the evaluation-cohort range, and whether a secondary method is documented. It is not a statistical leverage analysis or a probabilistic confidence interval.

Abraham-equation provenance is stored in `data/model_registry.json`. Where the archived source did not report training n, R-squared, or standard error, the app displays a missing value rather than inventing one.

## Reactive-record unit audit

The source workbook and the regression definition in the paper identify reactive critical burdens as `-log10(mol/kg)`. Applying the conversion above gives plastic-phase medians from approximately **0.001001 to 0.678054 mmol/kg**. The reactive-burden range printed in the paper's abstract and prose is exactly 1,000-fold lower, consistent with omitting the mol/kg-to-mmol/kg multiplication.

The dashboard therefore:

1. retains the equation- and workbook-consistent values;
2. converts mol/kg to mmol/kg only by multiplying by 1,000;
3. exposes this source discrepancy in the interface and validation report; and
4. independently disables reactive-toxicant predictions because specifically reactive toxicity is outside the predictive scope of a phase-partitioning critical-burden model.

The paper also states on page 6499 that the five less-inert plastic burdens range from 0.04 to 6.90 mmol/kg, then identifies PA as 26.6 mmol/kg on the same page. The abstract and SI data support the wider range, 0.04 to 26.6 mmol/kg; the app retains the SI-derived PA value.

## Evidence tiers

- `paper_validated`: PDMS, PA, POM, PE/LDPE, and PU in baseline or less-inert cohorts.
- `reference`: phospholipid and octanol comparator phases.
- `exploratory`: HDPE, polypropylene, polystyrene, PVC, and UHMWPE records from Table S6.
- `out_of_domain`: reactive calculations shown only for auditing.

## CompTox and fish toxicity

The optional connector retrieves exact identity, detailed molecular weight, logKow summaries, and the EPA TEST 96-hour fathead-minnow LC50 property. A TEST property can contain an experimental reference and a QSAR prediction; the app preserves and labels them separately with the TEST applicability-domain conclusion and reasoning. ECOTOX remains the linked source for study-level experimental review.

When an experimental TEST reference and a defensible `Kplastic-water` are both available, the optional investigation calculates a secondary chemical-specific burden as `Ccrit,plastic = LC50 * Kplastic-water`. The paper's mode-specific median burden remains the operational TPM denominator.

The published Khawar and Nabi (2021) PE/LDPE equation is labeled as published screening evidence. The PDMS, PA, POM, and PU one-parameter equations were fitted for this dashboard to paired logKow and ASM-derived partition values in the TPM supporting data. Their fit statistics and `dashboard_derived_screening` status are explicit in `data/model_registry.json`; they are not represented as published TPM equations.

## Mixture screening, PNEC, and RQ

Once a chemical is assigned to an appropriate toxic mode and measured on a validated common plastic phase, neither chemical-specific LC50 nor `Kplastic-water` is an input to the direct toxic-unit calculation. Molecular weight is used only to convert a mass-based concentration to mmol/kg.

The app implements equations 8-11 of the paper:

```text
TUi                    = Cplastic,i / Ccrit,plastic
TUmixture              = sum(TUi)
PNECplastic,equivalent = Ccrit,plastic / AF
RQ                     = TUmixture * AF
```

The default assessment factors reproduce the values cited in the paper: 1,000 for freshwater and 10,000 for marine screening. `PNECplastic,equivalent` is explicitly a screening equivalent in mmol/kg plastic, not an independently measured water-column PNEC.

Assessment-factor context is attributed to ECHA Chapter R.10 and Chapman, Fairbrother, and Brown (1998, DOI 10.1002/etc.5620170112). Mixture-risk framing follows Backhaus and Faust (2012, DOI 10.1021/es2034125), and environmental-plastic context follows Faure et al. (2015, DOI 10.1071/EN14218).

The field processor preserves sample, site, date, replicate, qualifier, detection limit, mode confidence, and result-source fields. Nondetect substitution is user-selected and exported. Film thickness and kinetic confidence are intentionally not required.
