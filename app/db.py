
import sqlite3
from datetime import datetime
from typing import Optional, List, Tuple, Dict

DB_NAME = "invoice_app.db"

SCHEMA = [
    """CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        nif TEXT,
        address TEXT,
        email TEXT,
        phone TEXT
    );""",

    """CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number TEXT UNIQUE NOT NULL,
        date TEXT NOT NULL,
        client_id INTEGER NOT NULL,
        base REAL NOT NULL,
        iva REAL NOT NULL,
        irpf REAL NOT NULL,
        total REAL NOT NULL,
        notes TEXT,
        FOREIGN KEY(client_id) REFERENCES clients(id)
    );""",

    """CREATE TABLE IF NOT EXISTS invoice_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER NOT NULL,
        description TEXT NOT NULL,
        qty REAL NOT NULL,
        unit_price REAL NOT NULL,
        line_total REAL NOT NULL,
        FOREIGN KEY(invoice_id) REFERENCES invoices(id)
    );""",

    """CREATE TABLE IF NOT EXISTS invoice_seq (
        year INTEGER PRIMARY KEY,
        next_seq INTEGER NOT NULL
    );"""
]


def get_conn(db_path: Optional[str] = None) -> sqlite3.Connection:
    return sqlite3.connect(db_path or DB_NAME)

def init_db(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    for stmt in SCHEMA:
        cur.execute(stmt)
    conn.commit()

# --- Clients ---
def new_client(conn, client: Dict[str, str]) -> int:
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO clients (name, nif, address, email, phone)
               VALUES (:name, :nif, :address, :email, :phone)""", client
    )
    conn.commit()
    return cur.lastrowid

def get_client(conn, client_id: int):
    cur = conn.cursor()
    cur.execute("SELECT id, name, nif, address, email, phone FROM clients WHERE id = ?", (client_id,))
    return cur.fetchone()

def list_clients(conn) -> List[Tuple]:
    cur = conn.cursor()
    cur.execute("SELECT id, name, nif, address, email, phone FROM clients ORDER BY id DESC")
    return cur.fetchall()

# --- Invoice numbering ---
def _last_suffix_for_year(conn, year: str) -> int:
    cur = conn.cursor()
    cur.execute("SELECT number FROM invoices WHERE number LIKE ? ORDER BY id DESC LIMIT 1", (f"{year}-%",))
    row = cur.fetchone()
    if not row:
        return 0
    try:
        return int(row[0].split('-')[1])
    except Exception:
        return 0

def next_invoice_number(conn, date_str: str | None = None) -> str:
    """
    Returns the next invoice number 'YYYY-NNNN'.
    - If date_str is given (e.g. '2025-09-24'), use that year; else use today's year.
    - Sequence is max(DB max for year + 1, invoice_seq.next_seq).
    """
    from datetime import datetime

    # Determine year
    if date_str and len(str(date_str)) >= 4 and str(date_str)[:4].isdigit():
        year = int(str(date_str)[:4])
    else:
        year = int(datetime.today().strftime("%Y"))

    cur = conn.cursor()

    # Highest existing seq in invoices for that year
    cur.execute("""
        SELECT number FROM invoices
        WHERE number LIKE ?
        ORDER BY number DESC
        LIMIT 1
    """, (f"{year}-%",))
    row = cur.fetchone()
    db_next = 1
    if row:
        try:
            # parse 'YYYY-NNNN'
            db_next = int(row[0].split("-", 1)[1]) + 1
        except Exception:
            db_next = 1

    # Stored next_seq in invoice_seq (if any)
    cur.execute("SELECT next_seq FROM invoice_seq WHERE year = ?", (year,))
    row = cur.fetchone()
    stored_next = row[0] if row else 1

    seq = max(db_next, stored_next)
    return f"{year}-{seq:04d}"


# --- Invoices ---
def insert_invoice(conn, number: str, date: str, client_id: int, base: float, iva: float, irpf: float, total: float, notes: str) -> int:
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO invoices (number, date, client_id, base, iva, irpf, total, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (number, date, client_id, base, iva, irpf, total, notes)
    )
    conn.commit()
    return cur.lastrowid

def insert_item(conn, invoice_id: int, description: str, qty: float, unit_price: float) -> int:
    line_total = round(qty * unit_price, 2)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO invoice_items (invoice_id, description, qty, unit_price, line_total)
            VALUES (?, ?, ?, ?, ?)""", (invoice_id, description, qty, unit_price, line_total)
    )
    conn.commit()
    return cur.lastrowid

def fetch_invoice_full(conn, invoice_id: int):
    cur = conn.cursor()
    cur.execute("SELECT id, number, date, client_id, base, iva, irpf, total, notes FROM invoices WHERE id = ?", (invoice_id,))
    inv = cur.fetchone()
    cur.execute("SELECT description, qty, unit_price, line_total FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
    items = cur.fetchall()
    cur.execute("SELECT id, name, nif, address, email, phone FROM clients WHERE id = ?", (inv[3],))
    client = cur.fetchone()
    return inv, items, client

# ⬇️ Add these helpers (anywhere in db.py)
def _year_from_number(inv_number: str) -> int:
    # expects "YYYY-NNNN"
    return int(inv_number.split("-", 1)[0])

def _seq_from_number(inv_number: str) -> int:
    return int(inv_number.split("-", 1)[1])

def _compose_number(year: int, seq: int) -> str:
    return f"{year}-{seq:04d}"

def forward_invoice_number(conn, target_number: str) -> None:
    """
    Force the NEXT invoice number >= target_number for its year.
    Example: forward_invoice_number(conn, "2025-0031")
    """
    year = _year_from_number(target_number)
    target_seq = _seq_from_number(target_number)
    cur = conn.cursor()
    # Upsert the invoice_seq row for that year
    cur.execute("""
        INSERT INTO invoice_seq(year, next_seq) VALUES(?, ?)
        ON CONFLICT(year) DO UPDATE SET next_seq = MAX(next_seq, excluded.next_seq)
    """, (year, target_seq))
    conn.commit()

def mark_invoice_used(conn, inv_number: str) -> None:
    """
    After inserting an invoice row, call this to bump invoice_seq to seq+1.
    """
    year = _year_from_number(inv_number)
    seq = _seq_from_number(inv_number) + 1
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO invoice_seq(year, next_seq) VALUES(?, ?)
        ON CONFLICT(year) DO UPDATE SET next_seq = MAX(next_seq, excluded.next_seq)
    """, (year, seq))
    conn.commit()

