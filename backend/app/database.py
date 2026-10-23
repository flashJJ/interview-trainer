import os

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from .config import get_settings

settings = get_settings()


def _ensure_sqlite_dir(url: str) -> None:
    """SQLite 不会自动创建父目录，连接前先确保存在。"""
    if not url.startswith("sqlite"):
        return
    db_name = make_url(url).database
    if not db_name or db_name == ":memory:":
        return
    parent = os.path.dirname(os.path.abspath(db_name))
    if parent:
        os.makedirs(parent, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)

_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db() -> None:
    from .models import Base  # noqa: F401（确保模型已注册）

    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
