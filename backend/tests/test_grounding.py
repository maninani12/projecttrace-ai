from app.parsers.archive import ParsedFile
from app.parsers.source import detect
from app.security.redaction import redact


def fixture(path, language, content):
    return ParsedFile(path, language, content, len(content), "synthetic", 0)


def test_framework_comment_is_not_implementation():
    assert detect([fixture("main.py", "Python", '# app = FastAPI()\nmessage = "FastAPI()"')]) == []


def test_alias_framework_is_detected_from_ast():
    stack = detect(
        [fixture("main.py", "Python", "from fastapi import FastAPI as API\napp = API()")]
    )
    assert stack[0]["name"] == "FastAPI" and stack[0]["status"] == "VERIFIED"


def test_requirements_only_is_inferred():
    stack = detect([fixture("requirements.txt", "Text", "fastapi>=0.115\n")])
    assert stack[0]["name"] == "FastAPI" and stack[0]["status"] == "INFERRED"


def test_plain_readme_cannot_verify_database():
    assert detect([fixture("README", "Markdown", "DATABASE_URL=postgresql://localhost/app")]) == []


def test_driver_connection_credentials_redacted():
    text, count = redact('DATABASE_URL="postgresql+psycopg://someone:synthetic-password@host/db"')
    assert count and "synthetic-password" not in text
    assert "postgresql+psycopg://" in text


def test_programmatic_password_assignment_is_preserved():
    text = "password = hasher.hash(body.password)"
    assert redact(text)[0] == text
