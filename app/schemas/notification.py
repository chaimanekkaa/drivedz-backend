from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    title: str
    message: str
    is_read: bool
    created_at: datetime


class NotificationsResponse(BaseModel):
    items: list[NotificationOut]
    unread_count: int
