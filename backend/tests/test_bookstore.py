import base64
import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from token_tide.bookstore import Bookstore, BookstoreError, StorageEngineFactory
from token_tide.bookstore.engines import (
    CodeupStorageEngine,
    GitHubStorageEngine,
    GitLabStorageEngine,
)


def test_github_engine_uses_raw_content_api() -> None:
    engine = GitHubStorageEngine("https://raw.example/repository/", "secret")

    assert (
        engine.assemble_url("token-tide/application-prod.yaml")
        == "https://raw.example/repository/token-tide/application-prod.yaml"
    )
    assert engine.assemble_headers() == {"Authorization": "token secret"}
    assert engine.parse_content("content") == "content"
    assert "secret" not in repr(engine)


def test_gitlab_and_codeup_decode_base64_content() -> None:
    response = json.dumps({"content": base64.b64encode("配置内容".encode()).decode()})
    gitlab = GitLabStorageEngine("https://gitlab.example/files", "gitlab-token")
    codeup = CodeupStorageEngine("https://codeup.example/files", "codeup-token")

    assert "token-tide%2Fapplication-prod.yaml" in gitlab.assemble_url(
        "token-tide/application-prod.yaml"
    )
    assert gitlab.assemble_headers() == {"PRIVATE-TOKEN": "gitlab-token"}
    assert gitlab.parse_content(response) == "配置内容"
    assert codeup.assemble_headers() == {"x-yunxiao-token": "codeup-token"}
    assert codeup.parse_content(response) == "配置内容"


def test_invalid_base64_content_fails() -> None:
    engine = CodeupStorageEngine("https://codeup.example/files", "token")

    with pytest.raises(BookstoreError):
        engine.parse_content('{"content": "not-base64"}')


def test_factory_selects_codeup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOKSTORE_ENGINE", "codeup")
    monkeypatch.setenv("BOOKSTORE_CODEUP_URL", "https://codeup.example/files/")
    monkeypatch.setenv("BOOKSTORE_CODEUP_TOKEN", "secret")

    engine = StorageEngineFactory.new_storage_engine()

    assert isinstance(engine, CodeupStorageEngine)


def test_factory_rejects_missing_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOOKSTORE_ENGINE", raising=False)

    with pytest.raises(BookstoreError):
        StorageEngineFactory.new_storage_engine()


def test_factory_rejects_unknown_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOKSTORE_ENGINE", "unknown")

    with pytest.raises(BookstoreError):
        StorageEngineFactory.new_storage_engine()


def test_factory_requires_selected_engine_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BOOKSTORE_ENGINE", "github")
    monkeypatch.delenv("BOOKSTORE_GITHUB_URL", raising=False)
    monkeypatch.delenv("BOOKSTORE_GITHUB_TOKEN", raising=False)

    with pytest.raises(BookstoreError):
        StorageEngineFactory.new_storage_engine()


def test_download_resolves_tail_and_overwrites_local_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = GitHubStorageEngine("https://raw.example/repository", "secret")
    bookstore = Bookstore(engine)
    path = tmp_path / "application-prod.yaml"
    path.write_text("old", encoding="utf-8")
    monkeypatch.setenv("CONFIGURATION_TAIL", "prod")

    with (
        patch("token_tide.bookstore.bookstore.Path.cwd", return_value=tmp_path),
        patch.object(bookstore, "pull_text", return_value="new") as pull,
    ):
        result = bookstore.download_configuration(
            "token-tide/application-:tail.yaml",
            8000,
        )

    pull.assert_called_once_with("token-tide/application-prod.yaml", 8000)
    assert result == path
    assert path.read_text(encoding="utf-8") == "new"


def test_download_requires_configuration_tail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bookstore = Bookstore(
        GitHubStorageEngine("https://raw.example/repository", "secret")
    )
    monkeypatch.delenv("CONFIGURATION_TAIL", raising=False)

    with pytest.raises(BookstoreError):
        bookstore.download_configuration("token-tide/application-:tail.yaml", 8000)


def test_pull_rejects_non_success_response() -> None:
    bookstore = Bookstore(
        GitHubStorageEngine("https://raw.example/repository", "secret")
    )
    response = httpx.Response(
        404,
        request=httpx.Request("GET", "https://raw.example/missing"),
    )
    with patch("token_tide.bookstore.bookstore.httpx.get", return_value=response):
        with pytest.raises(BookstoreError):
            bookstore.pull_text("missing", 8000)


def test_write_failure_is_wrapped() -> None:
    bookstore = Bookstore(
        GitHubStorageEngine("https://raw.example/repository", "secret")
    )
    with patch(
        "token_tide.bookstore.bookstore.Path.write_text",
        side_effect=OSError,
    ):
        with pytest.raises(BookstoreError):
            bookstore.write_text_to_file("application-prod.yaml", "content")
