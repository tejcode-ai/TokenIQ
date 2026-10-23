from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import ModelPricing
from app.routes import router

DEMO_PRICING = [
    ("openai", "gpt-4o-mini", 0.15, 0.60),
    ("openai", "gpt-4o", 2.50, 10.00),
    ("anthropic", "claude-3-5-haiku", 0.80, 4.00),
    ("anthropic", "claude-3-5-sonnet", 3.00, 15.00),
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        for provider, model, input_price, output_price in DEMO_PRICING:
            existing = db.scalar(
                select(ModelPricing).where(
                    ModelPricing.provider == provider,
                    ModelPricing.model == model,
                )
            )
            if existing is None:
                db.add(
                    ModelPricing(
                        provider=provider,
                        model=model,
                        input_usd_per_million=input_price,
                        output_usd_per_million=output_price,
                    )
                )
        db.commit()
    yield


app = FastAPI(
    title="TokenIQ",
    description="AI API token usage, cost, budget, and model comparison API.",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router, prefix="/api/v1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
