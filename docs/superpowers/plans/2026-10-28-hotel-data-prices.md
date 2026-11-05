# Hotel dataset enrichment and price references Implementation Plan

> **For agentic workers:** Implement inline in the user's current local project folder, task-by-task. Write failing tests before production code.

**Goal:** Merge the supplied hotel metadata and price archives into the catalog, maximize useful hotel attributes and price coverage, verify locally, then deploy and validate only inside the previously authorized server project folder.

**Architecture:** A streaming preparation utility converts the large mixed-country archive and UTF-8 price archive into compact, deterministic, source-preserving JSONL artifacts. The catalog importer merges only high-confidence identities and keeps uncertain records as separately identified source records; legacy prices remain reference observations and never become canonical bookable prices. RAG receives descriptive metadata, not volatile prices or fabricated reviews.

**Tech Stack:** Python 3.13, stdlib `zipfile`/`csv`/`json`/`hashlib`, existing catalog JSON, pytest.

**Spec:** User request in this Codex task; captured in `.planning/2026-10-28-hotel-data-prices/findings.md`.

## Global Constraints
- Work locally in `C:\Users\user\Desktop\хакатон` until local checks pass.
- Do not touch weather/climate or transport.
- Do not access or modify files outside the server project directory `Островок хак`.
- Never treat a price with unknown currency/date/guest/stay basis as current or filterable.
- Preserve source provenance and factual distinction between hotel descriptions and guest reviews.

## Review Focus
- A price-only row must not pass as a current affordable offer; test that reference prices do not populate `price` or affect `price_min`/`price_max`.
- Same-name hotels in different cities or repeated rows must not be collapsed; test city disambiguation and stable source IDs.
- UTF-8 BOM/whitespace headers and malformed/missing coordinates must not crash or silently corrupt the import; test these and missing fields.
- A full all-country 2.4 GB CSV must be processed without loading the whole file in memory; test streaming behavior with fixtures and run the real conversion.
- Source descriptions and amenities must enter RAG with provenance; prices and descriptions must not be mislabeled as reviews or embedded as transient rates.

---

### Task 1: Prepare compact, deterministic source artifacts

**Files:**
- Create: `scripts/prepare_hotel_enrichment.py`
- Create: `tests/catalog/test_prepare_hotel_enrichment.py`
- Create: `datasets/hotel_enrichment/booking_hotels_ru.jsonl.gz`
- Create: `datasets/hotel_enrichment/hotel_price_references.jsonl.gz`

**Interfaces:**
- `prepare_booking_hotels(source_zip: Path, output_gz: Path) -> dict[str, int]`
- `prepare_price_references(source_zip: Path, output_gz: Path) -> dict[str, int]`
- Input paths are CLI arguments; rows are read from ZIP members as streams. Output records preserve source row number and stable source identity.

- [ ] Write tests for RU filtering/header whitespace/coordinate parsing; UTF-8 BOM handling; numeric/boolean parsing; stable IDs; and missing price context.
- [ ] Run focused tests and confirm the expected failures.
- [ ] Implement the preparation functions with streaming CSV reads and explicit per-record provenance.
- [ ] Run focused tests to green.
- [ ] Convert the real user archives; verify row counts, output sizes, and sample records.

### Task 2: Merge metadata and price observations into the catalog

**Files:**
- Modify: `scripts/import_data.py`
- Create: `scripts/hotel_enrichment.py`
- Create: `tests/catalog/test_hotel_enrichment_merge.py`
- Modify: `tests/catalog/test_import_manifest.py`

**Interfaces:**
- `load_prepared_hotel_sources(base_hotels: list[dict], source_dir: Path) -> tuple[list[dict], dict[str, int]]`
- A price reference stores amount/raw value and provenance, while currency, check-in/out, guest count, room count, and rate basis remain null/unknown. It does not write canonical `price` or Agent `total_price`.
- Deterministic strong identity matching is exact normalized name plus verified locality and, when both coordinates exist, distance <=50m; ambiguous matches stay separate and carry candidate-link metadata.
- Price-only rows remain separate source records unless a unique exact-name + verified-Saint-Petersburg match exists; never collapse the 410 repeated price-source names by name alone.
- The 29 cross-archive exact-name overlaps inspected so far include conflicting cities, so cross-archive linking requires verified matching city and uniqueness.

- [ ] Write tests for exact strong match enrichment; unsafe near-only/name-only non-match; repeat price rows preserved; unknown price context; and no cross-city merge.
- [ ] Run focused tests and confirm the expected failures.
- [ ] Implement the merge and integrate counts/source limitations in `build_manifest`.
- [ ] Run focused tests to green.

### Task 3: Improve descriptive RAG coverage and preserve price safety

**Files:**
- Modify: `backend/app/catalog/rag/documents.py`
- Create: `tests/catalog/test_rag_hotel_enrichment.py`
- Modify: `tests/catalog/test_find_offers.py`

- [ ] Test that real description/facility/attraction text enters derived RAG chunks with source metadata and explicit non-review labeling.
- [ ] Test that price references are excluded from RAG text and cannot satisfy canonical `require_price` or budget filters.
- [ ] Ensure the Agent's comparison response retains price observations under an explicit “unverified reference” structure rather than exposing them as `price`.
- [ ] Implement the minimal text enrichment and regression protections.
- [ ] Run affected catalog/RAG tests.

### Task 4: Run local verification and quality review

**Files:**
- Modify: `.planning/2026-10-28-hotel-data-prices/progress.md`
- Modify: `.planning/2026-10-28-hotel-data-prices/findings.md`

- [ ] Rebuild normalized data and confirm counts/duplicate candidates/reference-price coverage.
- [ ] Run `python -m pytest tests -q` and catalog/RAG smoke scripts.
- [ ] Review changed files, generated catalog size, and no weather/transport modifications.
- [ ] Document any price/identity limitations and exact local test output.

### Task 5: Deploy and test only within the authorized server project

**Files:**
- Modify only files under server-root `Островок хак`.

- [ ] Inspect remote path and version read-only; verify it resolves to the project directory before any write.
- [ ] Transfer only changed code, tests/docs as needed, compressed prepared source artifacts, and regenerated catalog files required by runtime.
- [ ] Run relevant tests and `scripts/smoke_catalog.py` remotely, recording exact counts/results.
- [ ] Verify remote write paths remained inside the authorized project directory and report results.
