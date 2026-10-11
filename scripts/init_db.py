"""Create all tables. Run once per environment (Cloud Run Job on GCP): python -m scripts.init_db"""
from app.core.database import engine
import app.models.item as models


def init_db():
    models.Base.metadata.create_all(bind=engine)
    print("Tables ensured:", ", ".join(sorted(models.Base.metadata.tables)))


if __name__ == "__main__":
    init_db()
