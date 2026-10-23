from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Budget, ModelPricing, UsageRecord
from app.schemas import (
    BudgetCreate,
    BudgetRead,
    PricingCreate,
    UsageCreate,
    UsageRead,
)
from app.services import budget_spend, estimate_cost, period_bounds

router = APIRouter()


@router.post("/usage", response_model=UsageRead, status_code=status.HTTP_201_CREATED)
def create_usage(payload: UsageCreate, db: Session = Depends(get_db)) -> UsageRecord:
    if payload.reported_cost_usd is None:
        try:
            cost = estimate_cost(
                db, payload.provider, payload.model, payload.input_tokens, payload.output_tokens
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        source = "estimated"
    else:
        cost = payload.reported_cost_usd
        source = "reported"
    occurred_at = payload.occurred_at
    if occurred_at.tzinfo is not None:
        occurred_at = occurred_at.astimezone(timezone.utc).replace(tzinfo=None)
    record = UsageRecord(
        provider=payload.provider,
        model=payload.model,
        employee=payload.employee,
        team=payload.team,
        input_tokens=payload.input_tokens,
        output_tokens=payload.output_tokens,
        cost_usd=cost,
        cost_source=source,
        request_id=payload.request_id,
        occurred_at=occurred_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/usage", response_model=list[UsageRead])
def list_usage(
    start: date | None = None,
    end: date | None = None,
    employee: str | None = None,
    team: str | None = None,
    model: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[UsageRecord]:
    query = select(UsageRecord).order_by(UsageRecord.occurred_at.desc())
    if start:
        query = query.where(UsageRecord.occurred_at >= datetime.combine(start, time.min))
    if end:
        query = query.where(
            UsageRecord.occurred_at < datetime.combine(end + timedelta(days=1), time.min)
        )
    if employee:
        query = query.where(UsageRecord.employee == employee)
    if team:
        query = query.where(UsageRecord.team == team)
    if model:
        query = query.where(UsageRecord.model == model)
    return list(db.scalars(query.limit(limit)).all())


@router.get("/usage/summary")
def usage_summary(
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> dict[str, float | int]:
    query = select(
        func.count(UsageRecord.id),
        func.coalesce(func.sum(UsageRecord.input_tokens), 0),
        func.coalesce(func.sum(UsageRecord.output_tokens), 0),
        func.coalesce(func.sum(UsageRecord.cost_usd), 0),
    )
    if start:
        query = query.where(UsageRecord.occurred_at >= datetime.combine(start, time.min))
    if end:
        query = query.where(
            UsageRecord.occurred_at < datetime.combine(end + timedelta(days=1), time.min)
        )
    count, input_tokens, output_tokens, cost = db.execute(query).one()
    return {
        "request_count": count,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "cost_usd": round(float(cost), 6),
    }


@router.get("/usage/breakdown")
def usage_breakdown(
    by: Literal["employee", "team", "model"] = "model",
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> list[dict[str, str | int | float]]:
    group_field = {
        "employee": UsageRecord.employee,
        "team": UsageRecord.team,
        "model": UsageRecord.model,
    }[by]
    query = select(
        group_field.label("name"),
        func.count(UsageRecord.id).label("requests"),
        func.sum(UsageRecord.input_tokens).label("input_tokens"),
        func.sum(UsageRecord.output_tokens).label("output_tokens"),
        func.sum(UsageRecord.cost_usd).label("cost_usd"),
    )
    if start:
        query = query.where(UsageRecord.occurred_at >= datetime.combine(start, time.min))
    if end:
        query = query.where(
            UsageRecord.occurred_at < datetime.combine(end + timedelta(days=1), time.min)
        )
    rows = db.execute(query.group_by(group_field).order_by(func.sum(UsageRecord.cost_usd).desc()))
    return [
        {
            "name": row.name,
            "requests": row.requests,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "total_tokens": row.input_tokens + row.output_tokens,
            "cost_usd": round(float(row.cost_usd), 6),
        }
        for row in rows
    ]


@router.post("/budgets", response_model=BudgetRead, status_code=status.HTTP_201_CREATED)
def create_budget(payload: BudgetCreate, db: Session = Depends(get_db)) -> Budget:
    if payload.scope_type == "company" and payload.scope_value != "all":
        raise HTTPException(status_code=422, detail="Company budgets must use scope_value='all'")
    budget = Budget(**payload.model_dump())
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return budget


@router.get("/budgets", response_model=list[BudgetRead])
def list_budgets(db: Session = Depends(get_db)) -> list[Budget]:
    return list(db.scalars(select(Budget).order_by(Budget.id)).all())


@router.get("/budgets/status")
def budget_status(db: Session = Depends(get_db)) -> list[dict[str, int | str | float | bool]]:
    results = []
    for budget in db.scalars(select(Budget).order_by(Budget.id)):
        start, end = period_bounds(budget.period)
        spent = budget_spend(db, budget, start, end)
        ratio = spent / budget.limit_usd
        results.append(
            {
                "budget_id": budget.id,
                "name": budget.name,
                "scope_type": budget.scope_type,
                "scope_value": budget.scope_value,
                "period": budget.period,
                "spent_usd": round(spent, 6),
                "limit_usd": budget.limit_usd,
                "usage_ratio": round(ratio, 4),
                "alert": ratio >= budget.alert_threshold,
                "over_limit": ratio >= 1,
            }
        )
    return results


@router.post("/models/pricing", status_code=status.HTTP_201_CREATED)
def upsert_pricing(payload: PricingCreate, db: Session = Depends(get_db)) -> dict[str, str | float]:
    pricing = db.scalar(
        select(ModelPricing).where(
            ModelPricing.provider == payload.provider,
            ModelPricing.model == payload.model,
        )
    )
    if pricing is None:
        pricing = ModelPricing(**payload.model_dump())
        db.add(pricing)
    else:
        pricing.input_usd_per_million = payload.input_usd_per_million
        pricing.output_usd_per_million = payload.output_usd_per_million
        pricing.updated_at = datetime.utcnow()
    db.commit()
    return {
        "provider": pricing.provider,
        "model": pricing.model,
        "input_usd_per_million": pricing.input_usd_per_million,
        "output_usd_per_million": pricing.output_usd_per_million,
    }


@router.get("/models/pricing")
def list_pricing(db: Session = Depends(get_db)) -> list[dict[str, str | float]]:
    entries = db.scalars(select(ModelPricing).order_by(ModelPricing.provider, ModelPricing.model))
    return [
        {
            "provider": item.provider,
            "model": item.model,
            "input_usd_per_million": item.input_usd_per_million,
            "output_usd_per_million": item.output_usd_per_million,
        }
        for item in entries
    ]


@router.get("/models/compare")
def compare_models(
    days: int = Query(default=30, ge=1, le=365),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    since = datetime.utcnow() - timedelta(days=days)
    totals = db.execute(
        select(
            func.coalesce(func.sum(UsageRecord.input_tokens), 0),
            func.coalesce(func.sum(UsageRecord.output_tokens), 0),
            func.coalesce(func.sum(UsageRecord.cost_usd), 0),
        ).where(UsageRecord.occurred_at >= since)
    ).one()
    input_tokens, output_tokens, actual_cost = totals
    catalog = db.scalars(select(ModelPricing).order_by(ModelPricing.provider, ModelPricing.model))
    options = []
    for item in catalog:
        projected = (
            input_tokens * item.input_usd_per_million
            + output_tokens * item.output_usd_per_million
        ) / 1_000_000
        options.append(
            {
                "provider": item.provider,
                "model": item.model,
                "projected_cost_usd": round(projected, 6),
                "estimated_savings_usd": round(float(actual_cost) - projected, 6),
            }
        )
    options.sort(key=lambda option: option["projected_cost_usd"])
    return {
        "days": days,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "actual_cost_usd": round(float(actual_cost), 6),
        "cheapest_option": options[0] if options else None,
        "options": options,
        "caveat": "Cost-only estimate: model quality, capabilities, and workload suitability are not evaluated.",
    }


@router.get("/anomalies")
def detect_spikes(
    days: int = Query(default=30, ge=2, le=365),
    multiplier: float = Query(default=2.0, gt=1, le=20),
    db: Session = Depends(get_db),
) -> list[dict[str, date | float | bool]]:
    today = date.today()
    first_day = today - timedelta(days=days - 1)
    rows = db.execute(
        select(
            func.date(UsageRecord.occurred_at).label("usage_day"),
            func.sum(UsageRecord.cost_usd).label("cost_usd"),
        )
        .where(UsageRecord.occurred_at >= datetime.combine(first_day, time.min))
        .group_by(func.date(UsageRecord.occurred_at))
        .order_by(func.date(UsageRecord.occurred_at))
    ).all()
    daily = {
        (
            row.usage_day
            if isinstance(row.usage_day, date)
            else date.fromisoformat(row.usage_day)
        ): float(row.cost_usd)
        for row in rows
    }
    results = []
    for day in sorted(daily):
        previous = [amount for prior_day, amount in daily.items() if prior_day < day]
        baseline = sum(previous) / len(previous) if previous else 0
        is_spike = len(previous) >= 3 and daily[day] > baseline * multiplier
        results.append(
            {
                "date": day,
                "cost_usd": round(daily[day], 6),
                "baseline_usd": round(baseline, 6),
                "is_spike": is_spike,
            }
        )
    return results
