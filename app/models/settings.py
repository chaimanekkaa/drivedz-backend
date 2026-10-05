from sqlalchemy import Column, Integer, String

from app.database import Base


class Pricing(Base):
    __tablename__ = "pricing"

    id = Column(Integer, primary_key=True, default=1)
    permit_fee = Column(Integer, nullable=False, default=20000)      # forfait Permis B (DA)
    extra_hour_fee = Column(Integer, nullable=False, default=1500)   # heure supplémentaire (DA)
    exam_fee = Column(Integer, nullable=False, default=250)          # informatif : versé à l'examinateur


class AutoEcoleInfo(Base):
    __tablename__ = "auto_ecole_info"

    id = Column(Integer, primary_key=True, default=1)
    business_name = Column(String(150), nullable=False, default="")
    agreement_number = Column(String(80), nullable=False, default="")
    director_name = Column(String(120), nullable=False, default="")
    wilaya = Column(String(80), nullable=False, default="")
    commune = Column(String(80), nullable=False, default="")
    address = Column(String(250), nullable=False, default="")
    phone = Column(String(20), nullable=False, default="")
