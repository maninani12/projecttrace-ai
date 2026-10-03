import os
import re
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import Settings


class GitHubError(ValueError):
    pass


def resolve_public_head(url, storage_dir):
    """Read refs only; never clone, checkout, run hooks or invoke repository code."""
    repository_parts(url)
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update(
        {"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"}
    )
    try:
        with tempfile.TemporaryDirectory(prefix="refs-", dir=storage_dir) as directory:
            result = subprocess.run(
                [
                    "git",
                    "-c",
                    "credential.helper=",
                    "-c",
                    "credential.interactive=never",
                    "-c",
                    "protocol.file.allow=never",
                    "-c",
                    "protocol.ext.allow=never",
                    "-c",
                    "http.followRedirects=false",
                    "ls-remote",
                    "--symref",
                    "--exit-code",
                    url,
                    "HEAD",
                ],
                cwd=directory,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        branch = re.search(r"^ref: refs/heads/([^\r\n\t]{1,200})\tHEAD$", result.stdout, re.M)
        commit = re.search(r"^([a-f0-9]{40})\tHEAD$", result.stdout, re.M)
        if result.returncode != 0 or not branch or not commit or len(result.stdout) > 2048:
            raise GitHubError(
                "Could not resolve this public repository. It may be private or unavailable."
            )
        return branch.group(1), commit.group(1)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise GitHubError(
            "GitHub API quota is unavailable and safe reference lookup failed. Install Git or try again later."
        ) from exc


def repository_parts(url):
    parsed = urlsplit(url)
    parts = parsed.path.strip("/").removesuffix(".git").split("/")
    if (
        parsed.scheme != "https"
        or parsed.netloc != "github.com"
        or parsed.query
        or parsed.fragment
        or len(parts) != 2
    ):
        raise GitHubError(
            "Use a public repository URL such as https://github.com/owner/repository."
        )
    if not all(re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", p) and p not in {".", ".."} for p in parts):
        raise GitHubError("Invalid GitHub repository path.")
    return parts


@retry(
    retry=retry_if_exception_type(httpx.TransportError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=4),
    reraise=True,
)
def download_repository(url: str, destination: Path, config: Settings):
    owner, repo = repository_parts(url)
    with httpx.Client(
        timeout=httpx.Timeout(30, connect=10),
        follow_redirects=False,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "ProjectTrace-AI"},
    ) as client:
        meta = client.get(f"https://api.github.com/repos/{owner}/{repo}")
        quota = meta.status_code in {403, 429} and meta.headers.get("x-ratelimit-remaining") == "0"
        if quota:
            branch, sha = resolve_public_head(url, config.storage_dir)
        elif meta.status_code != 200:
            raise GitHubError(
                "GitHub repository is unavailable, private, or the public API quota was reached."
            )
        else:
            branch = meta.json()["default_branch"]
            if meta.json().get("private"):
                raise GitHubError("Only public repositories are supported.")
            from urllib.parse import quote

            commit = client.get(
                f"https://api.github.com/repos/{owner}/{repo}/commits/{quote(branch, safe='')}"
            )
            if (
                commit.status_code in {403, 429}
                and commit.headers.get("x-ratelimit-remaining") == "0"
            ):
                branch, sha = resolve_public_head(url, config.storage_dir)
            elif commit.status_code != 200:
                raise GitHubError("Could not resolve the repository default branch.")
            else:
                sha = commit.json()["sha"]
        if not re.fullmatch(r"[a-f0-9]{40}", sha):
            raise GitHubError("GitHub returned an invalid commit identifier.")
        # Fixed codeload host, immutable SHA, no user-controlled host and no redirects.
        with client.stream(
            "GET", f"https://codeload.github.com/{owner}/{repo}/zip/{sha}"
        ) as response:
            if response.status_code != 200:
                raise GitHubError("Could not download the GitHub snapshot.")
            size = 0
            with destination.open("wb") as handle:
                for block in response.iter_bytes(64 * 1024):
                    size += len(block)
                    if size > config.max_upload_mb * 1024**2:
                        raise GitHubError("GitHub archive exceeds the configured upload limit.")
                    handle.write(block)
        return branch, sha
