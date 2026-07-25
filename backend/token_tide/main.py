import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from token_tide.bootstrap import bootstrap_settings
from token_tide.config import Settings, get_settings
from token_tide.database import dispose_engine
from token_tide.dependencies import get_balance_service
from token_tide.logging import configure_application_logging
from token_tide.response import R, ok, register_exception_handlers
from token_tide.router import router
from token_tide.scheduler import create_scheduler
from token_tide.schemas import ApplicationInfo

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    service = get_balance_service()
    scheduler = create_scheduler(service, settings.refresh)
    scheduler.start()
    startup_refresh = asyncio.create_task(service.refresh_all("STARTUP"))
    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        if not startup_refresh.done():
            startup_refresh.cancel()
        dispose_engine()


app = FastAPI(title="TokenTide API", version="0.1.0", lifespan=lifespan)
register_exception_handlers(app)
app.include_router(router)


@app.get("/", response_model=R[ApplicationInfo])
def application_info() -> R[ApplicationInfo]:
    return ok(
        ApplicationInfo(
            app="token-tide",
            ts=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            TOKEN_TIDE_COMMIT=os.environ.get("TOKEN_TIDE_COMMIT", "unknown"),
        )
    )


def configure_app(application_settings: Settings) -> None:
    if getattr(app.state, "configuration_applied", False):
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=application_settings.server.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    app.state.configuration_applied = True


def main() -> None:
    configure_application_logging()
    try:
        settings = bootstrap_settings()
        configure_app(settings)
        uvicorn.run(
            "token_tide.main:app",
            host=settings.server.host,
            port=settings.server.port,
            log_config=None,
        )
    except Exception:
        logger.exception("token-tide startup failed")
        raise


if __name__ == "__main__":
    main()
