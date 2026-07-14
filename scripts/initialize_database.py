from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database_migrations import run_migrations  # noqa: E402

if __name__ == "__main__":
    (ROOT / "data").mkdir(exist_ok=True)
    run_migrations()
    print("Banco de dados inicializado com sucesso.")
