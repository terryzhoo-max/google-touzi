import pytest
import core.portfolio_book
from core.portfolio_book import Position

# Dynamic early-binding mockup to override CNY production data during tests.
# Construction of standard 9 ETFs with 100,000 market value each, total 900,000.0
test_positions = [
    Position("CSI300_ETF", "CSI300 ETF", "equity", "CNY", 100000.0, region="China", strategy="broad_market"),
    Position("CSI500_ETF", "CSI500 ETF", "equity", "CNY", 100000.0, region="China", strategy="small_mid_cap"),
    Position("STAR50_ETF", "STAR50 ETF", "equity", "CNY", 100000.0, region="China", strategy="technology"),
    Position("HSTECH_ETF", "HSTECH ETF", "equity", "HKD", 100000.0, region="HongKong", strategy="technology"),
    Position("SP500_ETF", "SP500 ETF", "equity", "USD", 100000.0, region="US", strategy="broad_market"),
    Position("NASDAQ_ETF", "NASDAQ ETF", "equity", "USD", 100000.0, region="US", strategy="technology"),
    Position("NIKKEI225_ETF", "NIKKEI225 ETF", "equity", "JPY", 100000.0, region="Japan", strategy="overseas"),
    Position("CHIP_ETF", "CHIP ETF", "equity", "CNY", 100000.0, region="China", strategy="technology"),
    Position("GOLD_ETF", "GOLD ETF", "gold", "CNY", 100000.0, region="Gold", strategy="gold"),
]

original_load = core.portfolio_book.load_portfolio_positions

def mocked_load(path=None):
    if path == "":
        from core.portfolio_book import get_sample_portfolio
        return get_sample_portfolio()
    if path is None or "institutional_portfolio.json" in path:
        return test_positions.copy()
    return original_load(path)

# Direct global import-level overwrite to fully solve Mocking Namespace Drift in fastapi test sessions.
core.portfolio_book.load_portfolio_positions = mocked_load

# Force global settings path to a recognized name early
from core.config import settings
settings.PORTFOLIO_BOOK_PATH = "data/institutional_portfolio.json"


@pytest.fixture(autouse=True)
def mock_portfolio_positions(monkeypatch):
    # Keep the monkeypatch fixture here for general pytest safety
    monkeypatch.setattr(core.portfolio_book, "load_portfolio_positions", mocked_load)
    monkeypatch.setattr(settings, "PORTFOLIO_BOOK_PATH", "data/institutional_portfolio.json")
