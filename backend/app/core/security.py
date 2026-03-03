import base64
import hashlib
import hmac
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from itsdangerous import BadSignature, URLSafeSerializer

from .database import DB_PATH


ADMIN_SESSION_COOKIE = "email_app_admin_session"
_MASTER_KEY_ENV = "EMAIL_APP_MASTER_KEY"


def _master_key_path() -> str:
    return os.path.join(os.path.dirname(DB_PATH), ".email_app_master.key")


def _load_or_create_master_key() -> bytes:
    env_value = os.getenv(_MASTER_KEY_ENV)
    if env_value:
        return env_value.encode("utf-8")

    path = _master_key_path()
    if os.path.exists(path):
        return open(path, "rb").read().strip()

    key = Fernet.generate_key()
    with open(path, "wb") as fh:
        fh.write(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


def _fernet() -> Fernet:
    return Fernet(_load_or_create_master_key())


def encrypt_secret(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return ""
    if value.startswith("enc:"):
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"enc:{token}"


def decrypt_secret(value: Optional[str]) -> str:
    if not value:
        return ""
    if not value.startswith("enc:"):
        return value
    token = value[4:].encode("utf-8")
    try:
        return _fernet().decrypt(token).decode("utf-8")
    except InvalidToken:
        return ""


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    if not salt:
        salt = os.urandom(16).hex()
    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        200_000,
    ).hex()
    return password_hash, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    candidate_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(candidate_hash, password_hash)


def _session_serializer() -> URLSafeSerializer:
    secret = base64.urlsafe_b64encode(
        hashlib.sha256(_load_or_create_master_key()).digest()
    ).decode("ascii")
    return URLSafeSerializer(secret, salt="email-app-admin-session")


def build_admin_session_token(password_hash: str) -> str:
    return _session_serializer().dumps({"hash_prefix": password_hash[:16]})


def verify_admin_session_token(token: Optional[str], password_hash: Optional[str]) -> bool:
    if not token or not password_hash:
        return False
    try:
        payload = _session_serializer().loads(token)
    except BadSignature:
        return False
    return hmac.compare_digest(payload.get("hash_prefix", ""), password_hash[:16])
