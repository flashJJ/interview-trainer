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

if settings.database_url.startswith("sqlite"):
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record):  # noqa: ANN001
        """SQLite 并发优化：WAL 允许读写并发，busy_timeout 缓解写锁竞争。

        背景：并发出题（LLM 多线程）与考试草稿自动保存同时写库时，
        默认 journal 模式会报 database is locked（500）。
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        # 写-写仍互斥（WAL 只放开读-写并发），等锁上限放宽到 30s 以覆盖 LLM 长请求场景
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.close()


def commit_with_retry(db, retries: int = 3, base_delay: float = 0.1) -> None:
    """提交事务，遇到 SQLite 写锁（database is locked）时退避重试。

    背景：并发出题/讲题期间，草稿自动保存等短写事务可能与其他写事务
    争抢 SQLite 写锁；busy_timeout 之外再加应用层重试，避免直接 500。
    """
    import time

    from sqlalchemy.exc import OperationalError

    for attempt in range(retries):
        try:
            db.commit()
            return
        except OperationalError as exc:
            db.rollback()
            if "locked" not in str(exc).lower() or attempt == retries - 1:
                raise
            time.sleep(base_delay * (attempt + 1))

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
