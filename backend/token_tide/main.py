import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from token_tide.config import get_settings
from token_tide.database import dispose_engine
from token_tide.dependencies import get_balance_service
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


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="TokenTide API", version="0.1.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )
    register_exception_handlers(application)
    application.include_router(router)

    @application.get("/", response_model=R[ApplicationInfo])
    def application_info() -> R[ApplicationInfo]:
        return ok(
            ApplicationInfo(
                app="token-tide",
                version="0.1.0",
                timestamp=datetime.now(UTC),
            )
        )

    return application


app = create_app()


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "token_tide.main:app",
        host=settings.server.host,
        port=settings.server.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
