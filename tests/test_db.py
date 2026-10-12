import pytest
from sqlalchemy.exc import OperationalError

from app.db import init_db, make_engine


def test_init_db_retries_then_gives_up(tmp_path, caplog):
    engine = make_engine(f"sqlite:///{tmp_path / 'missing' / 'db.sqlite'}")
    with pytest.raises(OperationalError):
        init_db(engine, timeout_seconds=1.0)
    assert "retrying" in caplog.text
    engine.dispose()


def test_init_db_is_idempotent(tmp_path):
    engine = make_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    init_db(engine, timeout_seconds=1.0)
    init_db(engine, timeout_seconds=1.0)
    engine.dispose()


def test_postgres_connections_time_out(monkeypatch):
    captured = {}
    monkeypatch.setattr("app.db.create_engine", lambda url, **kwargs: captured.update(kwargs))
    make_engine("postgresql+psycopg://kurz:kurz@db:5432/kurz", attempt_timeout_seconds=3)
    assert captured["connect_args"] == {"connect_timeout": 3}
