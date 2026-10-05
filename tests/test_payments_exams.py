from datetime import timedelta

from conftest import create_student, login
from app.core.time import today_dz

import test_sessions as ts


def d(delta):
    return (today_dz() + timedelta(days=delta)).isoformat()


def test_payment_validation(client, world, amine_h, wassila_h):
    s = create_student(client, amine_h, "Payeur Test", "0770000301", "m")
    assert client.post("/payments/", headers=amine_h, json={"student_id": s["id"], "amount": -500}).status_code == 422
    assert client.post("/payments/", headers=amine_h, json={"student_id": s["id"], "amount": 0}).status_code == 422
    assert client.post("/payments/", headers=amine_h, json={"student_id": 99999, "amount": 1000}).status_code == 404
    assert client.post("/payments/", headers=amine_h, json={"student_id": world["amine"].id, "amount": 1000}).status_code == 404
    assert client.post("/payments/", headers=wassila_h, json={"student_id": s["id"], "amount": 1000}).status_code == 404  # autre genre
    assert client.post("/payments/", headers=amine_h, json={"student_id": s["id"], "amount": 1000, "paid_at": d(3)}).status_code == 422
    assert client.post("/payments/", headers=amine_h, json={"student_id": s["id"], "amount": 30000}).status_code == 400  # > reste à payer
    ok = client.post("/payments/", headers=amine_h, json={"student_id": s["id"], "amount": 5000})
    assert ok.status_code == 201 and ok.json()["receipt_number"].startswith("REC-")
    p = client.get(f"/users/{s['id']}/progress", headers=amine_h).json()
    assert p["total_paid"] == 5000 and p["remaining"] == 15000
    assert len(client.get(f"/payments/{s['id']}", headers=amine_h).json()) == 1


def test_exam_creation_rules(client, world, amine_h):
    assert client.post("/exams/sessions", headers=amine_h, json={"phase": "code", "date": "2020-01-01"}).status_code == 422
    ok = client.post("/exams/sessions", headers=amine_h, json={"phase": "code", "date": d(5)})
    assert ok.status_code == 201
    assert client.post("/exams/sessions", headers=amine_h, json={"phase": "code", "date": d(5)}).status_code == 409


def _ready_code_student(client, headers, db, name, phone, gender="m"):
    s = create_student(client, headers, name, phone, gender)
    from app.models.student_profile import StudentProfile
    p = db.query(StudentProfile).filter(StudentProfile.user_id == s["id"]).first()
    p.hours_code = 8.0
    db.commit()
    return s


def test_exam_request_requires_hours_and_right_phase(client, world, amine_h, db):
    exam = client.post("/exams/sessions", headers=amine_h, json={"phase": "code", "date": d(5)}).json()
    exam2 = client.post("/exams/sessions", headers=amine_h, json={"phase": "creneau", "date": d(6)}).json()
    s = create_student(client, amine_h, "Pas Pret", "0770000302", "m")
    h = login(client, "0770000302", "Student#123")
    r = client.post("/exams/registrations", headers=h, json={"exam_session_id": exam["id"]})
    assert r.status_code == 400 and "manque" in r.json()["detail"]
    ready = _ready_code_student(client, amine_h, db, "Pret Code", "0770000303")
    h2 = login(client, "0770000303", "Student#123")
    assert client.post("/exams/registrations", headers=h2, json={"exam_session_id": exam2["id"]}).status_code == 400  # mauvaise épreuve
    assert client.post("/exams/registrations", headers=h2, json={"exam_session_id": exam["id"]}).status_code == 201
    assert client.post("/exams/registrations", headers=h2, json={"exam_session_id": exam["id"]}).status_code == 409  # doublon
    assert client.post("/exams/registrations", headers=amine_h, json={"exam_session_id": exam["id"]}).status_code == 403  # le staff n'est pas candidat


def test_full_exam_flow_accept_is_not_pass(client, world, amine_h, db):
    exam = client.post("/exams/sessions", headers=amine_h, json={"phase": "code", "date": d(5)}).json()
    s = _ready_code_student(client, amine_h, db, "Flow Test", "0770000304")
    h = login(client, "0770000304", "Student#123")
    reg = client.post("/exams/registrations", headers=h, json={"exam_session_id": exam["id"]}).json()
    # le moniteur reçoit une notification
    assert any(n["kind"] == "exam_request" for n in client.get("/notifications/", headers=amine_h).json()["items"])

    # ACCEPTER = autorisé à passer l'examen, PAS de changement de phase
    r = client.put(f"/exams/registrations/{reg['id']}", headers=amine_h, json={"status": "accepted"})
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    assert client.get(f"/users/{s['id']}/progress", headers=amine_h).json()["current_phase"] == "code"
    # résultat impossible avant la date d'examen
    assert client.put(f"/exams/registrations/{reg['id']}", headers=amine_h, json={"status": "passed"}).status_code == 400


def test_exam_result_passed_advances_and_failed_allows_retry(client, world, amine_h, db):
    from app.models.exam_session import ExamSession
    from app.models.student_profile import PhaseEnum
    past = ExamSession(phase=PhaseEnum.code, date=today_dz())  # examen aujourd'hui => résultat saisissable
    later = ExamSession(phase=PhaseEnum.code, date=today_dz() + timedelta(days=10))
    db.add_all([past, later]); db.commit()

    s = _ready_code_student(client, amine_h, db, "Result Test", "0770000305")
    h = login(client, "0770000305", "Student#123")
    reg = client.post("/exams/registrations", headers=h, json={"exam_session_id": past.id}).json()
    client.put(f"/exams/registrations/{reg['id']}", headers=amine_h, json={"status": "accepted"})

    # échec : on ne bouge pas de phase, on peut redemander une autre date
    assert client.put(f"/exams/registrations/{reg['id']}", headers=amine_h, json={"status": "failed"}).status_code == 200
    assert client.get(f"/users/{s['id']}/progress", headers=amine_h).json()["current_phase"] == "code"
    reg2 = client.post("/exams/registrations", headers=h, json={"exam_session_id": later.id})
    assert reg2.status_code == 201
    # un résultat est définitif
    assert client.put(f"/exams/registrations/{reg['id']}", headers=amine_h, json={"status": "passed"}).status_code == 409
    # une demande en attente peut être refusée, mais un refus est définitif
    rid = reg2.json()["id"]
    assert client.put(f"/exams/registrations/{rid}", headers=amine_h, json={"status": "refused"}).status_code == 200
    assert client.put(f"/exams/registrations/{rid}", headers=amine_h, json={"status": "accepted"}).status_code == 409
    assert client.get(f"/users/{s['id']}/progress", headers=amine_h).json()["current_phase"] == "code"


def test_passed_result_advances_phase(client, world, amine_h, db):
    from app.models.exam_session import ExamSession
    from app.models.student_profile import PhaseEnum
    e = ExamSession(phase=PhaseEnum.code, date=today_dz()); db.add(e); db.commit()
    s = _ready_code_student(client, amine_h, db, "Passe Test", "0770000306")
    h = login(client, "0770000306", "Student#123")
    reg = client.post("/exams/registrations", headers=h, json={"exam_session_id": e.id}).json()
    # on ne peut pas saisir un résultat sans autorisation préalable
    assert client.put(f"/exams/registrations/{reg['id']}", headers=amine_h, json={"status": "passed"}).status_code == 409
    client.put(f"/exams/registrations/{reg['id']}", headers=amine_h, json={"status": "accepted"})
    assert client.put(f"/exams/registrations/{reg['id']}", headers=amine_h, json={"status": "passed"}).status_code == 200
    p = client.get(f"/users/{s['id']}/progress", headers=amine_h).json()
    assert p["current_phase"] == "creneau"
    assert [x["status"] for x in p["phases"]] == ["done", "current", "locked"]
    kinds = [n["kind"] for n in client.get("/notifications/", headers=h).json()["items"]]
    assert "exam_passed" in kinds and "exam_accepted" in kinds


def test_final_exam_completes_course(client, world, amine_h, db):
    from app.models.exam_session import ExamSession
    from app.models.student_profile import PhaseEnum, StudentProfile
    s = create_student(client, amine_h, "Final Test", "0770000307", "m")
    client.put(f"/users/{s['id']}/phase", headers=amine_h, json={"phase": "circulation"})
    p = db.query(StudentProfile).filter(StudentProfile.user_id == s["id"]).first(); p.hours_circulation = 8.0; db.commit()
    e = ExamSession(phase=PhaseEnum.circulation, date=today_dz()); db.add(e); db.commit()
    h = login(client, "0770000307", "Student#123")
    reg = client.post("/exams/registrations", headers=h, json={"exam_session_id": e.id}).json()
    client.put(f"/exams/registrations/{reg['id']}", headers=amine_h, json={"status": "accepted"})
    client.put(f"/exams/registrations/{reg['id']}", headers=amine_h, json={"status": "passed"})
    prog = client.get(f"/users/{s['id']}/progress", headers=amine_h).json()
    assert prog["course_completed"] is True and prog["ready_for_exam"] is False
    assert [x["status"] for x in prog["phases"]] == ["done", "done", "done"]


def test_exam_registrations_are_gender_scoped(client, world, amine_h, wassila_h, db):
    exam = client.post("/exams/sessions", headers=amine_h, json={"phase": "code", "date": d(5)}).json()
    boy = _ready_code_student(client, amine_h, db, "Garcon Exam", "0770000308", "m")
    girl = _ready_code_student(client, wassila_h, db, "Fille Exam", "0770000309", "f")
    for phone in ("0770000308", "0770000309"):
        client.post("/exams/registrations", headers=login(client, phone, "Student#123"), json={"exam_session_id": exam["id"]})
    a = client.get("/exams/registrations", headers=amine_h).json()
    w = client.get("/exams/registrations", headers=wassila_h).json()
    assert [r["student_name"] for r in a] == ["Garcon Exam"]
    assert [r["student_name"] for r in w] == ["Fille Exam"]
    # Wassila ne peut pas trancher sur la demande d'un garçon
    assert client.put(f"/exams/registrations/{a[0]['id']}", headers=wassila_h, json={"status": "accepted"}).status_code == 404


def test_delete_exam_session_only_if_empty(client, world, amine_h, db):
    e1 = client.post("/exams/sessions", headers=amine_h, json={"phase": "code", "date": d(8)}).json()
    e2 = client.post("/exams/sessions", headers=amine_h, json={"phase": "code", "date": d(9)}).json()
    _ready_code_student(client, amine_h, db, "Del Exam", "0770000310")
    client.post("/exams/registrations", headers=login(client, "0770000310", "Student#123"), json={"exam_session_id": e1["id"]})
    assert client.delete(f"/exams/sessions/{e1['id']}", headers=amine_h).status_code == 409
    assert client.delete(f"/exams/sessions/{e2['id']}", headers=amine_h).status_code == 204


def test_manual_phase_keeps_hours_coherent(client, world, amine_h):
    s = create_student(client, amine_h, "Ailleurs Test", "0770000311", "m")
    client.put(f"/users/{s['id']}/phase", headers=amine_h, json={"phase": "circulation"})
    p = client.get(f"/users/{s['id']}/progress", headers=amine_h).json()
    assert (p["hours_code"], p["hours_creneau"], p["hours_circulation"]) == (8, 8, 0)
    client.put(f"/users/{s['id']}/phase", headers=amine_h, json={"phase": "creneau"})
    p = client.get(f"/users/{s['id']}/progress", headers=amine_h).json()
    assert (p["hours_code"], p["hours_creneau"], p["hours_circulation"]) == (8, 8, 0)


def test_validate_phase_requires_hours(client, world, amine_h, db):
    s = create_student(client, amine_h, "Valid Test", "0770000312", "m")
    r = client.post(f"/users/{s['id']}/validate-phase", headers=amine_h)
    assert r.status_code == 400 and "manque" in r.json()["detail"]


def test_settings_permissions(client, world, amine_h, wassila_h):
    assert client.get("/settings/pricing", headers=wassila_h).status_code == 200
    assert client.put("/settings/pricing", headers=wassila_h, json={"permit_fee": 1}).status_code == 403
    assert client.put("/settings/pricing", headers=amine_h, json={"permit_fee": 25000}).json()["permit_fee"] == 25000
    assert client.put("/settings/pricing", headers=amine_h, json={"permit_fee": -1}).status_code == 422
    assert client.put("/settings/info", headers=amine_h, json={"phone": "0550000001", "address": "Sétif"}).status_code == 200


def test_vehicle_admin_only_and_status_change(client, world, amine_h, wassila_h):
    v = client.post("/vehicles/", headers=amine_h, json={"plate": "999 ZZZ", "model": "Symbol"})
    assert v.status_code == 201
    assert client.post("/vehicles/", headers=amine_h, json={"plate": "999 ZZZ", "model": "Symbol"}).status_code == 409
    assert client.post("/vehicles/", headers=wassila_h, json={"plate": "888 YYY", "model": "Symbol"}).status_code == 403
    r = client.put(f"/vehicles/{v.json()['id']}", headers=amine_h, json={"status": "maintenance"})
    assert r.json()["status"] == "maintenance"


def test_notifications_read_flow(client, world, amine_h):
    s = create_student(client, amine_h, "Notif Test", "0770000313", "m")
    client.put(f"/users/{s['id']}/phase", headers=amine_h, json={"phase": "creneau"})
    h = login(client, "0770000313", "Student#123")
    data = client.get("/notifications/", headers=h).json()
    assert data["unread_count"] == 1
    assert client.post(f"/notifications/{data['items'][0]['id']}/read", headers=h).status_code == 200
    assert client.get("/notifications/", headers=h).json()["unread_count"] == 0
    # on ne peut pas lire la notification d'un autre
    assert client.post(f"/notifications/{data['items'][0]['id']}/read", headers=amine_h).status_code == 404
