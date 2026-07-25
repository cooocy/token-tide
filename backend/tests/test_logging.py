import logging
from pathlib import Path
from unittest.mock import patch

from token_tide.logging import configure_alembic_logging, configure_application_logging


def restore_logger(
    logger: logging.Logger,
    handlers: list[logging.Handler],
    level: int,
    propagate: bool,
) -> None:
    for handler in logger.handlers:
        if handler not in handlers:
            handler.close()
    logger.handlers[:] = handlers
    logger.setLevel(level)
    logger.propagate = propagate


def test_application_and_uvicorn_logs_are_separated(tmp_path: Path) -> None:
    loggers = [
        logging.getLogger(),
        logging.getLogger("uvicorn"),
        logging.getLogger("uvicorn.error"),
        logging.getLogger("uvicorn.access"),
    ]
    states = [
        (logger, list(logger.handlers), logger.level, logger.propagate)
        for logger in loggers
    ]
    try:
        with patch("token_tide.logging.Path.cwd", return_value=tmp_path):
            configure_application_logging()
            logging.getLogger("token_tide.test").info("app-message")
            logging.getLogger("uvicorn.access").info("uvicorn-message")
    finally:
        for state in states:
            restore_logger(*state)

    app_text = (tmp_path / "logs/app.log").read_text(encoding="utf-8")
    uvicorn_text = (tmp_path / "logs/uvicorn.log").read_text(encoding="utf-8")
    assert "app-message" in app_text
    assert "uvicorn-message" not in app_text
    assert "uvicorn-message" in uvicorn_text


def test_alembic_uses_dedicated_log(tmp_path: Path) -> None:
    root = logging.getLogger()
    state = (root, list(root.handlers), root.level, root.propagate)
    try:
        with patch("token_tide.logging.Path.cwd", return_value=tmp_path):
            configure_alembic_logging()
            logging.getLogger("alembic.test").info("migration-message")
    finally:
        restore_logger(*state)

    alembic_text = (tmp_path / "logs/alembic.log").read_text(encoding="utf-8")
    assert "migration-message" in alembic_text
