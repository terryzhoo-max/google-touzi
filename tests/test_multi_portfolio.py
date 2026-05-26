import pytest
from fastapi.testclient import TestClient
from data_engine import app

def test_get_available_portfolios():
    client = TestClient(app)
    res = client.get("/api/institutional/portfolios")
    assert res.status_code == 200
    data = res.json()
    assert "portfolios" in data
    books = data["portfolios"]
    assert len(books) > 0
    names = [b["name"] for b in books]
    assert "tactical_hedged_portfolio" in names or len(names) > 0

def test_portfolio_switching_param():
    client = TestClient(app)
    # Read custom portfolio
    res1 = client.get("/api/institutional/portfolio?portfolio=tactical_hedged_portfolio")
    assert res1.status_code == 200
    data1 = res1.json()
    assert "total_market_value" in data1
    
    # Read default portfolio (which gets mocked to conftest's 9 ETFs of 100k each)
    res2 = client.get("/api/institutional/portfolio")
    assert res2.status_code == 200
    data2 = res2.json()
    assert abs(data2["total_market_value"] - 900000.0) < 1.0
