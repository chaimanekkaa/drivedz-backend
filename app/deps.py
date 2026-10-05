from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import RoleEnum, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expirée ou invalide, veuillez vous reconnecter.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_token_payload(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        return decode_access_token(token)
    except Exception:
        raise _unauthorized()


def get_current_user(payload: dict = Depends(get_token_payload), db: Session = Depends(get_db)) -> User:
    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise _unauthorized()
    user = db.get(User, user_id)
    if user is None:
        raise _unauthorized()
    return user


def require_staff(user: User = Depends(get_current_user)) -> User:
    """Admin ou moniteur uniquement."""
    if user.role == RoleEnum.student:
        raise HTTPException(status_code=403, detail="Accès réservé au personnel de l'auto-école.")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Action réservée à l'administrateur.")
    return user


def require_student(user: User = Depends(get_current_user)) -> User:
    if user.role != RoleEnum.student:
        raise HTTPException(status_code=403, detail="Action réservée aux candidats.")
    return user
