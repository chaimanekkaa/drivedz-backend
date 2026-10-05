from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.time import today_dz
from app.database import get_db
from app.deps import get_current_user, require_staff
from app.models.payment import Payment
from app.models.user import RoleEnum, User
from app.schemas.payment import PaymentCreate, PaymentOut
from app.services import pipeline_service as ps
from app.services.notification_service import notify
from app.services.scope import get_scoped_student
from app.services.settings_service import get_pricing

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/", response_model=PaymentOut, status_code=201)
def create_payment(data: PaymentCreate, db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    user, profile = get_scoped_student(db, staff, data.student_id)

    paid = ps.total_paid_map(db, [user.id]).get(user.id, 0)
    remaining = max(0, ps.total_due(profile, get_pricing(db)) - paid)
    if remaining == 0:
        raise HTTPException(status_code=400, detail="Ce candidat a déjà tout réglé.")
    if data.amount > remaining:
        raise HTTPException(status_code=400, detail=f"Montant supérieur au reste à payer ({remaining} DA).")

    paid_at = data.paid_at or today_dz()
    payment = Payment(student_id=user.id, amount=data.amount, paid_at=paid_at, recorded_by=staff.id)
    db.add(payment)
    db.flush()
    payment.receipt_number = f"REC-{paid_at.year}-{payment.id:05d}"
    notify(db, user.id, "payment", "Paiement enregistré", f"{data.amount} DA reçus (reçu {payment.receipt_number}).")
    db.commit()
    db.refresh(payment)
    return payment


@router.get("/{student_id}", response_model=List[PaymentOut])
def list_payments(student_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == RoleEnum.student:
        if current_user.id != student_id:
            raise HTTPException(status_code=403, detail="Accès refusé.")
    else:
        get_scoped_student(db, current_user, student_id)
    return db.query(Payment).filter(Payment.student_id == student_id).order_by(Payment.paid_at.desc(), Payment.id.desc()).all()
