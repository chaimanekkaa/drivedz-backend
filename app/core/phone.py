import re

_MOBILE_RE = re.compile(r"^0[567]\d{8}$")


def clean_phone(raw: str) -> str:
    """Retire espaces, tirets, points, parenthèses et ramène +213 / 00213 / 213 au format local 0XXXXXXXXX."""
    p = re.sub(r"[\s\-\.\(\)]", "", raw or "")
    if p.startswith("+213"):
        p = "0" + p[4:]
    elif p.startswith("00213"):
        p = "0" + p[5:]
    elif p.startswith("213") and len(p) == 12:
        p = "0" + p[3:]
    return p


def normalize_phone(raw: str) -> str:
    """Normalise ET valide un numéro mobile algérien (05/06/07 + 8 chiffres)."""
    p = clean_phone(raw)
    if not _MOBILE_RE.match(p):
        raise ValueError("Numéro invalide : format attendu 05XX XX XX XX, 06XX... ou 07XX...")
    return p


def to_whatsapp_number(phone: str) -> str:
    """0550123456 -> 213550123456 (format wa.me)."""
    p = clean_phone(phone)
    return "213" + p[1:] if p.startswith("0") else p
