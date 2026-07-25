import base64
import json
import os
from dataclasses import dataclass, field
from typing import Protocol
from urllib.parse import quote

from token_tide.bookstore.errors import BookstoreError


class StorageEngine(Protocol):
    def assemble_url(self, full_name: str) -> str: ...

    def assemble_headers(self) -> dict[str, str]: ...

    def parse_content(self, response_body: str) -> str: ...


@dataclass(frozen=True)
class GitHubStorageEngine:
    base_url: str
    token: str = field(repr=False)

    def assemble_url(self, full_name: str) -> str:
        return f"{self.base_url.rstrip('/')}/{full_name}"

    def assemble_headers(self) -> dict[str, str]:
        return {"Authorization": f"token {self.token}"}

    def parse_content(self, response_body: str) -> str:
        return response_body


@dataclass(frozen=True)
class GitLabStorageEngine:
    base_url: str
    token: str = field(repr=False)

    def assemble_url(self, full_name: str) -> str:
        encoded_name = quote(full_name, safe="")
        return f"{self.base_url.rstrip('/')}/{encoded_name}?ref=main"

    def assemble_headers(self) -> dict[str, str]:
        return {"PRIVATE-TOKEN": self.token}

    def parse_content(self, response_body: str) -> str:
        return _parse_base64_content(response_body)


@dataclass(frozen=True)
class CodeupStorageEngine:
    base_url: str
    token: str = field(repr=False)

    def assemble_url(self, full_name: str) -> str:
        encoded_name = quote(full_name, safe="")
        return f"{self.base_url.rstrip('/')}/{encoded_name}?ref=main"

    def assemble_headers(self) -> dict[str, str]:
        return {"x-yunxiao-token": self.token}

    def parse_content(self, response_body: str) -> str:
        return _parse_base64_content(response_body)


class StorageEngineFactory:
    @staticmethod
    def new_storage_engine() -> StorageEngine:
        engine_name = os.environ.get("BOOKSTORE_ENGINE", "")
        if not engine_name:
            raise BookstoreError("BOOKSTORE_ENGINE environment variable is not set")
        if engine_name == "github":
            return StorageEngineFactory._new_github_engine()
        if engine_name == "gitlab":
            return StorageEngineFactory._new_gitlab_engine()
        if engine_name == "codeup":
            return StorageEngineFactory._new_codeup_engine()
        raise BookstoreError(f"Unknown BOOKSTORE_ENGINE: {engine_name}")

    @staticmethod
    def _new_github_engine() -> GitHubStorageEngine:
        url, token = _required_environment(
            "BOOKSTORE_GITHUB_URL",
            "BOOKSTORE_GITHUB_TOKEN",
        )
        return GitHubStorageEngine(url, token)

    @staticmethod
    def _new_gitlab_engine() -> GitLabStorageEngine:
        url, token = _required_environment(
            "BOOKSTORE_GITLAB_URL",
            "BOOKSTORE_GITLAB_TOKEN",
        )
        return GitLabStorageEngine(url, token)

    @staticmethod
    def _new_codeup_engine() -> CodeupStorageEngine:
        url, token = _required_environment(
            "BOOKSTORE_CODEUP_URL",
            "BOOKSTORE_CODEUP_TOKEN",
        )
        return CodeupStorageEngine(url, token)


def _required_environment(url_name: str, token_name: str) -> tuple[str, str]:
    url = os.environ.get(url_name, "")
    token = os.environ.get(token_name, "")
    if not url or not token:
        raise BookstoreError(f"{url_name}, {token_name} environment variable is not set")
    return url, token


def _parse_base64_content(response_body: str) -> str:
    try:
        body = json.loads(response_body)
        content = body.get("content")
        if not isinstance(content, str) or not content:
            raise ValueError("content is empty")
        decoded = base64.b64decode(content, validate=True).decode("utf-8")
    except (ValueError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BookstoreError("Remote response content is invalid") from exc
    if not decoded.strip():
        raise BookstoreError("Remote response content is empty")
    return decoded
