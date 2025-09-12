from app import new_client, add_client
from app.clients import choose_client_id


def year_from_date(issue_date_str: str) ->str:
    #expects YYYY-MM-DD
    return issue_date_str[:4]

def next_invoice_number(conn, issue_date: str) -> str:
    """
    Returns next number in format YYYY-XXX for the given issue_date's year.
    Must be called inside the same transaction as the insert to avoid races.
    """
    year = year_from_date(issue_date)
    cursor = conn.cursor()
    # numbers like "2025-001". Pull max suffix where number starts with "2025-"
    cursor.execute(
        """
        SELECT MAX(CAST(SUBSTR(number, 6) AS INTEGER)) AS max_seq
        FROM invoices
        WHERE number LIKE ?;
        """,
        (f"{year}-%",)
    )
    row = cursor.fetchone()
    next_seq = 1 if row["max_seq"] is None else row["max_seq"] + 1
    return f"{year}-{next_seq:03d}"

# invoices.py (cont.)
def create_invoice_header(conn, client_id: int, issue_date: str, notes: str = None) -> tuple[str, int]:
    """
    Creates an invoice row with a fresh number and zero totals (to be filled later).
    Returns (number, invoice_id).
    """
    with conn:  # BEGIN/COMMIT automatically; rolls back on exception
        number = next_invoice_number(conn, issue_date)
        cur = conn.execute(
            """
            INSERT INTO invoices (number, client_id, issue_date, base, iva, irpf, total, notes)
            VALUES (?, ?, ?, 0, 0, 0, 0, ?)
            """,
            (number, client_id, issue_date, notes)
        )
        invoice_id = cur.lastrowid
    return number, invoice_id

def flow_new_invoice(conn):
    while True:
        client_id = choose_client_id(conn)
        if client_id is not None:
            break  # valid client found
        choice = input("Invalid client. (C)reate new / (R)etry / (X) Cancel: ").lower()
        if choice == "c":
            # call your add_client() here
            client_id = new_client(conn, add_client())
            break
        elif choice == "x":
            client_id = None
            break

    #date: let user type or use today
    issue_date = input("Issue date [YYYY-MM-DD] (enter for today): ").strip()
    if not issue_date:
        from datetime import date
        issue_date = date.today().isoformat()

    number, invoice_id = create_invoice_header(conn, client_id, issue_date)
    print(f"Created invoice {number} (id={invoice_id}).")

    def print_total(total):
        irpf = total * 0.15
        iva = total * 0.21
        print(f"Total =  {total - iva + irpf} Iva = {iva} Irpf = {irpf}")

    def add_items_loop():
        items = []
        total = irpf = iva = 0
        while True:
            description = input("Enter description (or done if finished): ")
            if description.lower() == "done":
                break
            quantity = (int(input("Enter amount: " )))
            price = (float(input("Enter price per unit: ")))
            total += quantity * price
            print_total(total)
            items.append({"description" : description, "quantity" : quantity, "price" : price })
        return items

    # 4) compute totals and persist (C4)
    #compute_totals(conn, invoice_id)
    # 5) offer to export PDF (C5)