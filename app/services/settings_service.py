from sqlalchemy.orm import Session

from app.models.settings import AutoEcoleInfo, Pricing


def get_pricing(db: Session) -> Pricing:
    obj = db.get(Pricing, 1)
    if obj is None:
        obj = Pricing(id=1)
        db.add(obj)
        db.commit()
        db.refresh(obj)
    return obj


def get_info(db: Session) -> AutoEcoleInfo:
    obj = db.get(AutoEcoleInfo, 1)
    if obj is None:
        obj = AutoEcoleInfo(id=1)
        db.add(obj)
        db.commit()
        db.refresh(obj)
    return obj
