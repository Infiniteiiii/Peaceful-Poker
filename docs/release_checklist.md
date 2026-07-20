# Peaceful Poker 1.1.0 Release Checklist

- [x] Install editable development and build extras
- [x] Pass 228 baseline tests with `-p no:cacheprovider` before release work
- [x] Pass 231 final tests with `-p no:cacheprovider` after release work
- [x] Pass Ruff format and lint checks
- [x] Pass strict Mypy across 42 source files
- [x] Pass `pip check`
- [x] Launch both source entry points
- [x] Run required action-aware Quick and Standard benchmarks
- [x] Automate acceptance scenarios A through D
- [x] Verify version-1 save migration and schema-version-2 round trips
- [x] Verify raw showdown equity and action-aware EV remain separate in the UI and exports
- [x] Generate and inspect SVG, PNG, and ICO artwork
- [x] Build `dist\Peaceful Poker\Peaceful Poker.exe`
- [x] Run independent packaged raw/action-aware smoke analysis and save verification
- [x] Confirm release metadata, CI workflow, documentation, and clean stale-content search
- [x] Rebuild the final one-folder application and pass the expanded packaged smoke test twice
- [x] Launch a copied one-folder build outside the repository with Qt variables cleared
- [x] Create, extract, smoke-test, and checksum the versioned portable ZIP
- [ ] Build and checksum the Inno Setup installer when Inno Setup 6 is available

Measured action-aware benchmark times on the release machine (Python 3.14.6, Windows 11) were:

- Six-player hero last, Quick: 16.6277 seconds
- Six-player one behind, Quick: 15.9471 seconds
- Six-player three behind, Quick: 16.4946 seconds
- Ten-player table, Quick: 30.4666 seconds
- Six-player hero last, Standard: 61.5094 seconds

The application runs these estimates in a cancellable worker thread. Runtime depends on the table,
candidate count, entered ranges, and hardware; Quick remains the default preset.
