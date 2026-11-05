# RZD Train Provider Implementation Plan

> **For agentic workers:** Inline execution using the approved local-only scope. No server connection or server modification.

**Goal:** Add direct RZD train search to the existing transport tool while leaving other transport and hotel paths unchanged.

**Architecture:** A lazy `rzd_provider` translates RZD client results into Catalog transport dictionaries. `TransportService` dispatches only `type=train` to it; the existing JSON-backed path continues handling air and bus results. The Agent tool turns missing/ambiguous input into clarification and upstream failures into an explicit unavailable-source result. Any longer timeout is scoped to `search_transport` only.

**Tech Stack:** Python, FastAPI project contracts, Pydantic, `rzd-api==3.1.0`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-28-rzd-train-provider-design.md`

## Global Constraints

- Work and test locally only; do not connect to or modify the server.
- Use a single departure date and direct routes only.
- Do not treat unknown or partial data as confirmed inventory.
- Keep the global `ToolExecutor` timeout at 30 seconds; override only the registered `search_transport` tool if required.
- Preserve the existing plane, bus, hotel, Backend, Llama, and BGE/RAG paths.
- Never disable TLS verification or add model/server credentials.

## Review Focus

- Missing date or invalid date → ask for a concrete travel date; do not query RZD.
- Ambiguous/not-found city or station → request clarification; do not label it an outage.
- RZD timeout/HTTP/API/schema failure → report source unavailable; do not claim no trains exist.
- Partial upstream response → include a visible completeness warning.
- RZD response with no seats, no price, or unusual time values → preserve evidence as returned and avoid inventing availability or UTC.
- Plane/bus search and non-RZD tool latency → remain on existing behavior and the global 30-second default.

---

### Task 1: Verify local package and live source access

**Files:** Local virtual environment only; no production source changes.

- [ ] Inspect existing `.venv` interpreter; do not overwrite a broken environment.
- [ ] Create/use an isolated local environment and install `rzd-api==3.1.0`.
- [ ] Run one bounded live query Moscow → Kazan for a future date with a short timeout and no retries.
- [ ] Record whether network access, station resolution, result parsing, and `partial` are available. A network block is an environment limitation, not proof that the integration is broken.

### Task 2: RZD provider conversion

**Files:**
- Create: `backend/app/catalog/transport/rzd_provider.py`
- Modify: `requirements.txt`
- Test: `tests/catalog/test_rzd_provider.py`

**Interfaces:**
- Produces: `find_rzd_trains(filters: dict) -> list[dict]`.
- Consumes: a test-injectable RZD client factory and fields confirmed from `rzd-api==3.1.0`.

- [ ] Write tests for mapped train fields, missing required date, no results, partial results, and provider failures.
- [ ] Run the focused tests and confirm they fail for the expected missing behavior.
- [ ] Implement one-date direct search; map values only from RZD response fields and attach provenance/completeness metadata.
- [ ] Pin `rzd-api==3.1.0` in the project requirements.
- [ ] Re-run focused tests and preserve the exact result/exception distinction.

### Task 3: Catalog dispatch and tool-level timeout

**Files:**
- Modify: `backend/app/catalog/transport/service.py`
- Modify: `backend/app/agent/tools/registry.py`
- Modify: `backend/app/agent/tools/executor.py`
- Modify: `backend/app/agent/tools/factory.py`
- Test: `tests/catalog/test_find_transport.py`, `tests/agent/test_additional_checks.py`

- [ ] Add a failing test that `type=train` reaches the RZD provider while bus/plane remain local.
- [ ] Add a failing test that only `search_transport` can use an explicit timeout and all other tools retain 30 seconds.
- [ ] Run those tests to verify the expected failures.
- [ ] Implement train-only lazy dispatch and a bounded `search_transport` timeout if measured RZD call bounds require it.
- [ ] Run targeted tests; do not raise the global default.

### Task 4: Agent clarification and error semantics

**Files:**
- Modify: `backend/app/agent/tools/search_transport.py`
- Modify: `backend/app/agent/orchestrator.py`
- Test: `tests/agent/test_additional_checks.py`

- [ ] Add failing tests for absent date → clarification, ambiguous station → clarification, upstream failure → error/unavailable, partial results → results plus warning.
- [ ] Run the focused tests to verify the expected failures.
- [ ] Implement deterministic status handling so LLM prose cannot turn a provider failure into `no_results`.
- [ ] Re-run focused tests.

### Task 5: Regression verification and local live probe

- [ ] Run relevant offline agent and catalog tests, then the full project test suite required by the project.
- [ ] Run one opt-in live RZD probe only if the local network reaches ticket.rzd.ru; do not call live endpoints from pytest.
- [ ] Record skipped/failed live checks explicitly; never claim the real API is integrated-and-working based only on mocks.
- [ ] Review the changed files and confirm there are no server paths, credentials, or global timeout changes.
