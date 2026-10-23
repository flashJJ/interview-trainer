from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import User
from .security import decode_token

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="未登录或登录已过期，请重新登录",
    )
    if credentials is None:
        raise unauthorized
    payload = decode_token(credentials.credentials)
    if not payload or "sub" not in payload:
        raise unauthorized
    user = db.get(User, int(payload["sub"]))
    if user is None:
        raise unauthorized
    return user
