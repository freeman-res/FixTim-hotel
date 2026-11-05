from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.catalog.transfers.osrm import OsrmTransferRouter


def main() -> int:
    route = OsrmTransferRouter().route((55.6062, 49.2787), (55.7903, 49.1125))
    if not route:
        print("FAIL: OSRM route unavailable")
        return 1
    if not (15 < route["distance_km"] < 50 and 15 < route["duration_minutes"] < 120):
        print("FAIL: OSRM returned an unexpected route")
        return 1
    print(f"PASS: OSRM {route['distance_km']} km, {route['duration_minutes']} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
