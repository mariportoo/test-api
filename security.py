import hashlib
import os
import secrets
import string
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

from fastapi import Depends, Header, HTTPException, Query, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from database import get_db
from models import AccessTokenModel, ClientModel

load_dotenv()

ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY")
ACCESS_TOKEN_EXPIRE_HOURS = 24

# HTTP Basic scheme for browser-based docs
basic_security = HTTPBasic()


def generate_alphanumeric_str(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def hash_password(password: str, salt: Optional[str] = None):
    salt = salt or secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()
    return pwd_hash, salt


def verify_password(password: str, salt: str, hashed: str) -> bool:
    pwd_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(pwd_hash, hashed)


def authenticate_admin(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    authorization: Optional[str] = Header(None),
):
    """Admin guard for REST API endpoints using headers."""
    bearer = None
    if authorization and authorization.startswith("Bearer "):
        bearer = authorization.split("Bearer ", 1)[1].strip()

    provided_key = x_admin_key or bearer
    if not provided_key or not secrets.compare_digest(provided_key, ADMIN_SECRET_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: Invalid admin credentials.",
        )
    return True


def authenticate_admin_docs(credentials: HTTPBasicCredentials = Depends(basic_security)):
    """Browser popup guard for /admindocs and /admin-openapi.json."""
    is_password_valid = secrets.compare_digest(credentials.password, ADMIN_SECRET_KEY)
    is_username_valid = secrets.compare_digest(credentials.username, "admin") or secrets.compare_digest(credentials.username, ADMIN_SECRET_KEY)

    # Accepts either username="admin" + password=<ADMIN_SECRET_KEY> or entering the secret key directly
    if not (is_password_valid or (is_username_valid and not credentials.password)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect administration credentials.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return True


def authenticate_client(
    client_id: str,
    x_token: Optional[str] = Header(None, alias="X-Token"),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    bearer = None
    if authorization and authorization.startswith("Bearer "):
        bearer = authorization.split("Bearer ", 1)[1].strip()

    provided_token = x_token or bearer or token
    if not provided_token:
        raise HTTPException(status_code=403, detail="Authentication token missing.")

    token_record = (
        db.query(AccessTokenModel)
        .filter(
            AccessTokenModel.token == provided_token,
            AccessTokenModel.client_id == client_id,
        )
        .first()
    )

    if not token_record:
        raise HTTPException(status_code=403, detail="Invalid token or client ID.")

    now = datetime.now(timezone.utc)
    token_expires = (
        token_record.expires_at.replace(tzinfo=timezone.utc)
        if token_record.expires_at.tzinfo is None
        else token_record.expires_at
    )

    if now > token_expires:
        raise HTTPException(
            status_code=403,
            detail="Token expired. Request a new token via /auth/token.",
        )

    client = (
        db.query(ClientModel)
        .filter(ClientModel.client_id == client_id, ClientModel.is_active == True)
        .first()
    )

    if not client:
        raise HTTPException(status_code=403, detail="Client inactive or deleted.")

    client.last_used_at = now
    db.commit()
    return client