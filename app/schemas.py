from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UsageCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    employee: str = Field(min_length=1, max_length=160)
    team: str = Field(min_length=1, max_length=120)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    occurred_at: datetime
    request_id: str | None = Field(default=None, max_length=160)
    reported_cost_usd: float | None = Field(default=None, ge=0)


class UsageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    model: str
    employee: str
    team: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cost_source: str
    request_id: str | None
    occurred_at: datetime


class BudgetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    scope_type: Literal["company", "team", "employee"] = "company"
    scope_value: str = Field(default="all", min_length=1, max_length=160)
    period: Literal["monthly", "weekly"] = "monthly"
    limit_usd: float = Field(gt=0)
    alert_threshold: float = Field(default=0.8, gt=0, le=1)


class BudgetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    scope_type: str
    scope_value: str
    period: str
    limit_usd: float
    alert_threshold: float


class PricingCreate(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    input_usd_per_million: float = Field(ge=0)
    output_usd_per_million: float = Field(ge=0)
