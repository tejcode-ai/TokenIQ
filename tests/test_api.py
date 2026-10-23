from collections.abc import Generator
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import ModelPricing


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=test_engine)
    with TestingSession() as db:
        db.add_all(
            [
                ModelPricing(
                    provider="openai",
                    model="gpt-4o-mini",
                    input_usd_per_million=0.15,
                    output_usd_per_million=0.60,
                ),
                ModelPricing(
                    provider="openai",
                    model="gpt-4o",
                    input_usd_per_million=2.50,
                    output_usd_per_million=10.00,
                ),
            ]
        )
        db.commit()

    def override_get_db() -> Generator[Session, None, None]:
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


def add_usage(client: TestClient, **overrides: object):
    payload = {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "employee": "alex@example.com",
        "team": "engineering",
        "input_tokens": 10000,
        "output_tokens": 2000,
        "occurred_at": datetime.now().isoformat(),
    }
    payload.update(overrides)
    return client.post("/api/v1/usage", json=payload)


def test_usage_ingest_cost_summary_and_grouping(client: TestClient) -> None:
    response = add_usage(client)
    assert response.status_code == 201
    assert response.json()["cost_usd"] == pytest.approx(0.0027)

    summary = client.get("/api/v1/usage/summary").json()
    assert summary["total_tokens"] == 12000
    assert summary["cost_usd"] == pytest.approx(0.0027)

    breakdown = client.get("/api/v1/usage/breakdown?by=team").json()
    assert breakdown[0]["name"] == "engineering"


def test_reported_cost_and_unknown_model_validation(client: TestClient) -> None:
    reported = add_usage(client, reported_cost_usd=1.23)
    assert reported.status_code == 201
    assert reported.json()["cost_source"] == "reported"
    unknown = add_usage(client, model="not-in-catalog")
    assert unknown.status_code == 422


def test_budget_alert_and_cost_comparison(client: TestClient) -> None:
    add_usage(client, reported_cost_usd=90)
    budget = client.post(
        "/api/v1/budgets",
        json={
            "name": "Company monthly",
            "limit_usd": 100,
            "alert_threshold": 0.8,
        },
    )
    assert budget.status_code == 201
    status = client.get("/api/v1/budgets/status").json()[0]
    assert status["alert"] is True

    compare = client.get("/api/v1/models/compare?days=30").json()
    assert compare["cheapest_option"]["model"] == "gpt-4o-mini"


def test_daily_spike_detection(client: TestClient) -> None:
    for days_ago in (4, 3, 2):
        add_usage(
            client,
            reported_cost_usd=10,
            occurred_at=(datetime.now() - timedelta(days=days_ago)).isoformat(),
        )
    add_usage(client, reported_cost_usd=100, occurred_at=datetime.now().isoformat())

    anomalies = client.get("/api/v1/anomalies?days=7&multiplier=2").json()
    assert anomalies[-1]["is_spike"] is True
