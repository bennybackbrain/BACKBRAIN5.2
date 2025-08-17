from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from contextlib import contextmanager
import os

DB_URL = os.getenv("BB_DB_URL", "sqlite:///./backbrain.db")

def _make_engine(url: str):
    return create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )

# initial engine
engine = _make_engine(DB_URL)

class Base(DeclarativeBase):
    pass

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

def configure_engine():
    """Reconfigure engine & session factory if env var changed (used in tests)."""
    global engine, SessionLocal
    current_url = os.getenv("BB_DB_URL", "sqlite:///./backbrain.db")
    if str(engine.url) != current_url:
        try:
            engine.dispose()
        except Exception:
            pass
        engine = _make_engine(current_url)
        SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

@contextmanager
def get_session() -> Session:
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

# Startup helper
def init_db():
    configure_engine()
    from app.database import models  # noqa: F401 ensures models are imported
    # In testing we want a clean schema each time to avoid migration drift issues.
    import os as _os
    if _os.getenv("BB_TESTING") == "1":
        models.Base.metadata.drop_all(bind=engine)
    models.Base.metadata.create_all(bind=engine)
