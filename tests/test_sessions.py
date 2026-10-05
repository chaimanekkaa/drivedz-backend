from datetime import timedelta

from conftest import create_student
from app.core.time import today_dz


def iso(delta=0):
    return (today_dz() + timedelta(days=delta)).isoformat()


def payload(student_ids, vehicle_id, *, date=None, start="09:00:00", end="09:30:00", phase="creneau", **extra):
    d = {"phase": phase, "date": date or iso(0), "start_time": start, "end_time": end, "vehicle_id": vehicle_id, "student_ids": student_ids}
    d.update(extra)
    return d


def setup_creneau_student(client, headers, name, phone, gender="m"):
    s = create_student(client, headers, name, phone, gender)
    assert client.put(f"/users/{s['id']}/phase", headers=headers, json={"phase": "creneau"}).status_code == 200
    return s


def test_create_session_ok_and_visible_to_student(client, world, amine_h):
    s = setup_creneau_student(client, amine_h, "Sofiane Kaci", "0770000001")
    r = client.post("/planning/", headers=amine_h, json=payload([s["id"]], world["v1"].id))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["attendances"][0]["student_name"] == "Sofiane Kaci"
    assert body["vehicle_label"] == "Peugeot 208 — 111 AAA"
    assert body["instructor_name"] == "Amine Belkacem"

    from conftest import login
    sh = login(client, "0770000001", "Student#123")
    mine = client.get("/planning/", headers=sh).json()
    assert len(mine) == 1 and mine[0]["id"] == body["id"]
    kinds = [n["kind"] for n in client.get("/notifications/", headers=sh).json()["items"]]
    assert "session_created" in kinds


def test_end_before_start_rejected(client, world, amine_h):
    s = setup_creneau_student(client, amine_h, "Candidat A", "0770000002")
    r = client.post("/planning/", headers=amine_h, json=payload([s["id"]], world["v1"].id, start="11:00:00", end="10:00:00"))
    assert r.status_code == 422


def test_maintenance_vehicle_rejected(client, world, amine_h):
    s = setup_creneau_student(client, amine_h, "Candidat B", "0770000003")
    r = client.post("/planning/", headers=amine_h, json=payload([s["id"]], world["v3"].id))
    assert r.status_code == 400 and "maintenance" in r.json()["detail"]


def test_unknown_student_admin_as_student_and_other_gender_rejected(client, world, amine_h, wassila_h):
    girl = setup_creneau_student(client, wassila_h, "Fille Test", "0770000004", "f")
    s = setup_creneau_student(client, amine_h, "Garcon Test", "0770000005")
    assert client.post("/planning/", headers=amine_h, json=payload([99999], world["v1"].id)).status_code == 400
    assert client.post("/planning/", headers=amine_h, json=payload([world["amine"].id], world["v1"].id)).status_code == 400
    assert client.post("/planning/", headers=amine_h, json=payload([girl["id"]], world["v1"].id)).status_code == 400
    assert client.post("/planning/", headers=amine_h, json=payload([s["id"]], 99999)).status_code == 400


def test_student_must_be_in_session_phase(client, world, amine_h):
    s = create_student(client, amine_h, "Encore Code", "0770000006", "m")  # phase code
    r = client.post("/planning/", headers=amine_h, json=payload([s["id"]], world["v1"].id))
    assert r.status_code == 400


def test_conflicts_vehicle_student_instructor(client, world, amine_h, wassila_h):
    a = setup_creneau_student(client, amine_h, "Garcon Un", "0770000007")
    b = setup_creneau_student(client, amine_h, "Garcon Deux", "0770000008")
    g = setup_creneau_student(client, wassila_h, "Fille Une", "0770000009", "f")
    assert client.post("/planning/", headers=amine_h, json=payload([a["id"]], world["v1"].id)).status_code == 201
    # même véhicule, même horaire (autre moniteur) => refus
    assert client.post("/planning/", headers=wassila_h, json=payload([g["id"]], world["v1"].id)).status_code == 409
    # même moniteur, même horaire => refus
    assert client.post("/planning/", headers=amine_h, json=payload([b["id"]], world["v2"].id)).status_code == 409
    # chevauchement partiel
    assert client.post("/planning/", headers=wassila_h, json=payload([g["id"]], world["v1"].id, start="09:15:00", end="09:45:00")).status_code == 409
    # autre véhicule + autre moniteur => OK
    assert client.post("/planning/", headers=wassila_h, json=payload([g["id"]], world["v2"].id)).status_code == 201
    # créneau contigu => OK
    assert client.post("/planning/", headers=amine_h, json=payload([b["id"]], world["v1"].id, start="09:30:00", end="10:00:00")).status_code == 201


def test_group_code_session_rules(client, world, amine_h):
    ids = [create_student(client, amine_h, f"Candidat Code {i}", f"07700001{i:02d}", "m")["id"] for i in range(3)]
    ok = client.post("/planning/", headers=amine_h, json=payload(ids, None, phase="code", start="08:00:00", end="09:00:00", group_label="Groupe A"))
    assert ok.status_code == 201 and len(ok.json()["attendances"]) == 3
    # un véhicule sur une séance de code => refus
    assert client.post("/planning/", headers=amine_h, json=payload(ids[:1], world["v1"].id, phase="code", start="10:00:00", end="11:00:00")).status_code == 400


def test_completion_is_idempotent_and_counts_only_present(client, world, amine_h):
    a = setup_creneau_student(client, amine_h, "Present Test", "0770000201")
    sess = client.post("/planning/", headers=amine_h, json=payload([a["id"]], world["v1"].id, date=iso(-1))).json()
    r1 = client.post(f"/planning/{sess['id']}/complete", headers=amine_h, json={"attendances": [{"student_id": a["id"], "attended": True}]})
    assert r1.status_code == 200
    # 2e et 3e clic : refus, les heures ne bougent plus
    assert client.post(f"/planning/{sess['id']}/complete", headers=amine_h, json={}).status_code == 409
    assert client.post(f"/planning/{sess['id']}/complete", headers=amine_h, json={}).status_code == 409
    p = client.get(f"/users/{a['id']}/progress", headers=amine_h).json()
    assert p["hours_creneau"] == 0.5


def test_absent_student_gets_no_hours_and_reopen_reverts(client, world, amine_h):
    a = setup_creneau_student(client, amine_h, "Absent Test", "0770000202")
    b = setup_creneau_student(client, amine_h, "Present Test2", "0770000203")
    s1 = client.post("/planning/", headers=amine_h, json=payload([a["id"]], world["v1"].id, date=iso(-1))).json()
    s2 = client.post("/planning/", headers=amine_h, json=payload([b["id"]], world["v1"].id, date=iso(-1), start="10:00:00", end="10:30:00")).json()
    client.post(f"/planning/{s1['id']}/complete", headers=amine_h, json={"attendances": [{"student_id": a["id"], "attended": False}]})
    client.post(f"/planning/{s2['id']}/complete", headers=amine_h, json={})
    assert client.get(f"/users/{a['id']}/progress", headers=amine_h).json()["hours_creneau"] == 0
    assert client.get(f"/users/{b['id']}/progress", headers=amine_h).json()["hours_creneau"] == 0.5
    assert client.post(f"/planning/{s2['id']}/reopen", headers=amine_h).status_code == 200
    assert client.get(f"/users/{b['id']}/progress", headers=amine_h).json()["hours_creneau"] == 0
    # on peut alors terminer à nouveau, une seule fois
    assert client.post(f"/planning/{s2['id']}/complete", headers=amine_h, json={}).status_code == 200
    assert client.get(f"/users/{b['id']}/progress", headers=amine_h).json()["hours_creneau"] == 0.5


def test_cannot_complete_future_session(client, world, amine_h):
    a = setup_creneau_student(client, amine_h, "Futur Test", "0770000204")
    s = client.post("/planning/", headers=amine_h, json=payload([a["id"]], world["v1"].id, date=iso(3))).json()
    assert client.post(f"/planning/{s['id']}/complete", headers=amine_h, json={}).status_code == 400


def test_update_cancel_delete_and_ownership(client, world, amine_h, wassila_h):
    a = setup_creneau_student(client, amine_h, "Edit Test", "0770000205")
    s = client.post("/planning/", headers=amine_h, json=payload([a["id"]], world["v1"].id, date=iso(2))).json()
    # modifier l'horaire
    r = client.put(f"/planning/{s['id']}", headers=amine_h, json={"start_time": "14:00:00", "end_time": "14:30:00"})
    assert r.status_code == 200 and r.json()["start_time"] == "14:00:00"
    # un autre moniteur ne peut pas y toucher
    assert client.put(f"/planning/{s['id']}", headers=wassila_h, json={"start_time": "15:00:00", "end_time": "15:30:00"}).status_code == 404
    assert client.delete(f"/planning/{s['id']}", headers=wassila_h).status_code == 404
    assert client.post(f"/planning/{s['id']}/cancel", headers=amine_h).status_code == 200
    assert client.delete(f"/planning/{s['id']}", headers=amine_h).status_code == 204
    assert client.get("/planning/", headers=amine_h).json() == []


def test_completed_session_cannot_be_deleted(client, world, amine_h):
    a = setup_creneau_student(client, amine_h, "Del Test", "0770000206")
    s = client.post("/planning/", headers=amine_h, json=payload([a["id"]], world["v1"].id, date=iso(-1))).json()
    client.post(f"/planning/{s['id']}/complete", headers=amine_h, json={})
    assert client.delete(f"/planning/{s['id']}", headers=amine_h).status_code == 400


def test_extra_hours_are_billed(client, world, amine_h):
    a = setup_creneau_student(client, amine_h, "Extra Test", "0770000207")
    # 9 heures en Créneau => 1 h supplémentaire
    for i in range(9):
        s = client.post("/planning/", headers=amine_h, json=payload([a["id"]], world["v1"].id, date=iso(-5 - i), start="09:00:00", end="10:00:00")).json()
        assert client.post(f"/planning/{s['id']}/complete", headers=amine_h, json={}).status_code == 200
    p = client.get(f"/users/{a['id']}/progress", headers=amine_h).json()
    assert p["hours_creneau"] == 9 and p["extra_hours"] == 1
    assert p["total_due"] == 20000 + 1500 and p["remaining"] == 21500


def test_invalid_status_no_longer_possible_and_no_500(client, world, amine_h):
    a = setup_creneau_student(client, amine_h, "Status Test", "0770000208")
    s = client.post("/planning/", headers=amine_h, json=payload([a["id"]], world["v1"].id)).json()
    r = client.put(f"/planning/{s['id']}", headers=amine_h, json={"status": "nimportequoi"})
    assert r.status_code == 200  # champ inconnu ignoré, jamais de 500
