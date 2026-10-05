from sqlalchemy.orm import Session

from app.models.notification import Notification


def notify(db: Session, user_id: int | None, kind: str, title: str, message: str) -> None:
    """Ajoute une notification (le commit est fait par l'appelant, dans la même transaction)."""
    if user_id is None:
        return
    db.add(Notification(user_id=user_id, kind=kind, title=title[:120], message=message[:300]))
