
import re
from datetime import datetime
from .settings import DATE_FMT

NIF_RE = re.compile(r"^[A-Z0-9][A-Z0-9\d]{6,8}[A-Z0-9]$")

def validate_nif(nif: str) -> bool:
    if not nif:
        return False
    return bool(NIF_RE.match(nif.strip().upper()))

def today_str() -> str:
    return datetime.today().strftime(DATE_FMT)

def to_money(x: float) -> str:
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
