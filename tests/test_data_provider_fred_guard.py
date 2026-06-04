import time
from urllib.error import HTTPError

import pandas as pd

import core.data_providers as dp


class _Response:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def read(self) -> bytes:
        return self.body


def _series(name: str = "DGS10") -> pd.Series:
    return pd.Series([4.25], index=pd.to_datetime(["2026-05-29"]), name=name)


def _reset_fred_state() -> None:
    dp._provider_cache.clear()
    dp._provider_inflight.clear()
    dp._last_request_time.clear()
    dp._provider_stats["fred"].update(
        {"calls": 0, "hits": 0, "errors": 0, "last_ok": 0, "last_err": "", "avg_ms": 0}
    )
    dp._circuit["fred"].update({"state": "closed", "failures": 0, "opened_at": 0})


def test_fred_429_serves_stale_cache_without_sleep_or_retry(monkeypatch):
    _reset_fred_state()
    cache_key = "fred:DGS10:5"
    stale = _series("DGS10")
    dp._provider_cache[cache_key] = (time.time() - dp.MACRO_CACHE_TTL - 1, stale)
    monkeypatch.setattr(dp.settings, "FRED_API_KEY", "secret-fred-key", raising=False)

    urlopen_calls = []

    def fake_urlopen(req, timeout):
        urlopen_calls.append(req.full_url)
        raise HTTPError(
            url=req.full_url,
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=None,
        )

    sleep_calls = []

    def fail_on_sleep(seconds):
        sleep_calls.append(seconds)
        raise AssertionError("FRED 429 must not sleep before falling back")

    monkeypatch.setattr(dp.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(dp.time, "sleep", fail_on_sleep)

    result = dp._fred_series("DGS10", limit=5)

    assert result.equals(stale)
    assert len(urlopen_calls) == 1
    assert sleep_calls == []
    assert dp._provider_stats["fred"]["calls"] == 1
    assert dp._provider_stats["fred"]["errors"] == 1
    assert "secret-fred-key" not in dp._provider_stats["fred"]["last_err"]
    assert dp._circuit["fred"]["state"] == "open"


def test_fred_429_opens_circuit_for_follow_on_series(monkeypatch):
    _reset_fred_state()
    monkeypatch.setattr(dp.settings, "FRED_API_KEY", "secret-fred-key", raising=False)

    urlopen_calls = []

    def fake_urlopen(req, timeout):
        urlopen_calls.append(req.full_url)
        raise HTTPError(
            url=req.full_url,
            code=429,
            msg="Too Many Requests",
            hdrs=None,
            fp=None,
        )

    monkeypatch.setattr(dp.urllib.request, "urlopen", fake_urlopen)

    first = dp._fred_series("DGS10", limit=5)
    second = dp._fred_series("VIXCLS", limit=5)

    assert first.empty
    assert second.empty
    assert len(urlopen_calls) == 1
    assert dp._circuit["fred"]["state"] == "open"


def test_fred_inflight_marker_does_not_drop_cold_series(monkeypatch):
    _reset_fred_state()
    dp._provider_inflight.add("fred")

    def fake_urlopen(req, timeout):
        return _Response(
            b'{"observations":[{"date":"2026-05-30","value":"4.25"}]}'
        )

    monkeypatch.setattr(dp.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(dp.time, "sleep", lambda seconds: None)

    result = dp._fred_series("DGS10", limit=5)

    assert not result.empty
    assert result.name == "DGS10"
    assert float(result.iloc[-1]) == 4.25
    assert dp._provider_stats["fred"]["calls"] == 1


def test_fred_repeated_open_circuit_fallback_logs_once(monkeypatch):
    _reset_fred_state()
    dp._circuit["fred"].update({"state": "open", "failures": dp.CIRCUIT_FAIL_THRESH, "opened_at": time.time()})
    prints = []

    monkeypatch.setattr(dp, "_LOG_THROTTLE_S", 60)
    monkeypatch.setattr(dp, "_last_log_time", {})
    monkeypatch.setattr(dp, "print", lambda message: prints.append(message), raising=False)

    first = dp._fred_series("DGS10", limit=5)
    second = dp._fred_series("VIXCLS", limit=5)

    assert first.empty
    assert second.empty
    assert len(prints) == 1


def test_fred_open_circuit_serves_stale_cache_without_outbound_call(monkeypatch):
    _reset_fred_state()
    cache_key = "fred:DGS10:5"
    stale = _series("DGS10")
    dp._provider_cache[cache_key] = (time.time() - dp.MACRO_CACHE_TTL - 1, stale)
    dp._circuit["fred"].update({"state": "open", "failures": dp.CIRCUIT_FAIL_THRESH, "opened_at": time.time()})

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("open FRED circuit must not call the network")

    monkeypatch.setattr(dp.urllib.request, "urlopen", fail_urlopen)

    result = dp._fred_series("DGS10", limit=5)

    assert result.equals(stale)
    assert dp._provider_stats["fred"]["calls"] == 0


def test_fred_open_circuit_without_cache_returns_named_empty_series(monkeypatch):
    _reset_fred_state()
    dp._circuit["fred"].update({"state": "open", "failures": dp.CIRCUIT_FAIL_THRESH, "opened_at": time.time()})

    def fail_urlopen(*args, **kwargs):
        raise AssertionError("open FRED circuit must not call the network")

    monkeypatch.setattr(dp.urllib.request, "urlopen", fail_urlopen)

    result = dp._fred_series("DGS10", limit=5)

    assert result.empty
    assert result.name == "DGS10"
    assert dp._provider_stats["fred"]["calls"] == 0
