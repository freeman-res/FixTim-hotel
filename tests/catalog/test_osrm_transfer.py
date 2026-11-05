from backend.app.catalog.transfers.osrm import OsrmTransferRouter


def test_osrm_route_is_cached_and_estimate_is_labeled(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"code": "Ok", "routes": [{"distance": 27900, "duration": 3180}]}

    def fake_get(*args, **kwargs):
        calls.append(args)
        return Response()

    monkeypatch.setattr("backend.app.catalog.transfers.osrm.httpx.get", fake_get)
    router = OsrmTransferRouter()
    first = router.route((55.606, 49.279), (55.79, 49.12))
    second = router.route((55.606, 49.279), (55.79, 49.12))
    assert first == second
    assert len(calls) == 1
    assert first["distance_km"] == 27.9
    assert first["duration_minutes"] == 53
    assert first["price_estimate_rub"] > 0


def test_osrm_failure_does_not_make_up_a_route(monkeypatch):
    def fail(*args, **kwargs):
        raise TimeoutError()

    monkeypatch.setattr("backend.app.catalog.transfers.osrm.httpx.get", fail)
    assert OsrmTransferRouter().route((55.606, 49.279), (55.79, 49.12)) is None
