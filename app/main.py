import logging
import secrets
import string
import time
from collections.abc import Iterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app import __version__
from app.config import Settings, get_settings
from app.db import init_db, make_engine
from app.logging_setup import configure_logging
from app.metrics import HTTP_LATENCY, HTTP_REQUESTS, LINKS_CREATED, REDIRECTS
from app.models import Link
from app.schemas import LinkCreate, LinkOut

log = logging.getLogger("kurz")

ALPHABET = string.ascii_letters + string.digits
# Paths the app serves itself; a short code with one of these names could never be reached.
RESERVED_CODES = {"api", "healthz", "readyz", "metrics", "docs", "redoc", "openapi.json", "favicon.ico"}

# Read once at import: the page is static, and the image's filesystem is read-only anyway.
START_PAGE = (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")

router = APIRouter()


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


def to_out(link: Link, settings: Settings) -> LinkOut:
    return LinkOut(
        code=link.code,
        short_url=f"{settings.base_url.rstrip('/')}/{link.code}",
        target_url=link.target_url,
        clicks=link.clicks,
        created_at=link.created_at,
    )


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
def start_page() -> str:
    """A form for people; it calls POST /api/links like any other client."""
    return START_PAGE


@router.get("/healthz", tags=["ops"])
def healthz() -> dict:
    """Liveness: the process is up. Deliberately does not touch the database."""
    return {"status": "ok"}


@router.get("/readyz", tags=["ops"])
def readyz(db: Session = Depends(get_db)) -> dict:
    """Readiness: the app can serve traffic, which needs the database."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        log.warning("readiness check failed: %s", exc)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "database unavailable") from exc
    return {"status": "ready"}


@router.get("/metrics", tags=["ops"], include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Browsers ask for it on every page; without this it would hit the redirect
    route and cost a database lookup (and fail with the database down)."""
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/api/links", status_code=status.HTTP_201_CREATED, response_model=LinkOut, tags=["links"])
def create_link(body: LinkCreate, request: Request, db: Session = Depends(get_db)) -> LinkOut:
    settings: Settings = request.app.state.settings
    target = str(body.url)

    if body.code is not None:
        if body.code.lower() in RESERVED_CODES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"'{body.code}' is reserved")
        link = Link(code=body.code, target_url=target)
        db.add(link)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(status.HTTP_409_CONFLICT, f"code '{body.code}' is taken") from None
    else:
        # Random codes collide rarely; retry instead of checking first, which would race.
        for _ in range(5):
            code = "".join(secrets.choice(ALPHABET) for _ in range(settings.code_length))
            link = Link(code=code, target_url=target)
            db.add(link)
            try:
                db.commit()
                break
            except IntegrityError:
                db.rollback()
        else:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "could not allocate a code")

    db.refresh(link)
    LINKS_CREATED.inc()
    log.info("link created", extra={"fields": {"code": link.code}})
    return to_out(link, settings)


@router.get("/api/links/{code}", response_model=LinkOut, tags=["links"])
def get_link(code: str, request: Request, db: Session = Depends(get_db)) -> LinkOut:
    link = db.scalar(select(Link).where(Link.code == code))
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown code")
    return to_out(link, request.app.state.settings)


@router.get("/{code}", tags=["links"], response_class=RedirectResponse, status_code=307)
def follow(code: str, db: Session = Depends(get_db)) -> RedirectResponse:
    # One atomic UPDATE: concurrent clicks never overwrite each other's count.
    target = db.scalar(
        update(Link).where(Link.code == code).values(clicks=Link.clicks + 1).returning(Link.target_url)
    )
    if target is None:
        REDIRECTS.labels(result="not_found").inc()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown code")
    db.commit()
    REDIRECTS.labels(result="ok").inc()
    return RedirectResponse(target, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url, settings.db_attempt_timeout_seconds)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db(engine, settings.db_connect_timeout_seconds)
        yield
        engine.dispose()

    app = FastAPI(title="kurz", version=__version__, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.session_factory = sessionmaker(engine, expire_on_commit=False)

    @app.exception_handler(OperationalError)
    async def database_unavailable(request: Request, exc: OperationalError) -> JSONResponse:
        # A lost database is an outage, not a bug in this code: 503 tells clients and
        # load balancers to come back later, and one log line replaces a traceback.
        log.warning("database unavailable: %s", exc.orig)
        return JSONResponse(
            {"detail": "database unavailable"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers={"Retry-After": "5"},
        )

    @app.middleware("http")
    async def observe(request: Request, call_next):
        start = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            elapsed = time.perf_counter() - start
            # Label by route template ("/{code}"), never by raw path: one label per
            # short code would grow Prometheus' memory without bound.
            route = request.scope.get("route")
            route_label = getattr(route, "path", "unmatched")
            HTTP_REQUESTS.labels(request.method, route_label, str(status_code)).inc()
            HTTP_LATENCY.labels(request.method, route_label).observe(elapsed)
            if route_label != "/metrics":
                log.info(
                    "request",
                    extra={
                        "fields": {
                            "method": request.method,
                            "route": route_label,
                            "status": status_code,
                            "duration_ms": round(elapsed * 1000, 2),
                        }
                    },
                )

    app.include_router(router)
    return app
