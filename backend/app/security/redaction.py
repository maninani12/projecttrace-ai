import re
from pathlib import PurePosixPath

PATTERNS = [
    re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----[\s\S]*?-----END (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    re.compile(
        r"\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|AIza[\w-]{30,}|sk-(?:proj-)?[\w-]{16,})\b"
    ),
    re.compile(
        r'(?i)((?:api[_-]?key|secret[_-]?key|jwt[_-]?secret|client[_-]?secret|password|passwd|access[_-]?token|refresh[_-]?token|oauth[_-]?token|github[_-]?token|auth[_-]?token|aws_secret_access_key)[\s"\']*[:=][\s"\']*)([^\s"\'`,;)}]{4,})'
    ),
    re.compile(
        r'(?i)((?:postgres(?:ql)?(?:\+\w+)?|mongodb(?:\+srv)?|mysql(?:\+\w+)?|redis)://)[^\s/"\']+:[^\s/@"\']+@'
    ),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r'(?i)(Authorization[\s"\']*[:=][\s"\']*(?:Bearer|Basic)\s+)[\w+/=.-]+'),
]


def redact(text: str, path: str = "") -> tuple[str, int]:
    name = PurePosixPath(path).name.lower()
    if (name == ".env" or name.startswith(".env.")) and name not in {
        ".env.example",
        ".env.sample",
        ".env.template",
    }:
        return "\n".join("[REDACTED: environment file]" for _ in text.splitlines()), 1
    count = 0
    for i, pattern in enumerate(PATTERNS):

        def replacement(match, i=i):
            nonlocal count
            count += 1
            if i == 2:
                value = match.group(2)
                if value.startswith(
                    ("${", "REDACTED", "[REDACTED", "os.getenv", "os.environ", "process.env")
                ):
                    count -= 1
                    return match.group(0)
                if not match.group(1).rstrip().endswith(('"', "'")) and "(" in value:
                    count -= 1
                    return match.group(0)
                return match.group(1) + "[REDACTED]"
            if i == 3:
                return match.group(1) + "[REDACTED]@"
            if i == 5:
                return match.group(1) + "[REDACTED]"
            return "[REDACTED]"

        text = pattern.sub(replacement, text)
    return text, count
