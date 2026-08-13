# Version 1.2.0 release notes

Version 1.2.0 makes the paper's central analytical claim the dashboard's primary workflow: an analyst can normalize a measured plastic-associated concentration to the phase- and toxic-mode-specific median critical plastic burden and calculate toxic units without first obtaining a chemical-specific fish LC50 or plastic-water partition coefficient.

The default assessment workspace now supports both single chemicals and compatible mixtures. It reports component TU, summed mixture TU, the plastic-phase PNEC equivalent, RQ, component contributions, unit-conversion steps, and downloadable calculation records. Water-column measurements follow a separately labeled pathway because converting them to a plastic-equivalent burden requires `Kplastic-water`.

CompTox evidence is integrated into the workflow rather than presented only as external links. Exact identity, molecular weight, logKow summaries, and EPA TEST 96-hour fathead-minnow experimental-reference and predicted values are shown in common molar units with their provenance and applicability-domain labels. These values support identification, unit conversion, and optional mechanistic investigation; they do not silently replace the TPM median endpoint.

Scientific safeguards retained in this release:

- reactive-toxicant prediction is disabled;
- Table S6 plastics remain exploratory and excluded from operational calculation;
- compatible mixture addition requires a shared phase and justified toxic mode;
- validation RMSE is an empirical cohort statistic, not a calibrated uncertainty interval;
- the passive-dosing response curve is illustrative rather than fitted biological data; and
- HC5/SSD, multispecies calibration, quantitative equilibrium confidence, and weathered-plastic calibration remain outside this release.

The release audit reconstructs the normalized data from the original SI workbook without changing any output hashes, checks the paper equations against independent hand calculations, and documents two source-text inconsistencies. Most importantly, reactive `-log10(mol/kg)` values invert to burdens 1,000-fold higher in mmol/kg than the paper's reactive-burden prose reports. The app uses the equation- and workbook-consistent conversion, labels the discrepancy, and keeps reactive prediction disabled.

Before public release, push the prepared repository, run the deployment smoke test with the CompTox secret configured in the hosting platform, and review the Zenodo draft before publishing it.
