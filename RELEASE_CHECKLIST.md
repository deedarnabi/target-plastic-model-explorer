# Release checklist

## Completed locally

- [x] Reconstructed normalized tables from the original SI workbook.
- [x] Verified the SI workbook SHA-256 and all published cohort sizes.
- [x] Confirmed deterministic normalized output hashes.
- [x] Added equation-level scientific acceptance tests.
- [x] Verified the baseline evaluation RMSE range against the article.
- [x] Documented source-text unit/range discrepancies and application decisions.
- [x] Confirmed reactive prediction is disabled and Table S6 plastics are exploratory.
- [x] Aligned package, release, CFF, and Zenodo versions at 1.2.0.
- [x] Added Deedar Nabi's full name and ORCID to citation metadata.
- [x] Confirmed `.streamlit/secrets.toml` and temporary audit files are git-ignored.
- [x] Configured GitHub Actions to run the automated tests.

## Repository identity

- [x] Repository owner: `deedarnabi`.
- [x] Canonical URL: `https://github.com/deedarnabi/target-plastic-model-explorer`.
- [x] Privacy-preserving Git author email: `174426020+deedarnabi@users.noreply.github.com`.
- [x] Add the final `repository-code` URL to `CITATION.cff` and Zenodo metadata.

## Required before public release

- [ ] Review the dashboard wording and example values as the scientific owner.
- [x] Push the clean `main` branch to GitHub.
- [ ] Deploy `app.py` and store `COMPTOX_API_KEY` only in the hosting platform's secrets manager.
- [ ] Smoke-test every page on the deployed URL, including one successful CompTox identity/evidence retrieval.
- [ ] Confirm the app still works without an API key and produces no secret-bearing exports or logs.
- [x] Confirm the repository description, topics, license, and citation display on GitHub.
- [x] Enable the repository in Zenodo's GitHub integration.
- [x] Create and review release `v1.2.0`; verify creators, ORCID, paper DOI relation, license note, and archived files before publishing the Zenodo record.
- [x] Add the concept DOI badge and exact-release DOI identifier in a follow-up metadata commit.
