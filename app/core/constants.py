"""Règles métier centralisées (une seule source de vérité)."""

PHASE_ORDER = ["code", "creneau", "circulation"]

# Heures requises pour valider chaque phase. Au-delà => heures supplémentaires facturées.
PHASE_HOURS_REQUIRED = {"code": 8.0, "creneau": 8.0, "circulation": 8.0}

# Durée standard proposée (en minutes) à la création d'une séance
DEFAULT_SESSION_MINUTES = {"code": 60, "creneau": 30, "circulation": 30}

MAX_SESSION_MINUTES = 180
MAX_GROUP_SIZE = 15  # séance de Code en groupe (10-15 candidats)

PHASE_LABELS = {"code": "Code de la Route", "creneau": "Créneau", "circulation": "Circulation"}
