# RZD Train Provider Design

## Intent

The current catalog intentionally returns no trains because the supplied datasets contain air and bus data but no railway source. Add a bounded online provider using `rzd-api==3.1.0` so a `type=train` request can query ticket.rzd.ru through the existing Agent tool and CatalogGateway path.

## Goals

- Search direct trains for one explicit departure date and two cities/stations.
- Convert RZD results into the existing transport option shape without changing plane or bus behavior.
- Preserve train number, station names, local departure/arrival times, minimum price, reported places, source, and response completeness where supplied.
- Distinguish missing/ambiguous station input from an upstream outage; never report an outage as a confirmed empty search.
- Apply bounded network and retry limits and, only if needed, a per-tool timeout for `search_transport`; keep the global 30-second timeout unchanged.
- Add offline tests with a fake RZD client and perform one live probe only from the local laptop if its current network can reach RZD.

## Non-goals

- No transfers, return trips, booking, or ticket purchase.
- No use of train records in the static catalog and no fake fallback trains.
- No changes to hotel search, Backend contracts, the Llama model, BGE implementation, or RAG behavior as part of the RZD feature.
- No connection to or changes on either server.

## Constraints and decisions

- Use the existing `search_transport` tool and `CatalogGateway.find_transport` boundary.
- Route to RZD only when the normalized transport type is `train`; other searches remain on the JSON catalog.
- A concrete `date_from` is mandatory; the initial version accepts a single date only.
- Treat `partial` from `search_tickets_detailed` as a warning, not as a complete inventory.
- Do not disable TLS verification. Classify invalid/ambiguous station input separately from network, HTTP, API, and schema failures.
- Keep all work and generated artifacts local. Do not build a full 30,555-hotel vector index on the laptop.

## Open implementation details

- Confirm exact exception classes and dataclass fields from the pinned package before writing the adapter.
- Bound the end-to-end tool timeout against the RZD client timeout/retry configuration; do not raise the global timeout.
- Keep the live RZD request opt-in and avoid running it in unit tests.
