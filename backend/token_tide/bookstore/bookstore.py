import logging
import os
from pathlib import Path

import httpx

from token_tide.bookstore.engines import StorageEngine
from token_tide.bookstore.errors import BookstoreError

logger = logging.getLogger(__name__)


class Bookstore:
    def __init__(self, storage_engine: StorageEngine) -> None:
        self.storage_engine = storage_engine
        logger.info("[Bookstore] StorageEngine: %s", storage_engine.__class__.__name__)

    def pull_text(self, full_name: str, timeout_milliseconds: int) -> str:
        url = self.storage_engine.assemble_url(full_name)
        headers = self.storage_engine.assemble_headers()
        try:
            response = httpx.get(
                url,
                headers=headers,
                timeout=timeout_milliseconds / 1000,
            )
        except httpx.RequestError as exc:
            raise BookstoreError("Remote configuration request failed") from exc
        if response.status_code != 200:
            raise BookstoreError(
                f"Remote configuration request failed with HTTP {response.status_code}"
            )
        if not response.text.strip():
            raise BookstoreError("Remote configuration response is empty")
        return self.storage_engine.parse_content(response.text)

    def write_text_to_file(self, file_name: str, content: str) -> Path:
        file_path = Path.cwd() / file_name
        try:
            file_path.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise BookstoreError(
                f"Unable to write configuration file: {file_path}"
            ) from exc
        logger.info("[Bookstore] Configuration written to %s", file_path)
        return file_path

    def download_configuration(
        self,
        remote_name: str,
        timeout_milliseconds: int,
    ) -> Path:
        tail = os.environ.get("CONFIGURATION_TAIL", "")
        if not tail:
            raise BookstoreError("CONFIGURATION_TAIL environment variable is not set")

        resolved_remote_name = remote_name.replace(":tail", tail)
        local_name = resolved_remote_name.rsplit("/", 1)[-1]
        content = self.pull_text(resolved_remote_name, timeout_milliseconds)
        local_path = self.write_text_to_file(local_name, content)
        logger.info(
            "[Bookstore] Downloaded %s to %s",
            resolved_remote_name,
            local_path,
        )
        return local_path
