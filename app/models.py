from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ModelPricing(Base):
    __tablename__ = "model_pricing"
    __table_args__ = (UniqueConstraint("provider", "model", name="uq_provider_model"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(120), index=True)
    input_usd_per_million: Mapped[float] = mapped_column(Float)
    output_usd_per_million: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    model: Mapped[str] = mapped_column(String(120), index=True)
    employee: Mapped[str] = mapped_column(String(160), index=True)
    team: Mapped[str] = mapped_column(String(120), index=True)
    input_tokens: Mapped[int] = mapped_column(Integer)
    output_tokens: Mapped[int] = mapped_column(Integer)
    cost_usd: Mapped[float] = mapped_column(Float)
    cost_source: Mapped[str] = mapped_column(String(20), default="estimated")
    request_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Budget(Base):
    __tablename__ = "budgets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    scope_type: Mapped[str] = mapped_column(String(20), default="company")
    scope_value: Mapped[str] = mapped_column(String(160), default="all")
    period: Mapped[str] = mapped_column(String(20), default="monthly")
    limit_usd: Mapped[float] = mapped_column(Float)
    alert_threshold: Mapped[float] = mapped_column(Float, default=0.8)
