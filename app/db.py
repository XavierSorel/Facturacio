from app.clients import validate_client

def init_db(conn):
    def init_db(conn):
        cursor = conn.cursor()
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            nif      TEXT,
            address  TEXT
        );

        CREATE TABLE IF NOT EXISTS invoices (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            number     TEXT NOT NULL UNIQUE,
            client_id  INTEGER NOT NULL,
            issue_date TEXT NOT NULL,
            base       REAL NOT NULL DEFAULT 0,
            iva        REAL NOT NULL DEFAULT 0,
            irpf       REAL NOT NULL DEFAULT 0,
            total      REAL NOT NULL DEFAULT 0,
            notes      TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        );

        CREATE INDEX IF NOT EXISTS idx_invoices_client ON invoices(client_id);
        CREATE INDEX IF NOT EXISTS idx_invoices_date   ON invoices(issue_date);

        CREATE TABLE IF NOT EXISTS invoice_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id  INTEGER NOT NULL,
            description TEXT NOT NULL,
            qty         REAL NOT NULL,
            unit_price  REAL NOT NULL,
            line_total  REAL GENERATED ALWAYS AS (qty * unit_price) VIRTUAL,
            FOREIGN KEY (invoice_id) REFERENCES invoices(id)
        );

        CREATE INDEX IF NOT EXISTS idx_items_invoice ON invoice_items(invoice_id);
        """)
        conn.commit()


def new_client(conn, client: dict):
    errors = validate_client(client)
    if errors:
        raise ValueError(f"Invalid client data: {errors}")


    cursor = conn.cursor()
    # Insert data
    cursor.execute("""
            INSERT INTO clients (name, nif, address)
            VALUES (:name, :nif, :address)
        """, client)

    # Commit changes
    conn.commit()
