import re


def audit(files, secret_findings, routes):
    paths = [f.path.lower() for f in files]
    readme = "\n".join(
        f.content for f in files if f.path.lower().split("/")[-1].startswith("readme")
    )
    checks = []

    def add(name, condition, detail, absent="WARNING"):
        checks.append({"name": name, "status": "PASS" if condition else absent, "detail": detail})

    add("Project README", bool(readme), "README presence; accuracy is evaluated separately.")
    add(
        "Setup instructions",
        bool(
            re.search(r"\b(?:install|setup|getting started|npm|pip|docker compose)\b", readme, re.I)
        ),
        "Keyword-based static check; commands have not been executed.",
    )
    add(
        "Dependency manifest",
        any(
            p.endswith(
                (
                    "package.json",
                    "requirements.txt",
                    "pyproject.toml",
                    "pom.xml",
                    "build.gradle",
                    "composer.json",
                )
            )
            for p in paths
        ),
        "A supported manifest is present.",
    )
    add(
        "Environment example",
        any(p.endswith(".env.example") for p in paths),
        "Template presence; credentials are redacted before storage.",
    )
    add(
        "Docker configuration",
        any(p.endswith("dockerfile") for p in paths),
        "Container configuration presence only.",
    )
    add(
        "Test files",
        any(
            "/tests/" in "/" + p or p.split("/")[-1].startswith("test_") or ".test." in p
            for p in paths
        ),
        "Tests were detected, not executed.",
    )
    add(
        "CI workflow",
        any(".github/workflows/" in p for p in paths),
        "Workflow presence does not prove that CI passes.",
    )
    add(
        "Deployment configuration",
        any(
            p.endswith(
                (
                    "vercel.json",
                    "render.yaml",
                    "fly.toml",
                    "netlify.toml",
                    "docker-compose.yml",
                    "compose.yaml",
                )
            )
            for p in paths
        ),
        "Static deployment configuration; deployment is not verified.",
    )
    add(
        "Likely exposed secrets",
        not secret_findings,
        f"{len(secret_findings)} file(s) flagged. Values are redacted. Detection is heuristic.",
        "FAIL",
    )
    add(
        "License",
        any(p.split("/")[-1].startswith("license") for p in paths),
        "License file presence only.",
    )
    add(
        "Screenshots",
        "![" in readme,
        "README image references; images are not rendered by the analyzer.",
    )
    localhost = [
        f.path
        for f in files
        if f.language not in {"Markdown", "Text"}
        and re.search(r"https?://(?:localhost|127\.0\.0\.1)", f.content)
    ]
    add(
        "API URL configuration",
        not localhost,
        "Local URLs in: " + ", ".join(localhost[:5])
        if localhost
        else "No hard-coded HTTP loopback URLs detected in analyzed source.",
    )
    headers = any(
        re.search(r"(?:Content-Security-Policy|X-Content-Type-Options|helmet\()", f.content, re.I)
        for f in files
    )
    checks.append(
        {
            "name": "Security headers",
            "status": "PASS" if headers else "WARNING" if routes else "NOT APPLICABLE",
            "detail": "Presence check only; effective server behavior requires runtime testing.",
        }
    )
    return checks
