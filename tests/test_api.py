from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def create(client, **body):
    return client.post("/api/links", json=body)


def test_health_and_readiness(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}


def test_create_and_follow_link(client):
    resp = create(client, url="https://example.com/some/long/path?q=1")
    assert resp.status_code == 201
    link = resp.json()
    assert len(link["code"]) == 7
    assert link["short_url"] == f"http://sho.rt/{link['code']}"
    assert link["clicks"] == 0

    redirect = client.get(f"/{link['code']}", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == "https://example.com/some/long/path?q=1"


def test_clicks_are_counted(client):
    code = create(client, url="https://example.com").json()["code"]
    for _ in range(3):
        client.get(f"/{code}", follow_redirects=False)
    assert client.get(f"/api/links/{code}").json()["clicks"] == 3


def test_custom_code(client):
    resp = create(client, url="https://example.com", code="my-link")
    assert resp.status_code == 201
    assert resp.json()["code"] == "my-link"


def test_custom_code_conflict(client):
    assert create(client, url="https://a.example", code="taken").status_code == 201
    assert create(client, url="https://b.example", code="taken").status_code == 409


def test_reserved_code_is_rejected(client):
    assert create(client, url="https://example.com", code="healthz").status_code == 422
    assert create(client, url="https://example.com", code="Metrics").status_code == 422


def test_invalid_input_is_rejected(client):
    assert create(client, url="not a url").status_code == 422
    assert create(client, url="ftp://example.com").status_code == 422
    assert create(client, url="https://example.com", code="a").status_code == 422
    assert create(client, url="https://example.com", code="has space").status_code == 422


def test_unknown_code(client):
    assert client.get("/nope123", follow_redirects=False).status_code == 404
    assert client.get("/api/links/nope123").status_code == 404


def test_metrics_use_route_templates(client):
    code = create(client, url="https://example.com").json()["code"]
    client.get(f"/{code}", follow_redirects=False)
    body = client.get("/metrics").text
    assert "kurz_links_created_total" in body
    assert 'route="/{code}"' in body
    # The concrete code must never become a label value.
    assert f'route="/{code}"' not in body


def test_readiness_fails_without_database(tmp_path):
    missing_dir = tmp_path / "does-not-exist" / "db.sqlite"
    app = create_app(Settings(database_url=f"sqlite:///{missing_dir}", db_connect_timeout_seconds=0))
    # Skip the lifespan (which would fail creating the schema) to probe readiness alone.
    client = TestClient(app)
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 503
    app.state.engine.dispose()


def test_database_outage_is_a_503_not_a_500(tmp_path):
    missing_dir = tmp_path / "does-not-exist" / "db.sqlite"
    app = create_app(Settings(database_url=f"sqlite:///{missing_dir}", db_connect_timeout_seconds=0))
    client = TestClient(app)  # no lifespan: the database is "down" from the start

    for resp in (
        client.get("/someCode", follow_redirects=False),
        client.get("/api/links/someCode"),
        client.post("/api/links", json={"url": "https://example.com"}),
    ):
        assert resp.status_code == 503
        assert resp.headers["retry-after"] == "5"
        assert resp.json() == {"detail": "database unavailable"}

    metrics = client.get("/metrics").text
    assert 'route="/{code}",status="503"' in metrics
    app.state.engine.dispose()


def test_favicon_never_touches_the_database(tmp_path):
    missing_dir = tmp_path / "does-not-exist" / "db.sqlite"
    app = create_app(Settings(database_url=f"sqlite:///{missing_dir}", db_connect_timeout_seconds=0))
    client = TestClient(app)
    assert client.get("/favicon.ico").status_code == 204
    app.state.engine.dispose()


def test_start_page_works_without_the_database(tmp_path):
    missing_dir = tmp_path / "does-not-exist" / "db.sqlite"
    app = create_app(Settings(database_url=f"sqlite:///{missing_dir}", db_connect_timeout_seconds=0))
    resp = TestClient(app).get("/")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    assert '<form id="shorten">' in resp.text
    assert 'fetch("/api/links"' in resp.text
    app.state.engine.dispose()
