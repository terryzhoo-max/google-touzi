import pytest
import pandas as pd
from unittest.mock import patch
from core.data_providers import (
    get_vix_history,
    get_dxy_history,
    get_tnx_history,
    get_us_etf_history,
    get_fallback_active_state,
    _fallback_active
)

@pytest.fixture(autouse=True)
def clean_fallback_state():
    _fallback_active.clear()
    yield
    _fallback_active.clear()

@patch("core.data_providers.os.path.exists")
@patch("core.data_providers.pd.read_sql_query")
@patch("core.data_providers._circuit_allow")
@patch("core.data_providers._fred_series")
def test_vix_resilience_failover(mock_fred, mock_circuit, mock_read_sql, mock_exists):
    # Simulate a network outage / open circuit breaker
    mock_circuit.return_value = False
    mock_fred.side_effect = Exception("Network Connection Lost")
    mock_exists.return_value = True
    
    # Mock SQLite query to return valid dataframe
    mock_read_sql.return_value = pd.DataFrame({
        "date": ["2026-05-24"],
        "close": [20.0]
    })
    
    # Under failover, it should read from the local SQLite time_series cache
    s = get_vix_history(days=30)
    
    # Assertions
    assert not s.empty
    assert s.name == "VIXCLS" or s.name == "VIX"
    assert s.attrs.get("fallback") is True
    assert s.attrs.get("source") == "sqlite_offline"
    
    # Check that the fallback status is active for VIX
    fallback_state = get_fallback_active_state()
    assert fallback_state.get("VIX") is True


@patch("core.data_providers.os.path.exists")
@patch("core.data_providers.pd.read_sql_query")
@patch("core.data_providers._circuit_allow")
@patch("core.data_providers._fred_series")
def test_tnx_resilience_failover(mock_fred, mock_circuit, mock_read_sql, mock_exists):
    # Simulate network failure
    mock_circuit.return_value = False
    mock_fred.side_effect = Exception("FRED Timeout")
    mock_exists.return_value = True
    
    mock_read_sql.return_value = pd.DataFrame({
        "date": ["2026-05-24"],
        "close": [4.2]
    })
    
    s = get_tnx_history(days=30)
    
    assert not s.empty
    assert s.name == "DGS10" or s.name == "TNX"
    assert s.attrs.get("fallback") is True
    assert s.attrs.get("source") == "sqlite_offline"
    assert get_fallback_active_state().get("TNX") is True
