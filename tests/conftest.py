import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    # CI points KURZ_DATABASE_URL at a real Postgres service; locally SQLite is enough.
    url = os.environ.get("KURZ_DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    return Settings(database_url=url, base_url="http://sho.rt", db_connect_timeout_seconds=5)


@pytest.fixture
def client(settings) -> TestClient:
    app = create_app(settings)
    with TestClient(app) as c:
        yield c
        with app.state.session_factory() as session:
            session.execute(text("DELETE FROM links"))
            session.commit()
