from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin, require_staff
from app.models.driving_session import DrivingSession
from app.models.user import User
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleOut, VehicleUpdate

router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@router.get("/", response_model=List[VehicleOut])
def list_vehicles(db: Session = Depends(get_db), staff: User = Depends(require_staff)):
    return db.query(Vehicle).order_by(Vehicle.model, Vehicle.plate).all()


@router.post("/", response_model=VehicleOut, status_code=201)
def create_vehicle(data: VehicleCreate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    if db.query(Vehicle).filter(Vehicle.plate == data.plate).first():
        raise HTTPException(status_code=409, detail="Cette plaque d'immatriculation existe déjà.")
    vehicle = Vehicle(plate=data.plate, model=data.model)
    db.add(vehicle)
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.put("/{vehicle_id}", response_model=VehicleOut)
def update_vehicle(vehicle_id: int, data: VehicleUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Véhicule introuvable.")
    if data.plate and data.plate != vehicle.plate:
        if db.query(Vehicle).filter(Vehicle.plate == data.plate, Vehicle.id != vehicle_id).first():
            raise HTTPException(status_code=409, detail="Cette plaque d'immatriculation existe déjà.")
        vehicle.plate = data.plate
    if data.model:
        vehicle.model = data.model
    if data.status:
        vehicle.status = data.status
    db.commit()
    db.refresh(vehicle)
    return vehicle


@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(vehicle_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    vehicle = db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=404, detail="Véhicule introuvable.")
    if db.query(DrivingSession).filter(DrivingSession.vehicle_id == vehicle_id).first():
        raise HTTPException(status_code=409, detail="Ce véhicule est utilisé dans des séances : passez-le plutôt en maintenance.")
    db.delete(vehicle)
    db.commit()
