# DriveDZ Backend v3 — Installation

Ce dossier **remplace entièrement** votre ancien `app/`, `alembic/`, `requirements.txt`.
C'est une refonte complète, pas un patch — ne mélangez pas avec les anciens fichiers.

## 1) Copier les fichiers
Supprimez l'ancien `app/` et `alembic/` de votre projet `AUTO_ECOLE`, puis copiez-y
le contenu de ce dossier (`app/`, `alembic/`, `alembic.ini`, `requirements.txt`, `.env.example`,
`seed.py`/`reset_db.py` sont déjà dans `app/`).

## 2) Dépendances
```powershell
pip install -r requirements.txt
# pour lancer les tests (optionnel) :
pip install -r requirements-dev.txt
```

## 3) Configuration
```powershell
copy .env.example .env
```
Éditez `.env` : mot de passe PostgreSQL réel, et générez une vraie `SECRET_KEY` :
```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 4) Base de données — repartir propre
Votre ancienne base a un historique de migrations cassé (`da264d0b24be` supprimait
5 tables en silence). On ne le répare pas : on repart sur une base saine.

**Option A — tout effacer et repartir avec des données de démo :**
```powershell
python -m app.reset_db --demo --yes
```
Comptes créés : Admin `0550000001` / `Admin#123`, Moniteur `0660000002` / `Wassila#123`,
6 candidats `0770000001` à `0770000006` / `Student#123`.
**Changez ces mots de passe avant toute mise en production.**

**Option B — tout effacer et créer juste votre vrai compte admin (interactif) :**
```powershell
python -m app.reset_db --yes
```

Après la première installation, les migrations suivantes utiliseront `alembic upgrade head`
normalement — plus besoin de `reset_db`.

## 5) Lancer
```powershell
uvicorn app.main:app --reload
```

## 6) Tests (optionnel mais recommandé)
```powershell
pip install -r requirements-dev.txt
pytest -q
```
41 tests couvrent : sécurité/rôles, séparation hommes/femmes, conflits de planning,
idempotence des séances, examens, paiements, notifications.
