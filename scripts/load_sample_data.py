import json
from datetime import datetime
from pathlib import Path

from app.database import Base, SessionLocal, engine
from app.models import UsageRecord
from app.services import estimate_cost


def main() -> None:
    Base.metadata.create_all(bind=engine)
    sample_file = Path(__file__).resolve().parents[1] / "sample_data" / "usage.json"
    records = json.loads(sample_file.read_text(encoding="utf-8"))
    loaded = 0
    with SessionLocal() as db:
        for item in records:
            if item.get("request_id") and db.query(UsageRecord).filter_by(
                request_id=item["request_id"]
            ).first():
                continue
            item["occurred_at"] = datetime.fromisoformat(item["occurred_at"])
            cost = estimate_cost(
                db,
                item["provider"],
                item["model"],
                item["input_tokens"],
                item["output_tokens"],
            )
            db.add(UsageRecord(**item, cost_usd=cost, cost_source="estimated"))
            loaded += 1
        db.commit()
    print(f"Loaded {loaded} sample usage records.")


if __name__ == "__main__":
    main()
