"""Veritabanı bağlantısı ve oturum yardımcıları."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from examprep import config
from examprep.models import Base


def make_engine(url: str | None = None) -> Engine:
    if url is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:///{config.DATA_DIR / config.DB_FILENAME}"
    engine = create_engine(url)

    # SQLite foreign key kısıtları (ve ON DELETE CASCADE) varsayılan olarak kapalı.
    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        _engine = make_engine()
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def reset_engine() -> None:
    """Önbellekteki engine'i kapatır (testlerde DATA_DIR değiştiğinde kullanılır)."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = _SessionLocal = None


def init_db(engine: Engine | None = None) -> None:
    Base.metadata.create_all(engine or get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    get_engine()
    assert _SessionLocal is not None
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
