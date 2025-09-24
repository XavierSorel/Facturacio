import sqlite3
from app.db import init_db, forward_invoice_number

def main():
    # open your DB
    conn = sqlite3.connect("invoice_app.db")
    init_db(conn)  # makes sure all tables exist

    # ⚡ change this to the number you want to reach
    target_number = "2025-0023"

    forward_invoice_number(conn, target_number)
    print(f"Forwarded invoice sequence to at least {target_number}")

if __name__ == "__main__":
    main()
