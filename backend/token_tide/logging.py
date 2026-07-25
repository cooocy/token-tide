import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

MAX_LOG_BYTES = 20 * 1024 * 1024
BACKUP_COUNT = 10
LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"


def _log_handler(file_name: str) -> RotatingFileHandler:
    log_dir = Path.cwd() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / file_name,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    return handler


def configure_application_logging() -> None:
    app_handler = _log_handler("app.log")
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(app_handler)
    root.setLevel(logging.INFO)

    uvicorn_handler = _log_handler("uvicorn.log")
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.addHandler(uvicorn_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False


def configure_alembic_logging() -> None:
    handler = _log_handler("alembic.log")
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
