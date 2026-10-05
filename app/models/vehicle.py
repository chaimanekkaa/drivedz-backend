import enum

from sqlalchemy import Column, Enum, Integer, String

from app.database import Base


class VehicleStatusEnum(str, enum.Enum):
    disponible = "disponible"
    maintenance = "maintenance"


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    plate = Column(String(30), unique=True, nullable=False)
    model = Column(String(80), nullable=False)
    status = Column(Enum(VehicleStatusEnum, native_enum=False, length=20), nullable=False, default=VehicleStatusEnum.disponible)
