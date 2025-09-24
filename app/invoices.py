import re
from datetime import datetime, date

from .db import next_invoice_number, insert_invoice, insert_item, fetch_invoice_full, mark_invoice_used
from .settings import IVA_RATE, IRPF_RATE
from .utils import to_money
from . import pdf

def _input_items():
    items = []
    total = 0.0
    print("Add line items. Type 'done' as description to finish.")
    while True:
        desc = input("  Description: ").strip()
        if desc.lower() == "done":
            break
        try:
            qty = float(input("  Quantity: ").strip())
            price = float(input("  Unit price: ").strip())
        except ValueError:
            print("  Invalid number, try again.")
            continue
        line_total = qty * price
        items.append((desc, qty, price, line_total))
        total += line_total
        print(f"  Subtotal: {to_money(total)}")
    return items

# Accepts 'DD MM YY', 'DD/MM/YYYY', 'YYYY-MM-DD', etc.
# Returns ISO 'YYYY-MM-DD' (fallback: today)
def _parse_invoice_date_str(s: str | None) -> str:
    from datetime import datetime, date
    s = (s or "").strip()
    if not s:
        return date.today().isoformat()
    fmts = [
        "%d %m %y", "%d %m %Y",
        "%d/%m/%y", "%d/%m/%Y",
        "%Y-%m-%d", "%Y/%m/%d",
        "%d-%m-%Y", "%d.%m.%Y",
    ]
    for f in fmts:
        try:
            return datetime.strptime(s, f).date().isoformat()
        except ValueError:
            pass
    # last resort: today
    return date.today().isoformat()

def create_invoice_interactive(
    conn,
    client_id: int | None = None,
    notes: str = "",
    invoice_date: str | None = None,     # NEW (optional)
    override_number: str | None = None,  # NEW (optional)
) -> int:
    # 1) Pick/parse the invoice date
    if invoice_date is None:
        print("Data d'emissió (enter = avui). Formats: 'DD MM YY', 'DD/MM/YYYY', 'YYYY-MM-DD'")
        user_input = input("> ").strip()
        date_iso = _parse_invoice_date_str(user_input)
    else:
        date_iso = _parse_invoice_date_str(invoice_date)

    # 2) Pick/compute the invoice number
    if override_number:
        number = override_number
        if not re.match(r"^\d{4}-\d{4}$", number):
            print("⚠️ Número de factura esperat com 'YYYY-NNNN' (ex: 2025-0031). Continuo igualment…")
    else:
        # your existing signature expects (conn, date_iso)
        number = next_invoice_number(conn, date_iso)

    # 3) Client guard
    if client_id is None:
        print("No client selected. Use 'New Client' first or enter an existing id.")
        return -1

    # 4) Items and totals (same as your code)
    items = _input_items()
    base = round(sum(l[3] for l in items), 2)
    iva = round(base * IVA_RATE, 2)
    irpf = round(base * IRPF_RATE, 2)
    total = round(base + iva - irpf, 2)

    # 5) Insert invoice + items (same as your code)
    invoice_id = insert_invoice(conn, number, date_iso, client_id, base, iva, irpf, total, notes)
    mark_invoice_used(conn, number)  # keep invoice_seq in sync
    for desc, qty, price, line_total in items:
        insert_item(conn, invoice_id, desc, qty, price)

    print(f"Created invoice {number}: Base {to_money(base)} + IVA {to_money(iva)} - IRPF {to_money(irpf)} = Total {to_money(total)}")

    # 6) Export PDF (same as your code)
    try:
        inv, it, cli = fetch_invoice_full(conn, invoice_id)
        pdf.export_invoice(inv, it, cli)
        print("PDF exported in 'out/' directory.")
    except Exception as e:
        print("PDF export failed:", e)

    return invoice_id
