# Lemon — TODO

## Feature Gaps (vs Rust kiss)

- [ ] **`mimic` command** — write generated .kissconfig to a file (`--out` option), not just stdout like `clamp`
- [ ] **`viz --zoom`** — graph coarsening via Leiden community detection for large dependency graphs
- [ ] **`show-tests` coverage map** — list *which specific test functions* cover each definition (not just tested/untested)

## Performance

- [ ] **Incremental caching** — cache parse trees and metrics to avoid re-analyzing unchanged files

## Polish

- [x] **`stats --all` without `=`** — split into `--all` (flag=10) + `--top N`
- [x] **Graph edges** — fixed relative import resolution (`.models` → `lemon.models`)
- [ ] **Test coverage gate** — currently disabled in .kissconfig; add real tests to reach 90%
