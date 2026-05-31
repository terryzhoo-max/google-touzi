from pydantic import BaseModel, Field


class WhatIfRequest(BaseModel):
    adjustments: dict[str, float] = Field(default_factory=lambda: {
        "SPY": -0.10,
        "GLD": 0.05,
        "CASH": 0.05,
    })


class HistoricalCrisisRequest(BaseModel):
    portfolio: str | None = None
    defense_trigger_drawdown: float = -0.05
    defense_risk_cut_ratio: float = 0.50
    stabilization_days: int = 10


class AllocationModelSimulateRequest(BaseModel):
    market_context: dict = Field(default_factory=dict)
    data_quality_score: int = Field(default=100, ge=0, le=100)
    data_quality_flags: list[str] = Field(default_factory=list)


class CustomShockRequest(BaseModel):
    equity_shock: float = 0.0
    rate_shock: float = 0.0
    vol_shock: float = 0.0
    commodity_shock: float = 0.0


class BlackLittermanRequest(BaseModel):
    views: dict[str, float] = Field(default_factory=dict)
    confidences: dict[str, float] = Field(default_factory=dict)


class RiskParityRequest(BaseModel):
    budgets: dict[str, float] = Field(default_factory=dict)


class CommitCustomDecisionRequest(BaseModel):
    source: str
    portfolio: str | None = None
    views: dict[str, float] = Field(default_factory=dict)
    confidences: dict[str, float] = Field(default_factory=dict)
    shocks: dict[str, float] = Field(default_factory=dict)
    budgets: dict[str, float] = Field(default_factory=dict)


class FrictionRequest(BaseModel):
    target_weights: dict[str, float] = Field(default_factory=dict)


class ForceReleaseRequest(BaseModel):
    auth_key: str
    symbol: str
    side: str
    quantity: int
    limit_price: float
    execution_algo: str = "DIRECT"
    portfolio_id: str = "institutional_portfolio"


class SignOffOrder(BaseModel):
    symbol: str
    side: str
    quantity: int
    price: float
    execution_algo: str


class SignOffOrdersRequest(BaseModel):
    orders: list[SignOffOrder]


class ExecuteTradeRequest(BaseModel):
    ticker: str
    action: str
    qty: float
