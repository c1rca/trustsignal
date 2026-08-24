from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path


logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self, require_login: bool, store_path: str, session_ttl_minutes: int = 480) -> None:
        self._require_login = require_login
        raw_path = Path(store_path)
        self._store_path = raw_path if raw_path.is_absolute() else (Path.cwd() / raw_path)
        self._session_ttl = timedelta(minutes=session_ttl_minutes)
        self._sessions: dict[str, dict[str, object]] = {}

    @property
    def require_login(self) -> bool:
        return self._require_login

    def is_setup_required(self) -> bool:
        if not self._require_login:
            return False
        return not self._store_path.exists()

    def setup_credentials(self, username: str, password: str) -> None:
        if not self._require_login:
            return
        if not username.strip() or len(password) < 12:
            raise ValueError("Username required and password must be at least 12 characters")

        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        salt = secrets.token_bytes(16)
        iterations = 600_000
        password_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)

        payload = {
            "username": username.strip(),
            "salt_b64": base64.b64encode(salt).decode("ascii"),
            "hash_b64": base64.b64encode(password_hash).decode("ascii"),
            "iterations": iterations,
        }
        self._store_path.write_text(json.dumps(payload), encoding="utf-8")
        logger.info("auth setup complete")

    def login(self, username: str, password: str) -> tuple[str, str]:
        if not self._require_login:
            return "", ""
        if not self._store_path.exists():
            raise ValueError("Credentials are not set up")

        data = json.loads(self._store_path.read_text(encoding="utf-8"))
        if username.strip() != data.get("username"):
            raise ValueError("Invalid username or password")

        salt = base64.b64decode(data["salt_b64"])
        expected_hash = base64.b64decode(data["hash_b64"])
        iterations = int(data.get("iterations", 600_000))
        check_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        if not hmac.compare_digest(expected_hash, check_hash):
            raise ValueError("Invalid username or password")

        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(24)
        self._sessions[token] = {
            "expires_at": datetime.now(UTC) + self._session_ttl,
            "csrf": csrf_token,
        }
        logger.info("auth login success for user=%s", username.strip())
        return token, csrf_token

    def logout(self, token: str) -> None:
        if token:
            self._sessions.pop(token, None)
            logger.info("auth logout")

    def is_authenticated(self, token: str | None) -> bool:
        if not self._require_login:
            return True
        if not token:
            return False

        session = self._sessions.get(token)
        if not session:
            return False

        expires_at = session.get("expires_at")
        if not isinstance(expires_at, datetime) or datetime.now(UTC) >= expires_at:
            self._sessions.pop(token, None)
            return False

        # Sliding expiration.
        session["expires_at"] = datetime.now(UTC) + self._session_ttl
        return True

    def validate_csrf(self, token: str | None, csrf_token: str | None) -> bool:
        if not token or not csrf_token:
            return False
        session = self._sessions.get(token)
        if not session:
            return False
        expected = session.get("csrf")
        if not isinstance(expected, str):
            return False
        return hmac.compare_digest(expected, csrf_token)
