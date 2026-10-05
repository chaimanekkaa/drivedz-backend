"""ATTENTION : efface TOUTE la base, la recrée avec Alembic, puis (option) injecte les données de démo.

    python -m app.reset_db --demo
"""
import argparse

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app import models  # noqa: F401
from app.database import Base, engine


def wipe():
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        else:
            Base.metadata.drop_all(conn)
            conn.execute(text("DROP TABLE IF EXISTS alembic_version"))


def main(demo: bool, yes: bool):
    if not yes:
        if input("Cela va EFFACER toutes les données. Tapez « oui » pour continuer : ").strip().lower() != "oui":
            print("Annulé.")
            return
    wipe()
    command.upgrade(Config("alembic.ini"), "head")
    from app.seed import main as seed_main
    seed_main(demo=demo)
    print("Base réinitialisée.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="ajoute des données de démonstration")
    ap.add_argument("--yes", action="store_true", help="ne pas demander de confirmation")
    a = ap.parse_args()
    main(a.demo, a.yes)
