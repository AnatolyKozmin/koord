from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.config import get_settings


def create_access_token(subject: str, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(tz=UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "role": role, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
