import hashlib
import re
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from app.core.config import Settings
from app.security.redaction import redact

IGNORED = {
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "coverage",
    ".git",
    "__pycache__",
    "vendor",
    "target",
}
EXTENSIONS = {
    ".py": "Python",
    ".tsx": "TypeScript",
    ".ts": "TypeScript",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".php": "PHP",
    ".cs": "C#",
    ".rb": "Ruby",
    ".vue": "Vue",
    ".json": "JSON",
    ".toml": "TOML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".md": "Markdown",
    ".txt": "Text",
    ".html": "HTML",
    ".css": "CSS",
    ".sql": "SQL",
    ".xml": "XML",
    ".ini": "Config",
    ".cfg": "Config",
    ".gradle": "Gradle",
    ".sh": "Shell",
    ".ps1": "PowerShell",
    ".env": "Config",
    ".ipynb": "Notebook",
}
ARCHIVES = {".zip", ".tar", ".gz", ".7z", ".rar", ".bz2", ".xz", ".jar", ".war"}
RESERVED = re.compile(r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$", re.I)


class ArchiveError(ValueError):
    pass


@dataclass
class ParsedFile:
    path: str
    language: str
    content: str
    size: int
    sha256: str
    secrets: int


def validate_path(name):
    if not name or len(name) > 500 or "\\" in name or name.startswith("/"):
        raise ArchiveError("Archive contains an unsafe filename.")
    parts = name.rstrip("/").split("/")
    if any(
        p in {"", ".", ".."}
        or RESERVED.match(p)
        or p[-1:] in {" ", "."}
        or any(ord(c) < 32 or c in ':<>"|?*' for c in p)
        for p in parts
    ):
        raise ArchiveError("Archive contains a traversal or unsupported filename.")
    return parts


def read_archive(path: Path, config: Settings):
    if path.stat().st_size > config.max_upload_mb * 1024**2:
        raise ArchiveError("Archive exceeds the configured upload limit.")
    try:
        with zipfile.ZipFile(path) as archive:
            items = archive.infolist()
            if len(items) > config.max_file_count:
                raise ArchiveError("Archive exceeds the configured file count limit.")
            total = 0
            seen = set()
            validated = []
            for info in items:
                parts = validate_path(info.filename)
                mode = info.external_attr >> 16
                if stat.S_ISLNK(mode) or info.flag_bits & 1:
                    raise ArchiveError("Symbolic links and encrypted entries are prohibited.")
                total += info.file_size
                if total > config.max_extracted_mb * 1024**2:
                    raise ArchiveError("Archive exceeds the decompressed size limit.")
                if (
                    info.file_size > 1024
                    and info.file_size / max(info.compress_size, 1) > config.max_compression_ratio
                ):
                    raise ArchiveError("Archive compression ratio exceeds the safety limit.")
                if info.filename.casefold() in seen:
                    raise ArchiveError("Archive contains duplicate filenames.")
                seen.add(info.filename.casefold())
                if not info.is_dir():
                    validated.append((info, parts))
            # GitHub archives have a wrapper directory; ZIPs retain repository-relative paths.
            roots = {parts[0] for _, parts in validated}
            strip = len(roots) == 1 and all(len(parts) > 1 for _, parts in validated)
            for info, parts in validated:
                if strip:
                    parts = parts[1:]
                if any(p in IGNORED for p in parts):
                    continue
                filename = PurePosixPath("/".join(parts))
                if filename.suffix.lower() in ARCHIVES:
                    raise ArchiveError("Nested archives are prohibited.")
                language = EXTENSIONS.get(filename.suffix.lower())
                if filename.name.lower() in {"readme", "license", "licence"}:
                    language = "Markdown" if filename.name.lower() == "readme" else "Text"
                if filename.name.lower().startswith(".env") or filename.name in {
                    "Dockerfile",
                    "LICENSE",
                    "Makefile",
                    ".gitignore",
                }:
                    language = "Config"
                if language is None:
                    continue
                if info.file_size > config.max_text_file_mb * 1024**2:
                    raise ArchiveError("A text file exceeds the individual file size limit.")
                with archive.open(info) as handle:
                    raw = handle.read(config.max_text_file_mb * 1024**2 + 1)
                if len(raw) != info.file_size:
                    raise ArchiveError("Archive entry size does not match its metadata.")
                if b"\x00" in raw[:4096]:
                    continue
                try:
                    text = raw.decode("utf-8-sig")
                except UnicodeDecodeError:
                    continue
                safe, secrets = redact(text, str(filename))
                yield ParsedFile(
                    str(filename),
                    language,
                    safe,
                    len(raw),
                    hashlib.sha256(raw).hexdigest(),
                    secrets,
                )
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise ArchiveError("The upload is not a supported, valid ZIP archive.") from exc
