import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-tests-only-0123456789abcdef")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.core.security import hash_password
from app.database import Base, get_db
from app.main import app
from app.models.user import GenderEnum, RoleEnum, User
from app.models.vehicle import Vehicle, VehicleStatusEnum


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def client(db):
    def _get_db():
        yield db

    app.dependency_overrides[get_db] = _get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def make_user(db, name, phone, role, gender, password="Secret#123"):
    u = User(full_name=name, phone=phone, password_hash=hash_password(password), role=role, gender=gender)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def world(db):
    """Amine (admin, homme), Wassila (moniteur, femme), 2 véhicules dont un en maintenance."""
    amine = make_user(db, "Amine Belkacem", "0550000001", RoleEnum.admin, GenderEnum.m)
    wassila = make_user(db, "Wassila Cherif", "0660000002", RoleEnum.instructor, GenderEnum.f)
    v1 = Vehicle(plate="111 AAA", model="Peugeot 208")
    v2 = Vehicle(plate="222 BBB", model="Clio 4")
    v3 = Vehicle(plate="333 CCC", model="Logan", status=VehicleStatusEnum.maintenance)
    db.add_all([v1, v2, v3])
    db.commit()
    return {"amine": amine, "wassila": wassila, "v1": v1, "v2": v2, "v3": v3}


def login(client, phone, password="Secret#123"):
    r = client.post("/auth/login", data={"username": phone, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def amine_h(client, world):
    return login(client, "0550000001")


@pytest.fixture()
def wassila_h(client, world):
    return login(client, "0660000002")


def create_student(client, headers, name, phone, gender, password="Student#123"):
    r = client.post("/users/", headers=headers, json={"full_name": name, "phone": phone, "password": password, "role": "student", "gender": gender})
    assert r.status_code == 201, r.text
    return r.json()
