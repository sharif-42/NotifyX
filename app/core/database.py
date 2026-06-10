from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

# Get settings from the config
settings = get_settings()

# Create the SQLAlchemy engine and session factory
engine = create_engine(
    settings.database_url, 
    pool_pre_ping=True
)
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False, 
    autoflush=False, 
)

# Base class for all models
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

