import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User
from app.config import get_session_secret, get_settings

SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 3
SCRYPT_MAX_MEMORY = 64 * 1024 * 1024


def hash_password(password: str) -> str:
    """Hash a password with scrypt and a unique random salt."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P,
        dklen=32, maxmem=SCRYPT_MAX_MEMORY,
    )
    return "scrypt${}${}${}${}${}".format(
        SCRYPT_N,
        SCRYPT_R,
        SCRYPT_P,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_value, digest_value = encoded.split("$", 5)
        if algorithm != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_value.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_value.encode("ascii"))
        actual = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=int(n), r=int(r), p=int(p),
            dklen=len(expected), maxmem=SCRYPT_MAX_MEMORY,
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


class AuthService:
    def __init__(self, db: Session):
        self.db = db

    def authenticate(self, username: str, password: str) -> User | None:
        user = self.db.scalar(select(User).where(User.username == username.strip().lower()))
        if not user or not user.is_active or not verify_password(password, user.password_hash):
            return None
        if self.password_hash_needs_upgrade(user.password_hash):
            user.password_hash = hash_password(password)
        user.last_login_at = datetime.now(timezone.utc)
        self.db.commit()
        return user

    @staticmethod
    def password_hash_needs_upgrade(encoded: str) -> bool:
        try:
            algorithm, n, r, p, *_ = encoded.split("$")
            return (
                algorithm != "scrypt"
                or int(n) != SCRYPT_N
                or int(r) != SCRYPT_R
                or int(p) != SCRYPT_P
            )
        except (ValueError, TypeError):
            return True

    @staticmethod
    def session_marker(user: User) -> str:
        secret = get_session_secret(get_settings()).encode("utf-8")
        state = f"{user.id}:{user.role}:{user.password_hash}".encode("utf-8")
        return hmac.new(secret, state, hashlib.sha256).hexdigest()

    def get_active_user(self, user_id: int | None) -> User | None:
        if not user_id:
            return None
        return self.db.scalar(select(User).where(User.id == user_id, User.is_active.is_(True)))

    def get_active_master(self, user_id: int | None) -> User | None:
        user = self.get_active_user(user_id)
        return user if user and user.role == "master" else None

    def create_or_reset_master(self, username: str, password: str) -> User:
        normalized = username.strip().lower()
        user = self.db.scalar(select(User).where(User.username == normalized))
        if user:
            user.password_hash = hash_password(password)
            user.role = "master"
            user.is_active = True
        else:
            user = User(
                username=normalized,
                password_hash=hash_password(password),
                role="master",
                is_active=True,
            )
            self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def list_users(self) -> list[User]:
        return list(self.db.scalars(select(User).order_by(User.username)))

    def create_user(self, username: str, password: str, role: str) -> User:
        normalized = username.strip().lower()
        if self.db.scalar(select(User).where(User.username == normalized)):
            raise ValueError("Já existe um usuário com esse nome.")
        user = User(username=normalized, password_hash=hash_password(password), role=role, is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def reset_password(self, user: User, password: str) -> None:
        user.password_hash = hash_password(password)
        self.db.commit()

    def set_active(self, user: User, active: bool) -> None:
        user.is_active = active
        self.db.commit()

    def change_password(self, user: User, current_password: str, new_password: str) -> bool:
        if not verify_password(current_password, user.password_hash):
            return False
        user.password_hash = hash_password(new_password)
        self.db.commit()
        return True
