"""Création des comptes de base et (optionnellement) de données de démonstration.

    python -m app.seed            -> crée l'administrateur (et un moniteur si vous le souhaitez), en interactif
    python -m app.seed --demo     -> comptes + candidats, véhicules, examens... (mots de passe de démo, DEV uniquement)
"""
import argparse
import getpass
from datetime import timedelta

from app import models  # noqa: F401
from app.core.phone import normalize_phone
from app.core.security import hash_password
from app.core.time import today_dz
from app.database import SessionLocal
from app.models.driving_session import DrivingSession, SessionAttendance
from app.models.exam_session import ExamSession
from app.models.payment import Payment
from app.models.student_profile import PhaseEnum, StudentProfile
from app.models.user import GenderEnum, RoleEnum, User
from app.models.vehicle import Vehicle, VehicleStatusEnum
from app.services.settings_service import get_info, get_pricing


def get_or_create_user(db, *, full_name, phone, password, role, gender) -> User:
    phone = normalize_phone(phone)
    user = db.query(User).filter(User.phone == phone).first()
    if user:
        return user
    user = User(full_name=full_name, phone=phone, password_hash=hash_password(password), role=role, gender=gender)
    db.add(user)
    db.flush()
    return user


def add_student(db, instructor: User, name, phone, phase, hours, paid=0, password="Student#123"):
    fee = get_pricing(db).permit_fee
    user = get_or_create_user(db, full_name=name, phone=phone, password=password, role=RoleEnum.student, gender=instructor.gender)
    if db.query(StudentProfile).filter(StudentProfile.user_id == user.id).first():
        return user
    profile = StudentProfile(user_id=user.id, instructor_id=instructor.id, agreed_fee=fee, current_phase=phase)
    order = ["code", "creneau", "circulation"]
    for key in order[: order.index(phase.value)]:
        setattr(profile, f"hours_{key}", 8.0)
    setattr(profile, f"hours_{phase.value}", float(hours))
    db.add(profile)
    db.flush()
    if paid:
        p = Payment(student_id=user.id, amount=paid, paid_at=today_dz(), recorded_by=instructor.id)
        db.add(p)
        db.flush()
        p.receipt_number = f"REC-{today_dz().year}-{p.id:05d}"
    return user


def seed_demo(db):
    info = get_info(db)
    info.business_name = "Auto-École DriveDZ"
    info.agreement_number = "AG-2019-0457"
    info.director_name = "Amine Belkacem"
    info.wilaya, info.commune = "Sétif", "Sétif"
    info.address = "Cité El-Hidhab, Sétif"
    info.phone = "0550000001"

    amine = get_or_create_user(db, full_name="Amine Belkacem", phone="0550000001", password="Admin#123", role=RoleEnum.admin, gender=GenderEnum.m)
    wassila = get_or_create_user(db, full_name="Wassila Cherif", phone="0660000002", password="Wassila#123", role=RoleEnum.instructor, gender=GenderEnum.f)

    for plate, model, st in [("305 12345 19", "Peugeot 208", VehicleStatusEnum.disponible),
                             ("112 67890 19", "Renault Clio 4", VehicleStatusEnum.disponible),
                             ("078 24680 19", "Dacia Logan", VehicleStatusEnum.maintenance)]:
        if not db.query(Vehicle).filter(Vehicle.plate == plate).first():
            db.add(Vehicle(plate=plate, model=model, status=st))

    add_student(db, amine, "Yacine Boudiaf", "0770000001", PhaseEnum.code, 4, paid=8000)
    add_student(db, amine, "Sofiane Kaci", "0770000002", PhaseEnum.creneau, 4, paid=15000)
    add_student(db, amine, "Rayan Mansouri", "0770000003", PhaseEnum.circulation, 8, paid=20000)
    add_student(db, wassila, "Meriem Haddad", "0770000004", PhaseEnum.code, 8, paid=20000)
    add_student(db, wassila, "Amina Larbi", "0770000005", PhaseEnum.creneau, 7, paid=10000)
    add_student(db, wassila, "Nesrine Belaid", "0770000006", PhaseEnum.circulation, 5, paid=5000)

    today = today_dz()
    for phase, delta in [(PhaseEnum.code, 7), (PhaseEnum.creneau, 14), (PhaseEnum.circulation, 21)]:
        d = today + timedelta(days=delta)
        if not db.query(ExamSession).filter(ExamSession.phase == phase, ExamSession.date == d).first():
            db.add(ExamSession(phase=phase, date=d))
    db.flush()

    # Quelques séances d'exemple
    from datetime import time
    v1 = db.query(Vehicle).filter(Vehicle.plate == "305 12345 19").first()
    v2 = db.query(Vehicle).filter(Vehicle.plate == "112 67890 19").first()
    sofiane = db.query(User).filter(User.phone == "0770000002").first()
    amina = db.query(User).filter(User.phone == "0770000005").first()
    yacine = db.query(User).filter(User.phone == "0770000001").first()
    if not db.query(DrivingSession).first():
        s1 = DrivingSession(instructor_id=amine.id, date=today, start_time=time(9, 0), end_time=time(9, 30), phase=PhaseEnum.creneau, vehicle_id=v1.id)
        s2 = DrivingSession(instructor_id=wassila.id, date=today, start_time=time(10, 0), end_time=time(10, 30), phase=PhaseEnum.creneau, vehicle_id=v2.id)
        s3 = DrivingSession(instructor_id=amine.id, date=today + timedelta(days=1), start_time=time(8, 0), end_time=time(9, 0), phase=PhaseEnum.code, group_label="Groupe A")
        db.add_all([s1, s2, s3])
        db.flush()
        db.add_all([SessionAttendance(session_id=s1.id, student_id=sofiane.id),
                    SessionAttendance(session_id=s2.id, student_id=amina.id),
                    SessionAttendance(session_id=s3.id, student_id=yacine.id)])


def interactive(db):
    print("=== Création du compte administrateur ===")
    name = input("Nom complet : ").strip()
    phone = input("Téléphone (05/06/07...) : ").strip()
    gender = input("Genre (m/f) : ").strip().lower()
    password = getpass.getpass("Mot de passe (min. 6 caractères) : ")
    get_or_create_user(db, full_name=name, phone=phone, password=password, role=RoleEnum.admin, gender=GenderEnum(gender))
    if input("Créer aussi un compte moniteur ? (o/N) ").strip().lower() == "o":
        name = input("Nom complet du moniteur : ").strip()
        phone = input("Téléphone : ").strip()
        gender = input("Genre (m/f) : ").strip().lower()
        password = getpass.getpass("Mot de passe : ")
        get_or_create_user(db, full_name=name, phone=phone, password=password, role=RoleEnum.instructor, gender=GenderEnum(gender))


def main(demo: bool = False):
    db = SessionLocal()
    try:
        get_pricing(db)
        get_info(db)
        if demo:
            seed_demo(db)
        else:
            interactive(db)
        db.commit()
    finally:
        db.close()
    if demo:
        print("\nComptes de démonstration (NE PAS utiliser en production) :")
        print("  Admin      0550000001 / Admin#123     (Amine, gère les hommes)")
        print("  Moniteur   0660000002 / Wassila#123   (Wassila, gère les femmes)")
        print("  Candidats  0770000001 ... 0770000006 / Student#123")
    else:
        print("Compte(s) créé(s).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    main(ap.parse_args().demo)
