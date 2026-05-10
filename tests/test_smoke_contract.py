import test_system


def test_smoke_endpoints_are_reusable_test_data():
    assert isinstance(test_system.ENDPOINTS, dict)
    assert "/api/health" in test_system.ENDPOINTS.values()
    assert "/api/macro/decision" in test_system.ENDPOINTS.values()


def test_smoke_runner_returns_structured_results():
    assert callable(test_system.run_endpoint_checks)
