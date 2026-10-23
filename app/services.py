from calendar import monthrange
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Budget, ModelPricing, UsageRecord


def period_bounds(period: str, today: date | None = None) -> tuple[datetime, datetime]:
    today = today or date.today()
    if period == "weekly":
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=7)
    else:
        start = today.replace(day=1)
        end = today.replace(day=monthrange(today.year, today.month)[1]) + timedelta(days=1)
    return datetime.combine(start, datetime.min.time()), datetime.combine(end, datetime.min.time())


def budget_spend(db: Session, budget: Budget, start: datetime, end: datetime) -> float:
    query = select(func.coalesce(func.sum(UsageRecord.cost_usd), 0)).where(
        UsageRecord.occurred_at >= start,
        UsageRecord.occurred_at < end,
    )
    if budget.scope_type == "team":
        query = query.where(UsageRecord.team == budget.scope_value)
    elif budget.scope_type == "employee":
        query = query.where(UsageRecord.employee == budget.scope_value)
    return float(db.scalar(query) or 0)


def estimate_cost(
    db: Session, provider: str, model: str, input_tokens: int, output_tokens: int
) -> float:
    pricing = db.scalar(
        select(ModelPricing).where(
            ModelPricing.provider == provider,
            ModelPricing.model == model,
        )
    )
    if pricing is None:
        raise ValueError(f"No pricing is configured for {provider}/{model}")
    amount = (
        input_tokens * pricing.input_usd_per_million
        + output_tokens * pricing.output_usd_per_million
    ) / 1_000_000
    return round(amount, 8)
