from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase): # SQLAlchemy looks Base.metadata to know which tables exist, Alembic uses metadata to gen migrations
    pass



engine = create_engine( #long lived connection pool
    get_settings().database_url,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(bind=engine, autoflush = False, autocommit = False) #nothing is committed to db until db.commit() called


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
