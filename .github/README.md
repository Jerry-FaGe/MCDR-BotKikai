# CI and releases

## CI

- Runs on pushes to `master`, pull requests, and manual dispatches. Feature
  branches use PR checks or manual dispatch to avoid duplicate push/PR runs.
- Checks Python syntax, example JSON, and the supported MCDR/Python matrix.
- Before the regression suite is committed, explicitly reports its absence.
  Once `tests/` exists, pytest failures (including zero collected tests) fail CI.
  Missing `tests/` also fails if `pytest.ini` or `requirements-dev.txt` exists.
- Builds one package on Linux with Python 3.14 and MCDR 2.16.2, verifies every
  archived file against the checkout, and uploads it with `SHA256SUMS` for 7 days.
  The package allowlist is plugin Python files, metadata, and `LICENSE`; update
  the verification step if runtime resources are added in the future.
- Pins Actions to commit SHAs; Dependabot groups monthly Action updates into a PR.
  The MCDR matrix versions are deliberate compatibility baselines, updated manually.

## Releases

- Push a `v*.*.*` tag matching `v` plus the version in `mcdreforged.plugin.json`.
- Reuses CI on the tagged revision. Only after the whole matrix passes does the
  publish job download and publish the same verified package; it never rebuilds it.
- Generates commit-based notes from the full local Git history, without API calls.
- Tags with a prerelease suffix (before any `+` build metadata) create prereleases.
- Only the publish job has repository write permission. Tag runs are not canceled
  by newer CI runs. No custom repository secret is needed.
- Rerunning failed jobs reuses the artifact from the same run. If it has expired,
  rerun all jobs to rebuild it. Replacing already-published assets is subject to
  the repository's release-immutability settings.

## Two-commit rollout

1. Commit only `.github/` first. This is self-contained on the old plugin revision:
   it does not require the pending plugin fixes, dev requirements, or pytest config.
2. Push that commit to `master` (or open a PR) and inspect CI and its package artifact.
3. Commit the plugin fixes, tests, dev requirements, pytest config, and other docs.
   Push again: the same CI now runs the regression suite automatically.
4. To test publishing, bump the plugin version and push a matching new tag. An
   ordinary commit only tests CI; it does not create a GitHub Release. Do not move
   an existing release tag to test the workflow.
