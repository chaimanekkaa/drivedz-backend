from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.phone import clean_phone
from app.core.security import burn_password_check, create_access_token, hash_password, verify_password
from app.database import get_db
from app.deps import get_current_user, get_token_payload, require_admin
from app.models.user import RoleEnum, User
from app.schemas.auth import ChangePasswordIn, TokenResponse, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    phone = clean_phone(form_data.username)
    user = db.query(User).filter(User.phone == phone).first()
    if user is None:
        burn_password_check(form_data.password)
        raise HTTPException(status_code=401, detail="Téléphone ou mot de passe incorrect.")
    if not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Téléphone ou mot de passe incorrect.")
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(access_token=token, role=user.role.value, full_name=user.full_name)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/change-password")
def change_password(data: ChangePasswordIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not verify_password(data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Ancien mot de passe incorrect.")
    current_user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "Mot de passe modifié."}


@router.post("/impersonate/{instructor_id}", response_model=TokenResponse)
def impersonate(instructor_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    instructor = db.query(User).filter(User.id == instructor_id, User.role == RoleEnum.instructor).first()
    if instructor is None:
        raise HTTPException(status_code=404, detail="Moniteur introuvable.")
    token = create_access_token(
        {"sub": str(instructor.id), "role": instructor.role.value, "real_user_id": str(admin.id)}
    )
    return TokenResponse(access_token=token, role=instructor.role.value, full_name=instructor.full_name)


@router.post("/stop-impersonate", response_model=TokenResponse)
def stop_impersonate(payload: dict = Depends(get_token_payload), db: Session = Depends(get_db)):
    real_user_id = payload.get("real_user_id")
    if not real_user_id:
        raise HTTPException(status_code=400, detail="Vous n'êtes pas en mode « connecté en tant que ».")
    admin = db.get(User, int(real_user_id))
    if admin is None or admin.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Compte administrateur introuvable.")
    token = create_access_token({"sub": str(admin.id), "role": admin.role.value})
    return TokenResponse(access_token=token, role=admin.role.value, full_name=admin.full_name)
