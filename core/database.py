from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from .config import settings

# Aiven free tier caps max_connections at 20 total (shared across however many
# Cloud Run instances autoscale up), so the per-instance pool stays small enough
# that even every allowed instance maxed out won't exhaust that ceiling.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=3,
    pool_recycle=1800,
    pool_timeout=30,
    # Cloud Run can kill an instance without a clean disconnect (e.g. on scale-down
    # or a crash), leaving a dead TCP connection Postgres won't notice until the OS's
    # default keepalive timeout (~2h on Linux). These force detection within ~60s so
    # dead connections from past instances don't sit reserved against the free-tier
    # 20-connection cap until Aiven eventually reaps them on its own.
    connect_args={
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 3,
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db() -> Generator:
    """Dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    # Test the database connection
    try:
        with engine.connect() as connection:
            print("Database connection successful!")
    except Exception as e:
        print(f"Database connection failed: {e}")