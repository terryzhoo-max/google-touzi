import test_system


def test_smoke_endpoints_are_reusable_test_data():
    assert isinstance(test_system.ENDPOINTS, dict)
    assert "/api/health" in test_system.ENDPOINTS.values()
    assert "/api/macro/decision" in test_system.ENDPOINTS.values()
    assert "/api/institutional/decision" in test_system.ENDPOINTS.values()
    assert "/api/institutional/policy" in test_system.ENDPOINTS.values()


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {"status": "ok"}

    def json(self):
        return self._payload


def test_smoke_runner_returns_structured_results_without_network():
    calls = []

    def fake_get(url, timeout):
        calls.append((url, timeout))
        return FakeResponse(payload={"endpoint": url})

    results = test_system.run_endpoint_checks(
        base_url="http://testserver",
        timeout=3,
        get=fake_get,
        endpoints={"Health": "/api/health", "Policy": "/api/institutional/policy"},
    )

    assert [result.name for result in results] == ["Health", "Policy"]
    assert all(result.ok for result in results)
    assert results[0].status_code == 200
    assert results[0].payload == {"endpoint": "http://testserver/api/health"}
    assert calls == [
        ("http://testserver/api/health", 3),
        ("http://testserver/api/institutional/policy", 3),
    ]


def test_smoke_runner_marks_logic_error_as_failed_without_network():
    def fake_get(url, timeout):
        return FakeResponse(payload={"error": "downstream unavailable"})

    result = test_system.check_endpoint(
        "http://testserver",
        "Broken",
        "/api/broken",
        timeout=3,
        get=fake_get,
    )

    assert result.ok is False
    assert result.error == "Logic Error: downstream unavailable"
