from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
EXCLUDED_DIRS = {
    ".git", ".venv", "__pycache__", ".pytest_cache", "data", "node_modules",
}
EXCLUDED_SUFFIXES = {
    ".db", ".pyc", ".pyo", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".pdf",
}
PLACEHOLDER_VALUES = {
    "",
    "change-this-value",
    "strong-production-secret",
    "temporary-password-2026",
    "a-strong-local-password-2026",
    "another-strong-password-2026",
    "replacement-password-2026",
    "incorrect-password",
    "wrong-password",
    "test",
    "unused",
}
SECRET_ASSIGNMENT = re.compile(
    r"(?i)\\b(secret|secret_key|api[_-]?key|token|client_secret|service_role|password)\\b"
    r"\\s*[:=]\\s*[\"']?([^\"'\\s#;,)}]+)"
)
PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
HIGH_ENTROPY = re.compile(r"(?<![A-Za-z0-9_/-])[A-Za-z0-9_/-]{48,}(?![A-Za-z0-9_/-])")


def iter_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative_parts = set(path.relative_to(ROOT).parts)
        if relative_parts & EXCLUDED_DIRS:
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES:
            continue
        files.append(path)
    return files


def allowed_value(value: str) -> bool:
    normalized = value.strip().strip("\"'").lower()
    return (
        normalized in PLACEHOLDER_VALUES
        or "example" in normalized
        or "placeholder" in normalized
        or normalized.startswith("$")
        or normalized.startswith("%")
        or normalized.startswith("{")
    )


def high_entropy_candidate(value: str) -> bool:
    classes = 0
    classes += any(character.islower() for character in value)
    classes += any(character.isupper() for character in value)
    classes += any(character.isdigit() for character in value)
    classes += any(character in "+/=-_" for character in value)
    return classes >= 3


def scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return findings
    relative = path.relative_to(ROOT)
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.lstrip()
        if PRIVATE_KEY.search(line):
            findings.append(f"{relative}:{line_number}: chave privada encontrada")
        for match in SECRET_ASSIGNMENT.finditer(line):
            value = match.group(2)
            if not allowed_value(value):
                findings.append(f"{relative}:{line_number}: possivel segredo em '{match.group(1)}'")
        for match in HIGH_ENTROPY.finditer(line):
            candidate = match.group(0)
            if (
                high_entropy_candidate(candidate)
                and not allowed_value(candidate)
                and not stripped.startswith(("#", "//", "def ", "class ", "assert ", "from ", "import "))
            ):
                findings.append(f"{relative}:{line_number}: string de alta entropia")
    return findings


def main() -> int:
    findings: list[str] = []
    for path in iter_files():
        findings.extend(scan_file(path))
    if findings:
        print("Possiveis segredos encontrados:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("No hardcoded secrets found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
