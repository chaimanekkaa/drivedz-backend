from conftest import create_student, login, make_user
from app.models.user import GenderEnum, RoleEnum


def test_login_ok_and_wrong_password(client, world):
    assert client.post("/auth/login", data={"username": "0550000001", "password": "Secret#123"}).status_code == 200
    assert client.post("/auth/login", data={"username": "0550000001", "password": "nope"}).status_code == 401
    assert client.post("/auth/login", data={"username": "0999999999", "password": "x"}).status_code == 401


def test_login_accepts_spaces_and_international_format(client, world):
    assert client.post("/auth/login", data={"username": "0550 00 00 01", "password": "Secret#123"}).status_code == 200
    assert client.post("/auth/login", data={"username": "+213550000001", "password": "Secret#123"}).status_code == 200


def test_instructor_cannot_create_admin_or_instructor(client, world, wassila_h):
    for role in ("admin", "instructor"):
        r = client.post("/users/", headers=wassila_h, json={"full_name": "Pirate Test", "phone": "0770000009", "password": "Secret#123", "role": role, "gender": "f"})
        assert r.status_code == 403, (role, r.text)


def test_admin_can_create_instructor_but_not_admin(client, world, amine_h):
    r = client.post("/users/", headers=amine_h, json={"full_name": "Nouvelle Monitrice", "phone": "0660000010", "password": "Secret#123", "role": "instructor", "gender": "f"})
    assert r.status_code == 201
    r = client.post("/users/", headers=amine_h, json={"full_name": "Autre Admin", "phone": "0550000011", "password": "Secret#123", "role": "admin", "gender": "m"})
    assert r.status_code == 403


def test_create_user_requires_authentication(client, world):
    r = client.post("/users/", json={"full_name": "Anonyme Test", "phone": "0770000009", "password": "Secret#123", "role": "student", "gender": "m"})
    assert r.status_code == 401


def test_student_gender_must_match_creator(client, world, amine_h, wassila_h):
    r = client.post("/users/", headers=amine_h, json={"full_name": "Fille Test", "phone": "0770000001", "password": "Secret#123", "role": "student", "gender": "f"})
    assert r.status_code == 400
    create_student(client, amine_h, "Garcon Test", "0770000002", "m")


def test_phone_validation_and_duplicate(client, world, amine_h):
    bad = client.post("/users/", headers=amine_h, json={"full_name": "Numero Faux", "phone": "12345", "password": "Secret#123", "role": "student", "gender": "m"})
    assert bad.status_code == 422
    create_student(client, amine_h, "Premier Test", "0770 00 00 03", "m")
    dup = client.post("/users/", headers=amine_h, json={"full_name": "Doublon Test", "phone": "+213770000003", "password": "Secret#123", "role": "student", "gender": "m"})
    assert dup.status_code == 409


def test_password_too_long_is_rejected_not_500(client, world, amine_h):
    r = client.post("/users/", headers=amine_h, json={"full_name": "Long Mdp", "phone": "0770000004", "password": "x" * 100, "role": "student", "gender": "m"})
    assert r.status_code == 422


def test_gender_scope_on_students_and_progress_and_phase(client, world, amine_h, wassila_h):
    boy = create_student(client, amine_h, "Yacine Garcon", "0770000005", "m")
    girl = create_student(client, wassila_h, "Meriem Fille", "0770000006", "f")

    assert [s["id"] for s in client.get("/users/students", headers=amine_h).json()] == [boy["id"]]
    assert [s["id"] for s in client.get("/users/students", headers=wassila_h).json()] == [girl["id"]]

    # Wassila ne peut ni voir, ni modifier, ni valider, ni réinitialiser un candidat homme
    assert client.get(f"/users/{boy['id']}/progress", headers=wassila_h).status_code == 404
    assert client.put(f"/users/{boy['id']}/phase", headers=wassila_h, json={"phase": "circulation"}).status_code == 404
    assert client.post(f"/users/{boy['id']}/validate-phase", headers=wassila_h).status_code == 404
    assert client.post(f"/users/{boy['id']}/reset-password", headers=wassila_h, json={"new_password": "Nouveau#1"}).status_code == 404


def test_student_cannot_see_other_students(client, world, amine_h):
    a = create_student(client, amine_h, "Candidat Un", "0770000007", "m")
    b = create_student(client, amine_h, "Candidat Deux", "0770000008", "m")
    h = login(client, "0770000007", "Student#123")
    assert client.get(f"/users/{a['id']}/progress", headers=h).status_code == 200
    assert client.get(f"/users/{b['id']}/progress", headers=h).status_code == 403
    assert client.get("/users/students", headers=h).status_code == 403
    assert client.get(f"/payments/{b['id']}", headers=h).status_code == 403


def test_search_query(client, world, amine_h):
    create_student(client, amine_h, "Karim Benali", "0770000012", "m")
    create_student(client, amine_h, "Sofiane Kaci", "0770000013", "m")
    r = client.get("/users/students", headers=amine_h, params={"q": "kari"})
    assert [s["full_name"] for s in r.json()] == ["Karim Benali"]
    assert len(client.get("/users/students", headers=amine_h, params={"q": "0770000013"}).json()) == 1


def test_impersonation_flow(client, world, amine_h, wassila_h):
    girl = create_student(client, wassila_h, "Fille Imp", "0770000014", "f")
    # le moniteur ne peut pas usurper
    assert client.post(f"/auth/impersonate/{world['amine'].id}", headers=wassila_h).status_code == 403
    r = client.post(f"/auth/impersonate/{world['wassila'].id}", headers=amine_h)
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert client.get("/auth/me", headers=h).json()["full_name"] == "Wassila Cherif"
    assert [s["id"] for s in client.get("/users/students", headers=h).json()] == [girl["id"]]
    back = client.post("/auth/stop-impersonate", headers=h)
    assert back.status_code == 200 and back.json()["role"] == "admin"
    # on ne peut pas "arrêter" sans être en mode usurpation
    assert client.post("/auth/stop-impersonate", headers=amine_h).status_code == 400


def test_change_password(client, world, amine_h):
    assert client.post("/auth/change-password", headers=amine_h, json={"old_password": "faux", "new_password": "Nouveau#123"}).status_code == 400
    assert client.post("/auth/change-password", headers=amine_h, json={"old_password": "Secret#123", "new_password": "Nouveau#123"}).status_code == 200
    assert client.post("/auth/login", data={"username": "0550000001", "password": "Nouveau#123"}).status_code == 200
