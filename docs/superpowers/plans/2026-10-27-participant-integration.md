# Participant Integration Implementation Plan

> **For agentic workers:** Inline execution. User approved local integration and deferred all live tests to tomorrow. Do not connect to the server or run tests/model calls in this work.

**Goal:** Connect the existing Agent №2 to the provided FastAPI backend and Catalog/RAG modules while using the current real datasets.

**Architecture:** Preserve the existing agent package. Add the participant API and catalog modules, keep the Agent BGE-M3 implementation at `rag/embeddings.py`, and rename the Catalog embedding adapter to `rag/provider.py`. Normalize records and filters in a boundary adapter, then inject a shared CatalogGateway/AgentOrchestrator into FastAPI.

**Tech Stack:** Python, FastAPI, Pydantic, SQLAlchemy, Ollama SDK, pandas, NumPy, FAISS.

**Spec:** `docs/superpowers/specs/2026-10-27-participant-integration-design.md`; user brief: attached integration TЗ.

## Global Constraints

- Existing Agent №2 remains authoritative; do not replace its QueryParser or LLMClient.
- Never hardcode credentials or a server address; use server-provided environment configuration, including `OLLAMA_URL`.
- Do not equate unknown prices, amenities, dates, or availability with confirmed values.
- Do not present derived hotel metadata as reviews.
- Keep real hotel IDs from `hotel_key` and preserve source provenance.
- Do not alter source CSVs, contact the server, install models, or run tests today.

## Review Focus

- `hotel_key` stability and latest CSV priority → inspect importer/provider mapping.
- Unknown hotel prices with a user budget → keep such results but mark budget match unconfirmed.
- Unknown required amenities → exclude as unverified, never infer from semantic similarity.
- RAG index/adapter → maintain 1024 dimension and explicit derived-not-review provenance.
- API serialization → retain old fields while returning transport and nested hotel evidence.

---

### Task 1: Add the catalog and API packages

**Files:** Add backend/catalog, backend/api, backend/contracts, backend/core, backend/sessions, backend/services, checkout, and catalog import/index scripts from the provided archives. Do not overwrite `backend/app/agent/` or the current `backend/app/catalog/rag/embeddings.py`. Store catalog embedding abstractions in `backend/app/catalog/rag/provider.py` and update imports.

- [x] Copy only source modules and required text metadata; do not copy archive demo hotel JSON over the current dataset.
- [x] Resolve duplicate `normalize_city` so alias-file loading remains active.

### Task 2: Connect current datasets and normalize Catalog ↔ Agent

**Files:** Add/configure Catalog CSV import for `datasets/hotels-russia-for-agent.csv`, `flights_ru.csv`, `buses_full.csv`, and `cities.csv`; add `backend/app/agent/tools/catalog_adapter.py`; update Agent tool registration and ranking only where required.

- [x] Preserve `hotel_key`, QC city fields, coordinates, source, unknown price and unknown availability.
- [x] Translate Agent filters to Catalog filters without claiming unsupported dates/guests.
- [x] Allow unknown-price results under a stated budget with an explicit warning; keep confirmed prices within budget.
- [x] Make required amenity matching evidence-based.
- [x] Add bounded transport search through the registered tool path.

### Task 3: Wire FastAPI to the existing Agent

**Files:** Add API/backend files from the backend archive; replace its `agent_service.py` demo behavior with a shared AgentOrchestrator instance; extend ChatResponse/HotelCard compatibly; wire real status in health.

- [x] Preserve session and message persistence.
- [x] Preserve existing HTTP response fields and add `transport_options` plus location, stars, amenities, price/availability, source, and `is_demo` where available.
- [x] Set Ollama access only via environment; server deployment defaults to loopback Ollama as specified in its launch config.

### Task 4: Connect offline RAG and document tomorrow's run

**Files:** `backend/app/catalog/rag/{documents,provider,indexer,retriever,store}.py`, index build script, requirements and setup documentation.

- [x] Build from current normalized hotel records and keep the build offline, outside HTTP requests.
- [x] Mark metadata-derived chunks as `derived`; leave real-review retrieval empty in the absence of a review source.
- [x] Document commands to import data, build the index, launch API, and run tomorrow's server checks.

### Task 5: Handoff without running today's tests

- [ ] Review changed files and show the exact server-side test/run commands for tomorrow; do not execute them in this work.
