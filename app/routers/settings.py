from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user, require_admin
from app.models.user import User
from app.schemas.settings import InfoOut, InfoUpdate, PricingOut, PricingUpdate
from app.services.settings_service import get_info, get_pricing

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/pricing", response_model=PricingOut)
def read_pricing(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_pricing(db)


@router.put("/pricing", response_model=PricingOut)
def update_pricing(data: PricingUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    pricing = get_pricing(db)
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(pricing, field, value)
    db.commit()
    db.refresh(pricing)
    return pricing


@router.get("/info", response_model=InfoOut)
def read_info(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return get_info(db)


@router.put("/info", response_model=InfoOut)
def update_info(data: InfoUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    info = get_info(db)
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(info, field, value.strip())
    db.commit()
    db.refresh(info)
    return info
