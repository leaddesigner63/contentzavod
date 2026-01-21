from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from . import schemas
from .dependencies import get_store
from .storage_db import DatabaseStore

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(
    data: dict,
    secret_key: str,
    algorithm: str,
    expires_delta: timedelta,
) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, secret_key, algorithm=algorithm)


def authenticate_user(
    store: DatabaseStore, email: str, password: str
) -> schemas.User | None:
    user = store.get_user_by_email(email)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return store.to_user_schema(user)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    store: DatabaseStore = Depends(get_store),
) -> schemas.User:
    secret_key = store.jwt_secret_key
    algorithm = store.jwt_algorithm
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="could_not_validate_credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, secret_key, algorithms=[algorithm])
        email: str | None = payload.get("sub")
        if not email:
            raise credentials_exception
    except JWTError as exc:
        raise credentials_exception from exc
    user = store.get_user_by_email(email)
    if not user:
        raise credentials_exception
    return store.to_user_schema(user)


def require_roles(*roles: str):
    def dependency(current_user: schemas.User = Depends(get_current_user)) -> schemas.User:
        if not any(role in current_user.roles for role in roles):
            raise HTTPException(status_code=403, detail="insufficient_permissions")
        return current_user

    return dependency
