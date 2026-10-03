from types import SimpleNamespace

import httpx
import pytest

from app.core.config import Settings
from app.parsers.archive import read_archive
from app.services.github import GitHubError, download_repository, resolve_public_head


def test_safe_git_reference_lookup(monkeypatch, tmp_path):
    def run(args, **kwargs):
        assert args[-2:] == ["https://github.com/octocat/Hello-World", "HEAD"]
        assert "ls-remote" in args and "clone" not in args
        assert not kwargs.get("shell", False)
        assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
        assert kwargs["env"]["GIT_CONFIG_NOSYSTEM"] == "1"
        return SimpleNamespace(
            returncode=0, stdout="ref: refs/heads/main\tHEAD\n" + "a" * 40 + "\tHEAD\n"
        )

    monkeypatch.setattr("app.services.github.subprocess.run", run)
    assert resolve_public_head("https://github.com/octocat/Hello-World", tmp_path) == (
        "main",
        "a" * 40,
    )


def test_invalid_refs_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "app.services.github.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="untrusted"),
    )
    with pytest.raises(GitHubError):
        resolve_public_head("https://github.com/octocat/Hello-World", tmp_path)


def test_github_api_snapshot_and_bounded_archive(monkeypatch, tmp_path):
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("wrapper/README", "A safe project fixture.")
    payload = buffer.getvalue()

    def handler(request):
        if "/commits/" in str(request.url):
            return httpx.Response(200, json={"sha": "b" * 40})
        if request.url.host == "codeload.github.com":
            assert str(request.url).endswith("b" * 40)
            return httpx.Response(200, content=payload)
        return httpx.Response(200, json={"default_branch": "main", "private": False})

    original = httpx.Client
    monkeypatch.setattr(
        "app.services.github.httpx.Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    config = Settings(storage_dir=tmp_path)
    path = tmp_path / "github.zip"
    assert download_repository("https://github.com/a/b", path, config) == ("main", "b" * 40)
    assert [f.path for f in read_archive(path, config)] == ["README"]


def test_github_quota_fallback(monkeypatch, tmp_path):
    original = httpx.Client

    def handler(request):
        if request.url.host == "api.github.com":
            return httpx.Response(403, headers={"x-ratelimit-remaining": "0"})
        return httpx.Response(200, content=b"fixture")

    monkeypatch.setattr(
        "app.services.github.httpx.Client",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(
        "app.services.github.resolve_public_head", lambda url, directory: ("main", "c" * 40)
    )
    assert download_repository(
        "https://github.com/a/b", tmp_path / "x.zip", Settings(storage_dir=tmp_path)
    ) == ("main", "c" * 40)
