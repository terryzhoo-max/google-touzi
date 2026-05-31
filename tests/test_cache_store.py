from core.cache_store import make_cache_key


def test_cache_key_includes_portfolio_and_period_dimensions():
    assert (
        make_cache_key(
            "institutional_attribution",
            {"portfolio": "institutional_portfolio", "period": "T-1"},
        )
        == "institutional_attribution_institutional_portfolio_T-1"
    )


def test_cache_key_keeps_periods_isolated_for_default_portfolio():
    t1 = make_cache_key("institutional_attribution", {"period": "T-1", "portfolio": None})
    t5 = make_cache_key("institutional_attribution", {"period": "T-5", "portfolio": None})

    assert t1 == "institutional_attribution_T-1"
    assert t5 == "institutional_attribution_T-5"
    assert t1 != t5
