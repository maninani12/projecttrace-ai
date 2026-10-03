import ast
import json
import re
from pathlib import PurePosixPath

RULES = {
    "React": ("Frontend", [r'\b(?:from\s+["\']react["\']|React\.|useState\s*\()'], ["react"]),
    "FastAPI": ("Backend", [r"\bFastAPI\s*\("], ["fastapi"]),
    "Flask": ("Backend", [r"\bFlask\s*\("], ["flask"]),
    "Django": (
        "Backend",
        [r"\b(?:django\.conf|django\.urls|DJANGO_SETTINGS_MODULE)\b"],
        ["django"],
    ),
    "Express": ("Backend", [r"\bexpress\s*\("], ["express"]),
    "PostgreSQL": (
        "Database",
        [r"postgres(?:ql)?(?:\+\w+)?://", r"\bpsycopg\.(?:connect|Connection)\b"],
        ["psycopg", "psycopg2", "pg"],
    ),
    "MongoDB": (
        "Database",
        [r"mongodb(?:\+srv)?://", r"\b(?:MongoClient|mongoose\.connect)\s*\("],
        ["pymongo", "mongoose", "mongodb"],
    ),
    "SQLite": ("Database", [r"sqlite(?:\+\w+)?://", r"sqlite3\.connect\s*\("], []),
    "SQLAlchemy": ("Data access", [r"\b(?:from sqlalchemy|create_engine\s*\()"], ["sqlalchemy"]),
    "Redis": ("Background processing", [r"redis://", r"\bRedis\s*\("], ["redis"]),
    "JWT": (
        "Authentication",
        [r"\bjwt\.(?:encode|decode)\s*\("],
        ["pyjwt", "jsonwebtoken", "python-jose"],
    ),
    "Tailwind CSS": ("Styling", [r'@import ["\']tailwindcss', r"@tailwind\b"], ["tailwindcss"]),
}
DOC_EXTENSIONS = {".md", ".txt"}


def dependencies(path, content):
    name = PurePosixPath(path).name
    if name == "package.json":
        try:
            obj = json.loads(content)
            return set(obj.get("dependencies", {})) | set(obj.get("devDependencies", {}))
        except (ValueError, TypeError, AttributeError):
            return set()
    if name.startswith("requirements") or name in {
        "pyproject.toml",
        "pom.xml",
        "build.gradle",
        "composer.json",
    }:
        return set(re.findall(r"[a-z][a-z0-9_-]+", content.lower()))
    return set()


def python_signal(content, technology):
    try:
        tree = ast.parse(content)
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return False
    aliases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for name in node.names:
                aliases[name.asname or name.name] = name.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for name in node.names:
                aliases[name.asname or name.name] = node.module + "." + name.name

    def qualified(node):
        if isinstance(node, ast.Name):
            return aliases.get(node.id, node.id)
        if isinstance(node, ast.Attribute):
            return qualified(node.value) + "." + node.attr
        return ""

    calls = [qualified(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)]
    targets = {
        "FastAPI": {"fastapi.FastAPI"},
        "Flask": {"flask.Flask"},
        "MongoDB": {"pymongo.MongoClient", "motor.motor_asyncio.AsyncIOMotorClient"},
        "Redis": {"redis.Redis", "redis.from_url"},
        "JWT": {"jwt.encode", "jwt.decode", "jose.jwt.encode", "jose.jwt.decode"},
    }
    if set(calls) & targets.get(technology, set()):
        return True
    if technology == "SQLAlchemy" and any(
        value.startswith("sqlalchemy.") for value in aliases.values()
    ):
        return True
    if technology == "Django" and any(
        value.startswith(("django.conf", "django.urls")) for value in aliases.values()
    ):
        return True
    if technology == "PostgreSQL" and any(
        value.startswith(("psycopg.connect", "psycopg.Connection")) for value in calls
    ):
        return True
    if technology == "SQLite" and "sqlite3.connect" in calls:
        return True
    if RULES[technology][0] in {"Database", "Background processing"}:
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = [n.id for n in ast.walk(node) if isinstance(n, ast.Name)]
                if not any(
                    re.search(r"(database|db|url|connection|dsn)", name, re.I) for name in names
                ):
                    continue
                if any(
                    isinstance(n, ast.Constant)
                    and isinstance(n.value, str)
                    and any(re.search(pattern, n.value, re.I) for pattern in RULES[technology][1])
                    for n in ast.walk(node.value)
                ):
                    return True
    return False


def detect(files):
    result = []
    for technology, (category, patterns, packages) in RULES.items():
        direct, declared = [], []
        for file in files:
            manifest = PurePosixPath(file.path).name.startswith("requirements")
            if (file.language in {"Markdown", "Text"} and not manifest) or PurePosixPath(
                file.path
            ).name.startswith(".env"):
                continue
            source_text = re.sub(r"/\*[\s\S]*?\*/|^\s*//.*$", "", file.content, flags=re.M)
            signal = (
                python_signal(file.content, technology)
                if file.language == "Python"
                else any(re.search(pattern, source_text, re.I) for pattern in patterns)
            )
            if signal:
                direct.append(file.path)
            if set(packages) & dependencies(file.path, file.content):
                declared.append(file.path)
        paths = direct or declared
        if paths:
            result.append(
                {
                    "name": technology,
                    "category": category,
                    "confidence": "High" if direct else "Medium",
                    "status": "VERIFIED" if direct else "INFERRED",
                    "basis": "Source usage or configuration"
                    if direct
                    else "Dependency declaration only",
                    "files": paths[:10],
                }
            )
    return result


def code_metadata(file):
    result = {"routes": [], "symbols": [], "imports": []}
    if file.language == "Python":
        try:
            tree = ast.parse(file.content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    result["symbols"].append({"name": node.name, "line": node.lineno})
                if isinstance(node, ast.ImportFrom) and node.module:
                    result["imports"].append(node.module)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for dec in node.decorator_list:
                        if (
                            isinstance(dec, ast.Call)
                            and isinstance(dec.func, ast.Attribute)
                            and dec.func.attr in {"get", "post", "put", "delete", "patch"}
                        ):
                            if (
                                dec.args
                                and isinstance(dec.args[0], ast.Constant)
                                and isinstance(dec.args[0].value, str)
                            ):
                                result["routes"].append(
                                    {
                                        "method": dec.func.attr.upper(),
                                        "path": dec.args[0].value,
                                        "line": node.lineno,
                                    }
                                )
        except (SyntaxError, ValueError, MemoryError, RecursionError):
            result["parse_warning"] = (
                "Source could not be parsed as Python; text evidence retained."
            )
    return result


def chunk_file(content, lines_per_chunk=60, overlap=10):
    lines = content.splitlines()
    for start in range(0, len(lines), lines_per_chunk - overlap):
        end = min(start + lines_per_chunk, len(lines))
        text = "\n".join(lines[start:end])
        if text.strip():
            yield start + 1, end, text
        if end == len(lines):
            break
