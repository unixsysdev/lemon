# Lemon — TODO

## Feature Gaps (vs Rust kiss)

- [x] **`mimic` command** — write generated .kissconfig to a file (`--out` option)
- [x] **`viz --zoom`** — graph coarsening by path-prefix depth (0.0=packages, 1.0=full)
- [x] **`show-tests` coverage map** — list *which specific test functions* cover each definition

## Performance

- [ ] **Incremental caching** — cache parse trees and metrics to avoid re-analyzing unchanged files

## Polish

- [x] **`stats --all` without `=`** — split into `--all` (flag=10) + `--top N`
- [x] **Graph edges** — fixed relative import resolution (`.models` → `lemon.models`)
- [ ] **Test coverage gate** — currently disabled in .kissconfig; add real tests to reach 90%
