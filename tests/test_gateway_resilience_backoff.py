import pytest
from unittest.mock import patch, MagicMock
import requests
import qmt_gateway_daemon

def test_gateway_poll_hub_resilience_success():
    """Verify that poll_hub_decisions returns True on HTTP 200."""
    mock_trader = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "global_status": "NORMAL",
        "broker_orders": []
    }
    
    with patch("requests.get", return_value=mock_response) as mock_get:
        success = qmt_gateway_daemon.poll_hub_decisions(mock_trader)
        assert success is True
        mock_get.assert_called_once_with(qmt_gateway_daemon.HUB_API_URL, timeout=5)

def test_gateway_poll_hub_resilience_network_failure():
    """Verify that poll_hub_decisions returns False on RequestException."""
    mock_trader = MagicMock()
    
    with patch("requests.get", side_effect=requests.exceptions.RequestException("Network down")) as mock_get:
        success = qmt_gateway_daemon.poll_hub_decisions(mock_trader)
        assert success is False
        mock_get.assert_called_once()
        
def test_gateway_poll_hub_resilience_non_200():
    """Verify that poll_hub_decisions returns False on HTTP 500 error."""
    mock_trader = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 500
    
    with patch("requests.get", return_value=mock_response) as mock_get:
        success = qmt_gateway_daemon.poll_hub_decisions(mock_trader)
        assert success is False
        mock_get.assert_called_once()
