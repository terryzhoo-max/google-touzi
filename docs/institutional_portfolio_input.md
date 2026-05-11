# Institutional Portfolio Input

Set `PORTFOLIO_BOOK_PATH` to a UTF-8 JSON file to replace the default institutional portfolio for decision endpoints.

If unset, AlphaCore uses `data/institutional_portfolio.json`, currently initialized with:

- 沪深300ETF
- 中证500ETF
- 科创50ETF
- 恒生科技ETF
- 标普500ETF
- 纳指ETF
- 日经225ETF
- 芯片ETF
- 黄金ETF

Example:

```json
{
  "positions": [
    {
      "symbol": "AAPL",
      "name": "Apple Inc.",
      "asset_class": "equity",
      "region": "US",
      "currency": "USD",
      "market_value": 300000,
      "quantity": 1000,
      "cost_basis": 250000
    },
    {
      "symbol": "CASH",
      "name": "Cash",
      "asset_class": "cash",
      "currency": "USD",
      "market_value": 200000
    }
  ]
}
```

Required fields: `symbol`, `asset_class`, `market_value`.

Optional fields: `name`, `region`, `currency`, `quantity`, `cost_basis`.

Recommended `region` values for the default ETF portfolio:

- `China`
- `HongKong`
- `US`
- `Japan`
- `Gold`

If `PORTFOLIO_BOOK_PATH` is empty or the file does not exist, AlphaCore falls back to the deterministic sample portfolio used by lower-level unit tests.
