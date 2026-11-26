"""Application factory. Run with `uvicorn kairos.main:create_app --factory`."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from kairos import __version__
from kairos.adapters.db.engine import make_engine
from kairos.adapters.db.migrate import upgrade
from kairos.adapters.runtime import system_clock, uuid_ids
from kairos.config import Settings
from kairos.features.health.api import router as health_router
from kairos.features.registry.service import RegistryService
from kairos.features.tasks.queries import TaskQueries
from kairos.features.tasks.service import TaskService

# First path segments the SPA fallback must never answer for: the backend's own routes, and
# the build assets (a missing hashed asset must be a 404, never the index page).
_RESERVED_SEGMENTS = frozenset({"api", "mcp", "assets"})


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
        """Open the database, bring it to the latest schema and build the use cases."""
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        engine = make_engine(settings.database_path)
        upgrade(engine)
        app.state.engine = engine
        app.state.tasks = TaskService(engine, system_clock, uuid_ids)
        app.state.registry = RegistryService(engine, system_clock, uuid_ids)
        app.state.queries = TaskQueries(engine)
        try:
            yield
        finally:
            engine.dispose()

    app = FastAPI(title="Kairos", version=__version__, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.include_router(health_router)
    # The SPA catch-all matches every GET, so it must be registered after every other route.
    if settings.static_dir is not None and (settings.static_dir / "index.html").is_file():
        _serve_spa(app, settings.static_dir)
    return app


def _serve_spa(app: FastAPI, static_dir: Path) -> None:
    root = static_dir.resolve()
    index = root / "index.html"
    assets = root / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> FileResponse:
        if full_path.split("/", 1)[0] in _RESERVED_SEGMENTS:
            raise HTTPException(status_code=404)
        return FileResponse(_existing_file(root, full_path) or index)


def _existing_file(root: Path, relative: str) -> Path | None:
    """Return the file at `relative` inside `root`, or None if there is none or it escapes."""
    try:
        candidate = (root / relative).resolve()
        return candidate if candidate.is_relative_to(root) and candidate.is_file() else None
    except (OSError, ValueError):  # for example a NUL byte, which POSIX refuses to resolve
        return None
