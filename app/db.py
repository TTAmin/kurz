import logging
import time

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase

log = logging.getLogger(__name__)

# Arbitrary but fixed key: every replica takes the same lock before touching the schema.
SCHEMA_LOCK_KEY = 7_420_001


class Base(DeclarativeBase):
    pass


def make_engine(url: str) -> Engine:
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def init_db(engine: Engine, timeout_seconds: float) -> None:
    """Create the schema, waiting for the database to come up first.

    In Kubernetes the app and the database start at the same time, so the first
    connection attempts are expected to fail. Several replicas may start against
    a fresh database at once; a Postgres advisory lock serialises the CREATE TABLEs.
    """
    deadline = time.monotonic() + timeout_seconds
    delay = 0.5
    while True:
        try:
            with engine.begin() as conn:
                if conn.dialect.name == "postgresql":
                    conn.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": SCHEMA_LOCK_KEY})
                Base.metadata.create_all(conn)
            log.info("database ready")
            return
        except OperationalError as exc:
            if time.monotonic() + delay > deadline:
                raise
            log.warning("database not reachable yet, retrying in %.1fs: %s", delay, exc.orig)
            time.sleep(delay)
            delay = min(delay * 2, 5.0)
