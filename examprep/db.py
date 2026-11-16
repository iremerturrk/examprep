"""Veritabanı bağlantısı ve oturum yardımcıları."""

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine, event, inspect, text
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
    engine = engine or get_engine()
    Base.metadata.create_all(engine)
    add_missing_columns(engine)


def add_missing_columns(engine: Engine) -> list[str]:
    """Basit SQLite migration'ı: modelde olup tabloda olmayan kolonları ekler.

    Yeni tablolar create_all ile oluşur; mevcut tablolara eklenen kolonlar nullable
    olmalı ya da server_default taşımalı. Eklenen kolonları "tablo.kolon" olarak döndürür.
    """
    inspector = inspect(engine)
    added: list[str] = []
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name in existing:
                    continue
                if not column.nullable and column.server_default is None:
                    raise RuntimeError(
                        f"{table.name}.{column.name} NOT NULL ve server_default yok; otomatik eklenemez"
                    )
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column.type.compile(engine.dialect)}'
                if column.server_default is not None:
                    ddl += f" NOT NULL DEFAULT '{column.server_default.arg}'"
                for fk in column.foreign_keys:
                    ddl += f' REFERENCES "{fk.column.table.name}"("{fk.column.name}")'
                    if fk.ondelete:
                        ddl += f" ON DELETE {fk.ondelete}"
                conn.execute(text(ddl))
                added.append(f"{table.name}.{column.name}")
    return added


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
