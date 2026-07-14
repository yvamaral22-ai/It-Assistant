import argparse
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import BASE_DIR, get_settings  # noqa: E402


def sqlite_path(url: str) -> Path:
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        raise RuntimeError("O backup integrado atende SQLite. Para PostgreSQL, use pg_dump.")
    value = url[len(prefix):]
    path = Path(value)
    return path if path.is_absolute() else BASE_DIR / path


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria backup consistente do SQLite.")
    parser.add_argument("--retention-days", type=int)
    args = parser.parse_args()
    settings = get_settings()
    source = sqlite_path(settings.database_url)
    if not source.exists():
        raise SystemExit(f"Banco não encontrado: {source}")
    backup_dir = BASE_DIR / "data" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    destination = backup_dir / f"it_assistant-{datetime.now():%Y%m%d-%H%M%S}.db"
    with sqlite3.connect(source) as origin, sqlite3.connect(destination) as target:
        origin.backup(target)
    retention = args.retention_days or settings.backup_retention_days
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention)
    for path in backup_dir.glob("it_assistant-*.db"):
        modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        if modified < cutoff:
            path.unlink()
    print(f"Backup criado: {destination}")


if __name__ == "__main__":
    main()
