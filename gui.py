import sqlite3
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from app.db import (
    init_db, list_clients, new_client,
    next_invoice_number, insert_invoice, insert_item, fetch_invoice_full,
    mark_invoice_used,
)
from app.utils import to_money
from app.settings import IVA_RATE, IRPF_RATE
from app.invoices import _parse_invoice_date_str   # reuse the same parser
from app import pdf

DB_PATH = "invoice_app.db"

class InvoiceGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Invoice App — GUI (simple)")
        self.geometry("800x600")
        self.conn = sqlite3.connect(DB_PATH)
        init_db(self.conn)
        self._build_ui()

    def _build_ui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill=tk.BOTH, expand=True)

        self.clients_frame = ttk.Frame(nb)
        self.invoice_frame = ttk.Frame(nb)

        nb.add(self.clients_frame, text="Clients")
        nb.add(self.invoice_frame, text="New Invoice")

        self._build_clients_tab()
        self._build_invoice_tab()

    # -------- Clients Tab --------
    def _build_clients_tab(self):
        # Left: list of clients
        left = ttk.Frame(self.clients_frame)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.clients_list = tk.Listbox(left, height=20)
        self.clients_list.pack(fill=tk.BOTH, expand=True)
        self._refresh_clients_list()

        # Right: form to add client
        right = ttk.Frame(self.clients_frame)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        ttk.Label(right, text="Add Client", font=("Arial", 12, "bold")).pack(pady=(0,10))

        self.ent_name = ttk.Entry(right, width=30)
        self.ent_nif = ttk.Entry(right, width=30)
        self.ent_addr = ttk.Entry(right, width=30)
        self.ent_email = ttk.Entry(right, width=30)
        self.ent_phone = ttk.Entry(right, width=30)

        for lbl, widget in [
            ("Name", self.ent_name),
            ("NIF/NIE/CIF", self.ent_nif),
            ("Address", self.ent_addr),
            ("Email", self.ent_email),
            ("Phone", self.ent_phone),
        ]:
            ttk.Label(right, text=lbl).pack(anchor="w")
            widget.pack(fill=tk.X, pady=2)

        ttk.Button(right, text="Add Client", command=self._add_client).pack(pady=10)

    def _refresh_clients_list(self):
        self.clients_list.delete(0, tk.END)
        self._clients_cache = list_clients(self.conn)
        for cid, name, nif, addr, email, phone in self._clients_cache:
            self.clients_list.insert(tk.END, f"[{cid}] {name} — {nif}")

    def _add_client(self):
        client = {
            "name": self.ent_name.get().strip(),
            "nif": self.ent_nif.get().strip(),
            "address": self.ent_addr.get().strip(),
            "email": self.ent_email.get().strip(),
            "phone": self.ent_phone.get().strip(),
        }
        if not client["name"]:
            messagebox.showerror("Error", "Name is required")
            return
        try:
            new_client(self.conn, client)
            self._refresh_clients_list()
            messagebox.showinfo("OK", "Client added")
            for e in (self.ent_name, self.ent_nif, self.ent_addr, self.ent_email, self.ent_phone):
                e.delete(0, tk.END)
            # Also update invoice tab dropdown
            self._refresh_invoice_clients()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # -------- Invoice Tab --------
    def _build_invoice_tab(self):
        top = ttk.Frame(self.invoice_frame)
        top.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(top, text="Client:").pack(side=tk.LEFT)
        self.client_var = tk.StringVar()
        self.client_dropdown = ttk.Combobox(top, textvariable=self.client_var, state="readonly", width=50)
        self.client_dropdown.pack(side=tk.LEFT, padx=10)
        self._refresh_invoice_clients()

        self.items_frame = ttk.Frame(self.invoice_frame)
        self.items_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        header = ttk.Frame(self.items_frame)
        header.pack(fill=tk.X)
        for i, txt in enumerate(["Description", "Qty", "Unit Price", "Line Total"]):
            ttk.Label(header, text=txt, font=("Arial", 10, "bold")).grid(row=0, column=i, padx=5, pady=5, sticky="w")

        self.item_rows = []
        self._add_item_row()  # start with one row

        btn_row = ttk.Frame(self.invoice_frame)
        btn_row.pack(fill=tk.X, padx=10, pady=(0,10))
        ttk.Button(btn_row, text="+ Add Item", command=self._add_item_row).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Compute Totals", command=self._compute_totals).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_row, text="Save Invoice", command=self._save_invoice).pack(side=tk.LEFT, padx=10)

        self.totals_var = tk.StringVar(value="Base: 0,00  IVA: 0,00  IRPF: 0,00  TOTAL: 0,00")
        ttk.Label(self.invoice_frame, textvariable=self.totals_var, font=("Arial", 11, "bold")).pack(anchor="w", padx=10)

        self.status_var = tk.StringVar(value="")
        ttk.Label(self.invoice_frame, textvariable=self.status_var, foreground="gray").pack(anchor="w", padx=10, pady=(0,10))

    def _refresh_invoice_clients(self):
        rows = list_clients(self.conn)
        options = [f"{cid} | {name}" for cid, name, *_ in rows]
        self.client_dropdown["values"] = options
        if options and not self.client_var.get():
            self.client_var.set(options[0])

    def _add_item_row(self):
        row = ttk.Frame(self.items_frame)
        r_index = len(self.item_rows) + 1
        row.pack(fill=tk.X, pady=2)

        ent_desc = ttk.Entry(row, width=50)
        ent_qty = ttk.Entry(row, width=8)
        ent_price = ttk.Entry(row, width=12)
        ent_total = ttk.Entry(row, width=14, state="readonly")

        ent_desc.grid(row=r_index, column=0, padx=5)
        ent_qty.grid(row=r_index, column=1, padx=5)
        ent_price.grid(row=r_index, column=2, padx=5)
        ent_total.grid(row=r_index, column=3, padx=5)

        # update line total when qty/price change (on focus out)
        def update_line_total(*_):
            try:
                q = float(ent_qty.get().strip().replace(",", "."))
                p = float(ent_price.get().strip().replace(",", "."))
                lt = q * p
                ent_total.config(state="normal")
                ent_total.delete(0, tk.END)
                ent_total.insert(0, to_money(lt))
                ent_total.config(state="readonly")
            except ValueError:
                ent_total.config(state="normal")
                ent_total.delete(0, tk.END)
                ent_total.config(state="readonly")

        ent_qty.bind("<FocusOut>", update_line_total)
        ent_price.bind("<FocusOut>", update_line_total)

        self.item_rows.append((ent_desc, ent_qty, ent_price, ent_total))

    def _collect_items(self):
        items = []
        for ent_desc, ent_qty, ent_price, _ in self.item_rows:
            desc = ent_desc.get().strip()
            if not desc:
                continue
            try:
                qty = float(ent_qty.get().strip().replace(",", "."))
                price = float(ent_price.get().strip().replace(",", "."))
            except ValueError:
                raise ValueError("Invalid number in items (qty/price).")
            items.append((desc, qty, price, qty * price))
        if not items:
            raise ValueError("No valid items entered.")
        return items

    def _compute_totals(self):
        try:
            items = self._collect_items()
        except Exception as e:
            messagebox.showerror("Error", str(e)); return
        base = round(sum(l[3] for l in items), 2)
        iva = round(base * IVA_RATE, 2)
        irpf = round(base * IRPF_RATE, 2)
        total = round(base + iva - irpf, 2)
        self.totals_var.set(f"Base: {to_money(base)}  IVA: {to_money(iva)}  IRPF: {to_money(irpf)}  TOTAL: {to_money(total)}")

    def _save_invoice(self):
        try:
            items = self._collect_items()
        except Exception as e:
            messagebox.showerror("Error", str(e)); return

        # client selection
        sel = self.client_var.get()
        if "|" not in sel:
            messagebox.showerror("Error", "Select a client.")
            return
        client_id = int(sel.split("|",1)[0].strip())

        # --- Ask for invoice date (default = today) ---
        default_hint = datetime.now().strftime("%Y-%m-%d")
        date_input = simpledialog.askstring(
            "Data d’emissió",
            f"Exemples: 23 09 25 · 23/09/2025 · 2025-09-23\n(Enter = avui: {default_hint})",
            parent=self
        )
        date_iso = _parse_invoice_date_str(date_input)

        # --- Compute number for that year ---
        number = next_invoice_number(self.conn, date_iso)

        base = round(sum(l[3] for l in items), 2)
        iva = round(base * IVA_RATE, 2)
        irpf = round(base * IRPF_RATE, 2)
        total = round(base + iva - irpf, 2)

        # insert invoice + items
        try:
            inv_id = insert_invoice(self.conn, number, date_iso, client_id, base, iva, irpf, total, notes="")
            # keep invoice_seq in sync (optional but recommended)
            try:
                mark_invoice_used(self.conn, number)
            except Exception:
                pass

            for desc, qty, price, line_total in items:
                insert_item(self.conn, inv_id, desc, qty, price)
            inv, it, cli = fetch_invoice_full(self.conn, inv_id)
            out_path = pdf.export_invoice(inv, it, cli)
            self.status_var.set(f"Saved invoice {number}. Exported: {out_path}")
            messagebox.showinfo("OK", f"Invoice {number} saved. Exported to: {out_path}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

def main():
    app = InvoiceGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
