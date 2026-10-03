import stat
import zipfile

import pytest

from app.core.config import Settings
from app.parsers.archive import ArchiveError, read_archive
from app.security.redaction import redact
from app.services.github import GitHubError, repository_parts


def archive(tmp_path, entries):
    path = tmp_path / "input.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as handle:
        for name, value in entries:
            handle.writestr(name, value)
    return path


@pytest.mark.parametrize(
    "name",
    [
        "../evil.py",
        "/absolute.py",
        "C:/evil.py",
        "..\\evil.py",
        "safe/../../evil.py",
        "safe/NUL.txt",
        "safe/file:stream.py",
        "safe/a. /b.py",
    ],
)
def test_path_traversal(tmp_path, name):
    with pytest.raises(ArchiveError):
        list(read_archive(archive(tmp_path, [(name, 'print("unsafe")')]), Settings()))


def test_symlink(tmp_path):
    path = tmp_path / "link.zip"
    item = zipfile.ZipInfo("link.py")
    item.create_system = 3
    item.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(path, "w") as handle:
        handle.writestr(item, "../outside")
    with pytest.raises(ArchiveError):
        list(read_archive(path, Settings()))


def test_file_count(tmp_path):
    with pytest.raises(ArchiveError, match="count"):
        list(
            read_archive(
                archive(tmp_path, [("a.py", "x"), ("b.py", "y")]), Settings(max_file_count=1)
            )
        )


def test_bomb_ratio(tmp_path):
    with pytest.raises(ArchiveError, match="compression"):
        list(read_archive(archive(tmp_path, [("a.py", "a" * 100000)]), Settings()))


def test_nested_archive(tmp_path):
    with pytest.raises(ArchiveError, match="Nested"):
        list(read_archive(archive(tmp_path, [("a.zip", "archive")]), Settings()))


def test_duplicates(tmp_path):
    with pytest.raises(ArchiveError, match="duplicate"):
        list(read_archive(archive(tmp_path, [("a.py", "one"), ("A.py", "two")]), Settings()))


def test_binary_ignored_and_code_never_run(tmp_path):
    marker = tmp_path / "executed"
    code = f"from pathlib import Path; Path({str(marker)!r}).touch()"
    files = list(
        read_archive(
            archive(
                tmp_path,
                [("safe.py", code), ("program.exe", b"\x00\x01"), ("node_modules/x.js", "x")],
            ),
            Settings(),
        )
    )
    assert len(files) == 1
    assert not marker.exists()


def test_individual_file_limit(tmp_path):
    with pytest.raises(ArchiveError, match="individual"):
        list(
            read_archive(
                archive(tmp_path, [("a.py", bytes(range(32, 126)) * 12000)]),
                Settings(max_text_file_mb=1, max_compression_ratio=10000),
            )
        )


def test_upload_limit(tmp_path):
    path = tmp_path / "big.zip"
    path.write_bytes(b"x" * (1024**2 + 1))
    with pytest.raises(ArchiveError, match="upload"):
        list(read_archive(path, Settings(max_upload_mb=1)))


def test_extracted_limit(tmp_path):
    with pytest.raises(ArchiveError, match="decompressed"):
        list(
            read_archive(
                archive(tmp_path, [("a.py", "x" * (1024**2 + 1))]), Settings(max_extracted_mb=1)
            )
        )


@pytest.mark.parametrize(
    "value",
    [
        'API_KEY="sk-abcdefghijk123456789"',
        "PASSWORD=supersecretvalue",
        'DATABASE_URL="postgresql://user:secret@host/db"',
        "token=ghp_" + "a" * 36,
        "-----BEGIN PRIVATE KEY-----\nprivate\n-----END PRIVATE KEY-----",
    ],
)
def test_secret_redaction(value):
    safe, count = redact(value)
    assert count > 0
    assert "[REDACTED]" in safe
    assert "supersecretvalue" not in safe
    assert "user:secret" not in safe


def test_env_whole_redaction():
    safe, count = redact("OBSCURE_NAME=secret\nVALUE=anything", "backend/.env")
    assert "secret" not in safe and "anything" not in safe
    assert count == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/a/b",
        "https://github.com.evil/a/b",
        "https://user:pass@github.com/a/b",
        "https://github.com:443/a/b",
        "https://github.com/a/b/tree/main",
        "https://127.0.0.1/a/b",
        "https://github.com/a/b?url=evil",
        "https://github.com/a/..",
    ],
)
def test_ssrf_urls(url):
    with pytest.raises(GitHubError):
        repository_parts(url)


def test_valid_github():
    assert repository_parts("https://github.com/pallets/flask.git") == ["pallets", "flask"]


def test_production_config_fail_closed():
    with pytest.raises(ValueError):
        Settings(app_env="production")
    with pytest.raises(ValueError):
        Settings(cors_origins="*")
