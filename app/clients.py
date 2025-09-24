
from .utils import validate_nif

def add_client():
    client = {
        "name": input("Client name: ").strip(),
        "nif": input("Client NIF/NIE/CIF: ").strip(),
        "address": input("Client address: ").strip(),
        "email": input("Client email: ").strip(),
        "phone": input("Client phone: ").strip(),
    }
    return client

def validate_client(client: dict) -> bool:
    if not client.get("name"):
        print("Name is required.")
        return False
    if client.get("nif") and not validate_nif(client["nif"]):
        print("Warning: NIF format looks invalid.")
    return True

def choose_client_id(conn):
    raw = input("Enter client id (or blank to cancel): ").strip()
    if not raw:
        return None
    try:
        cid = int(raw)
    except ValueError:
        print("Not a number.")
        return None
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM clients WHERE id = ?", (cid,))
    if cur.fetchone():
        return cid
    print("Client id not found.")
    return None
