import re
from app.db import connect, init_db, new_client
from app.invoices import create_invoice_header

def add_client():
    client = {
        "name": input("Enter client name: "),
        "nif": input("Enter client NIF: "),
        "address": input("Enter client address: "),
        "email": input("Enter client email: "),
        "phone": input("Enter client phone: "),
    }
    return client

NIF_REGEX = re.compile(r"^\d{8}[A-Za-z]$")

def validate_client(client: dict) -> list[str]:
    """
    Validate a client dict.
    Returns a list of error messages. Empty if valid.
    """
    errors = []

    # Name check
    if not client.get("name") or not client["name"].strip():
        errors.append("Name cannot be empty")

    # NIF check
    nif = client.get("nif", "").strip().upper()
    if not NIF_REGEX.match(nif):
        errors.append("NIF must be 8 digits followed by a letter (e.g. 12345678Z)")

    # Address check
    if not client.get("address") or not client["address"].strip():
        errors.append("Address cannot be empty")

    return errors

def choose_client_id(conn):
    client_id_input = input("Enter client id: ")

    # validate integer input
    try:
        client_id = int(client_id_input)
    except ValueError:
        return None

    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM clients WHERE id = ?", (client_id,))
    if cursor.fetchone() is not None:
        return client_id
    return None




