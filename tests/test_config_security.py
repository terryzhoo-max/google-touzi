from core.config import parse_bool, parse_origins


def test_parse_origins_uses_safe_local_defaults():
    assert parse_origins("") == [
        "http://127.0.0.1:8888",
        "http://localhost:8888",
    ]


def test_parse_origins_rejects_wildcard():
    assert parse_origins("*") == [
        "http://127.0.0.1:8888",
        "http://localhost:8888",
    ]


def test_parse_bool_is_explicit():
    assert parse_bool("true") is True
    assert parse_bool("1") is True
    assert parse_bool("false") is False
    assert parse_bool("") is False
