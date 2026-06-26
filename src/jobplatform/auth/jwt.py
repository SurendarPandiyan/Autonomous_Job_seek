from datetime import datetime, timedelta, timezone
from typing import Literal

from jose import JWTError, jwt

from jobplatform.config import settings

ALGORITHM = "HS256"


def create_token(subject: str, token_type: Literal["access", "refresh"]) -> str:
    """Create a JWT token with subject and type.

    Args:
        subject: The subject claim (typically user ID as string)
        token_type: Either "access" (15 min) or "refresh" (7 days)

    Returns:
        Encoded JWT token string
    """
    expire_delta = (
        timedelta(minutes=settings.access_token_expire_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_expire_days)
    )
    payload = {
        "sub": subject,
        "type": token_type,
        "exp": datetime.now(timezone.utc) + expire_delta,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str, expected_type: Literal["access", "refresh"]) -> str:
    """Decode and validate a JWT token.

    Args:
        token: The JWT token string to decode
        expected_type: Expected token type ("access" or "refresh")

    Returns:
        The subject claim from the token

    Raises:
        ValueError: If token is invalid, expired, or type doesn't match
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError as e:
        raise ValueError(str(e)) from e
    if payload.get("type") != expected_type:
        raise ValueError(f"Expected token type '{expected_type}', got '{payload.get('type')}'")
    sub = payload.get("sub")
    if sub is None:
        raise ValueError("Token missing 'sub'")
    return sub
