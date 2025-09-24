import sqlite3
from app import add_client, new_client, init_db, choose_client_id, create_invoice_interactive

def main():
    conn = sqlite3.connect("invoice_app.db")
    init_db(conn)
    while True:
        print("Select option")
        print("1 - New Invoice")
        print("2 - New Client")
        print("3 - Exit")
        option = input().strip()
        if option == "1":
            cid = choose_client_id(conn)
            if cid:
                create_invoice_interactive(conn, cid)
        elif option == "2":
            client = add_client()
            try:
                new_client(conn, client)
                print("Client added.")
            except Exception as e:
                print("Could not add client:", e)
        elif option == "3":
            break
        else:
            print("Unknown option. Try again.")

if __name__ == "__main__":
    main()
