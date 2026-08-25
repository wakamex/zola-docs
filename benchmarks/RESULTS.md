# Version tombstone results

Retrieved on 2026-08-25. Rust snapshots use immutable Rust 1.70.0, 1.90.0, and 1.98.0 documentation.
Django uses ten English documentation versions from 2.2 through 5.2.

| Site | Versions | Unique routes | Existing HTML pages | Tombstones | File-count increase | Estimated raw overlay |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Rust Book | 3 | 130 | 329 | 61 | 18.5% | 298,717 B |
| Cargo Book | 3 | 100 | 280 | 20 | 7.1% | 97,940 B |
| Rust Reference | 3 | 119 | 346 | 11 | 3.2% | 53,867 B |
| Django documentation | 10 | 857 | 6,437 | 2,133 | 33.1% | 10,445,301 B |

The raw overlay estimate uses a 4,897-byte rendered 404 shell for every tombstone. It does not
include compression or shared-storage deduplication. The benchmark measures route-set growth, not
network transfer: a user downloads at most one tombstone page after following a missing versioned
route.
