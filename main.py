import sqlite3
from app import add_client, new_client, init_db

def main():
    conn = sqlite3.connect("invoice_app.db")
    init_db(conn)
    while True:
        print("Select option")
        print("1 - New Invoice")
        print("2 - New Client")
        print("3 - Exit")
        option = input()
        if option == "1":
            print("Coming soon")
        elif option == "2":
            client = add_client()
            try:
                new_client(conn, client)
            except ValueError as e:
                print("Could not add client", e)
        else:
            break

if __name__ == "__main__":
    main()
