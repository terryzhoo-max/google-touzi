from urllib.error import HTTPError, URLError

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


def test_http_get_keeps_bounded_retry_for_non_rate_limit_errors(monkeypatch):
    attempts = []

    def fake_urlopen(req, timeout):
        attempts.append(req.full_url)
        if len(attempts) < 3:
            raise URLError("temporary connection reset")
        return _Response(b"ok")

    sleeps = []
    monkeypatch.setattr(dp.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(dp.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = dp._http_get("https://example.test/data", retries=3, stop_on_rate_limit=True)

    assert result == b"ok"
    assert len(attempts) == 3
    assert sleeps == [1, 2]


def test_http_get_stops_immediately_on_rate_limit_when_enabled(monkeypatch):
    attempts = []

    def fake_urlopen(req, timeout):
        attempts.append(req.full_url)
        raise HTTPError(req.full_url, 429, "Too Many Requests", None, None)

    sleeps = []
    monkeypatch.setattr(dp.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(dp.time, "sleep", lambda seconds: sleeps.append(seconds))

    try:
        dp._http_get("https://example.test/fred", retries=3, stop_on_rate_limit=True)
    except HTTPError as exc:
        assert exc.code == 429
    else:
        raise AssertionError("expected HTTPError 429")

    assert len(attempts) == 1
    assert sleeps == []


def test_http_post_keeps_bounded_retry_for_tushare_transient_errors(monkeypatch):
    attempts = []

    def fake_urlopen(req, timeout):
        attempts.append(req.full_url)
        if len(attempts) < 2:
            raise URLError("temporary post failure")
        return _Response(b'{"data":{"items":[]}}')

    sleeps = []
    monkeypatch.setattr(dp.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setattr(dp.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = dp._http_post("https://api.tushare.pro", b"{}", retries=2)

    assert result == b'{"data":{"items":[]}}'
    assert len(attempts) == 2
    assert sleeps == [1]
