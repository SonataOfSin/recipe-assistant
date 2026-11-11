"""Password hashing and the app's signed bearer-token helpers."""

import base64
import hashlib
import hmac
import json
import secrets
import time

from app.config import JWT_SECRET

TOKEN_TTL_SECONDS = 60 * 60 * 12


def hash_password(password: str) -> str:
    # A fresh salt prevents identical passwords from producing identical hashes.
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"{base64.urlsafe_b64encode(salt).decode()}:{base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_text, digest_text = stored_hash.split(":", maxsplit=1)
        salt = base64.urlsafe_b64decode(salt_text)
        expected = base64.urlsafe_b64decode(digest_text)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    # Constant-time comparison avoids leaking how much of a hash matched.
    return hmac.compare_digest(actual, expected)


def create_access_token(user_id: int) -> str:
    now = int(time.time())
    header = _encode({"alg": "HS256", "typ": "JWT"})
    payload = _encode({"sub": str(user_id), "iat": now, "exp": now + TOKEN_TTL_SECONDS})
    signing_input = f"{header}.{payload}".encode()
    # Sign the header and claims so clients cannot edit the user or expiry.
    signature = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64(signature)}"


def decode_access_token(token: str) -> int:
    try:
        header, payload, signature = token.split(".")
        signing_input = f"{header}.{payload}".encode()
        expected = hmac.new(JWT_SECRET.encode(), signing_input, hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _unb64(signature)):
            raise ValueError("Invalid token signature.")
        claims = json.loads(_unb64(payload))
        # Check both the signature and expiry before trusting the user ID.
        if json.loads(_unb64(header)).get("alg") != "HS256":
            raise ValueError("Unsupported token algorithm.")
        if int(claims["exp"]) <= int(time.time()):
            raise ValueError("Token has expired.")
        return int(claims["sub"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid or expired access token.") from exc


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _unb64(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _encode(value: dict) -> str:
    return _b64(json.dumps(value, separators=(",", ":"), sort_keys=True).encode())
