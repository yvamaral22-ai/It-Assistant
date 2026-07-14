import argparse
import secrets
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal  # noqa: E402
from app.database_migrations import run_migrations  # noqa: E402
from app.models import User  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402
from sqlalchemy import select  # noqa: E402


def generate_password(length: int = 24) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%&*+-_"
    while True:
        value = "".join(secrets.choice(alphabet) for _ in range(length))
        if any(char.islower() for char in value) and any(char.isupper() for char in value) and any(char.isdigit() for char in value):
            return value


def main() -> None:
    parser = argparse.ArgumentParser(description="Cria ou redefine o usuário master local.")
    parser.add_argument("--username", default="master")
    parser.add_argument("--password", help="Omitir para gerar uma senha forte automaticamente.")
    parser.add_argument("--if-missing", action="store_true", help="Não redefine um master existente.")
    args = parser.parse_args()
    password = args.password or generate_password()
    if len(password) < 12:
        raise SystemExit("ERRO: a senha deve possuir pelo menos 12 caracteres.")
    run_migrations()
    with SessionLocal() as db:
        if args.if_missing and db.scalar(select(User).where(User.role == "master", User.is_active.is_(True))):
            print("Usuário master já configurado.")
            return
        user = AuthService(db).create_or_reset_master(args.username, password)
    print("Usuário master criado ou atualizado com sucesso.")
    print(f"Usuário: {user.username}")
    print(f"Senha inicial: {password}")
    print("Guarde esta senha em local seguro. Ela não poderá ser consultada novamente.")


if __name__ == "__main__":
    main()
