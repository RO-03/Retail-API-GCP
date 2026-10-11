import os
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker, declarative_base

# On Cloud Run, INSTANCE_CONNECTION_NAME ("project:region:instance") selects the Cloud SQL
# Unix socket at /cloudsql/<name>. Otherwise DATABASE_URL is used (local, Docker, K8s, tests).
INSTANCE_CONNECTION_NAME = os.getenv("INSTANCE_CONNECTION_NAME")

if INSTANCE_CONNECTION_NAME:
    DATABASE_URL = URL.create(
        drivername="postgresql+psycopg2",
        username=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        query={"host": f"/cloudsql/{INSTANCE_CONNECTION_NAME}"},
    )
else:
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@db:5432/retail_db")
    # SQLAlchemy 2.1+ maps a bare "postgresql://" to psycopg v3; we install psycopg2, so say so.
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# Pool is per worker process. Size it so that
# max_instances x workers x (pool_size + max_overflow) stays below Postgres max_connections.
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "30"))

if str(DATABASE_URL).startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_size=DB_POOL_SIZE,
        max_overflow=DB_MAX_OVERFLOW,
        pool_timeout=30,
        pool_recycle=1800
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """Yields a DB session and ensures it is closed after use."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
