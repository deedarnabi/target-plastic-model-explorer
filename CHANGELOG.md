# Changelog

All notable changes to this project are documented here.

## Unreleased

### Fixed

- Made release-data hashes invariant to Windows and Linux text line endings.
- Added explicit cross-platform line-ending rules for source, data, and launcher files.

## [1.2.0] - 2026-08-13

### Added

- A unified default assessment workspace for single chemicals and compatible mixtures.
- Direct calculation of component TU, mixture TU, plastic-phase PNEC equivalents, and RQ from measured plastic or passive-sampler burdens.
- Integrated CompTox identity, molecular weight, logKow, and EPA TEST 96-hour fathead-minnow evidence with explicit provenance labels.
- A visibly separate water-column pathway requiring a plastic-water partition coefficient.
- Editable environmental-scale PAH examples, unit-normalization graphics, and downloadable calculation records.
- Independent scientific acceptance tests, a release-audit command, and a source-to-code validation report.

### Changed

- Reorganized navigation around the direct `Cplastic / median Ccrit` workflow; chemical-specific LC50 and `Kplastic-water` are optional follow-up evidence.
- Standardized calculation outputs on mmol/kg plastic, mmol/L water, and dimensionless TU/RQ, while preserving original reported units in exports.
- Updated the landing design and scientific graphics to emphasize the paper's critical-plastic-burden hypothesis.
- Updated software citation and Zenodo metadata for Deedar Nabi, ORCID 0000-0002-0188-0404.
- Documented the paper/workbook reactive-burden unit discrepancy and retained the reactive prediction lockout.

## [1.1.0] - 2026-08-08

### Added

- Rule-based applicability-domain reporting for ionization, toxic-mode confidence, phase validation, log-K range, and partition-method provenance.
- Partition inputs from measured log K, documented one-parameter logKow LFERs, Abraham descriptors, and other documented prediction methods.
- Validation filters for hydrophobicity, observed toxicity, chemical class, ECOSAR class, and descriptor source, plus residual, class, and outlier diagnostics.
- Chemical-level critical-burden distributions with percentiles, IQR outliers, class context, and downloadable records.
- Polymer-selection assistant separating predictive accuracy, chemical enrichment, passive-sampling, passive-dosing, and qualitative material considerations.
- Multi-sample field-mixture processing with qualifiers, nondetect substitution, metadata, component contributions, and sample-level PNEC/RQ summaries.
- Passive-dosing experiment designer with polymer-loading tables and an explicitly illustrative dose-response curve.
- Fish-only CompTox workspace with exact identity resolution, direct EPA WebTEST 96-hour fathead-minnow values, ECOTOX links, and matching paper records.

### Changed

- Retained the median critical-burden method as the sole operational TPM estimator.
- Retained the paper-directed PNEC and RQ terminology and assessment-factor workflow.
- Strengthened warnings for exploratory other-plastic evidence.

### Deferred

- HC5/SSD, multispecies TPM, quantitative equilibration confidence, and weathered-plastic calibration remain future research directions.

## [1.0.0] - 2026-08-08

### Added

- Single-chemical TPM prediction from published values, measured log K, or Abraham descriptors.
- Mode-aware critical-burden registry with reactive prediction lockout.
- Mixture toxic-unit screen with mass-to-molar conversions and compatibility confirmation.
- Polymer atlas for validated, reference, exploratory, and out-of-domain evidence.
- Record-level validation laboratory with comparator-model diagnostics.
- Optional read-only CompTox identity lookup plus WebTEST and ECOTOX evidence links.
- Source hashing, unit audit, data downloads, citation metadata, and Zenodo release metadata.
