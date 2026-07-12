# Peaceful Poker 1.0.0 Release Checklist

- [x] Install editable development and build extras
- [x] Pass 140 tests with `-p no:cacheprovider` and no project warnings
- [x] Pass Ruff format and lint checks
- [x] Pass strict Mypy for `src`
- [x] Pass `pip check`
- [x] Launch both source entry points
- [x] Run exact and Monte Carlo benchmarks
- [x] Generate and inspect SVG, PNG, and ICO artwork
- [x] Build `dist\Peaceful Poker\Peaceful Poker.exe`
- [x] Run independent packaged smoke analysis and save verification
- [x] Confirm release metadata, CI workflow, documentation, and clean stale-content search

The standard cached Pytest run also passes all 140 tests but emits one OneDrive cache-provider
warning. OneDrive denies deletion of the stale cache path; the release verification command uses
the documented cache-independent mode and does not hide other warning categories.
