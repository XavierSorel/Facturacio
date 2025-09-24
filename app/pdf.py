import os
import re
from datetime import datetime, date
from typing import List, Tuple

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
)

from .settings import COMPANY_NAME, COMPANY_NIF, COMPANY_ADDRESS, COMPANY_IBAN, OUTPUT_DIR
from .utils import to_money


# ---------- layout constants (exact widths) ----------
PAGE_SIZE = A4
LM = RM = TM = BM = 18 * mm
CONTENT_W = PAGE_SIZE[0] - (LM + RM)  # exact content width in points

# Start with desired widths in mm for first 3 columns, make the last one "exact remainder"
C0 = 100 * mm
C1 = 20 * mm
C2 = 27 * mm
C3 = CONTENT_W - (C0 + C1 + C2)  # exact remainder to avoid float drift
COL_WIDTHS = [C0, C1, C2, C3]    # used across the single combined table


# ---------- helpers ----------

def _ensure_outdir() -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return OUTPUT_DIR


def _pdf_path(number: str) -> str:
    out = _ensure_outdir()
    return os.path.join(out, f"invoice_{number}.pdf")


def format_date_eu(d) -> str:
    """Return date in 'DD MM YY'."""
    if isinstance(d, (datetime, date)):
        return d.strftime("%d %m %y")

    s = str(d).strip()
    fmts = [
        "%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y",
        "%d.%m.%Y", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"
    ]
    for f in fmts:
        try:
            dt = datetime.strptime(s[:19], f)
            return dt.strftime("%d %m %y")
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s[:19])
        return dt.strftime("%d %m %y")
    except Exception:
        return s


def _insert_space_between_glued_caps(text: str) -> str:
    """Turn 'Alella ParkBarcelona' -> 'Alella Park Barcelona' (accents too)."""
    return re.sub(r'([a-záéíóúüïçñ])([A-ZÁÉÍÓÚÜÏÇÑ])', r'\1 \2', text)


def split_address_lines(address: str) -> Tuple[str, str, str]:
    """
    Return up to THREE lines: (line1, line2, line3).
    Heuristics:
      1) Respect existing newlines.
      2) Split AFTER 'street + number' (handles glued postal code like '2008328').
      3) Line2 begins with postal code if present.
      4) Try to split line2 again into locality vs province/country.
    """
    if not address:
        return "", "", ""

    if "\n" in address:
        parts = [p.strip() for p in address.split("\n")]
        parts += ["", "", ""]
        return parts[0], parts[1], parts[2]

    s = _insert_space_between_glued_caps(re.sub(r"\s+", " ", address.strip()))

    # number glued to postal code: "... 2008328 ..."
    m = re.match(r"^(.*?\b)(\d{1,5})(\d{5})(\b.*)$", s)
    if m:
        left_prefix = m.group(1).strip().rstrip(",")
        number = m.group(2)
        postal = m.group(3)
        rest = m.group(4).strip()
        line1 = f"{left_prefix} {number}".strip()
        line2_raw = f"{postal} {rest}".strip()
    else:
        # street+number + rest (allows 20B, 20-22, 20/2)
        m = re.match(r"^(.*?\b\d+[A-Za-z\-\/]?)\b[ ,]*\s*(.+)$", s)
        if m:
            line1 = m.group(1).strip()
            line2_raw = m.group(2).strip()
        else:
            # split before 5-digit postal code
            m = re.match(r"^(.*?)(\b\d{5}\b.*)$", s)
            if m:
                line1 = m.group(1).strip().rstrip(",")
                line2_raw = m.group(2).strip()
            else:
                # fallback
                parts = s.split()
                if len(parts) > 3:
                    mid = max(2, min(len(parts) - 2, len(parts) // 2))
                    return " ".join(parts[:mid]), " ".join(parts[mid:]), ""
                return s, "", ""

    # split line2_raw into line2 + line3
    line2_raw = _insert_space_between_glued_caps(line2_raw)
    if "," in line2_raw:
        a, b = line2_raw.split(",", 1)
        return line1, a.strip(), b.strip()

    words = line2_raw.split()
    if len(words) >= 4 and re.match(r"^\d{5}$", words[0]):
        return line1, " ".join(words[:3]), " ".join(words[3:])
    if len(words) >= 3:
        return line1, " ".join(words[:2]), " ".join(words[2:])
    return line1, line2_raw, ""


# ---------- layout blocks ----------

def _header(styles, inv, client) -> List:
    elems = []

    # Title: only "Factura" (left-aligned and same padding as tables)
    styles["Title"].alignment = 0  # LEFT
    title = Paragraph("<b>Factura</b>", styles["Title"])
    title_row = Table([[title]], colWidths=[CONTENT_W], hAlign="LEFT")
    title_row.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f7f7f7")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#dddddd")),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elems.append(title_row)
    elems.append(Spacer(0, 3 * mm))

    # Info box: Data d'emissió + Núm. de factura
    date_txt = format_date_eu(inv[2])
    info_tbl = Table(
        [[Paragraph("<b>Data d’emissió</b>", styles["Normal"]), Paragraph(date_txt, styles["Right"])],
         [Paragraph("<b>Núm. de factura</b>", styles["Normal"]), Paragraph(str(inv[1]), styles["Right"])]],
        colWidths=[CONTENT_W - (64 * mm), 64 * mm],
        hAlign="LEFT"
    )
    info_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafafa")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e5e5")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.25, colors.HexColor("#e5e5e5")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
    ]))
    elems.append(info_tbl)
    elems.append(Spacer(0, 6 * mm))

    # Emissor + Client (same formatter)
    comp_l1, comp_l2, comp_l3 = split_address_lines(COMPANY_ADDRESS)
    issuer_parts = [
        "<b>Emissor</b>",
        f"{COMPANY_NAME} — {COMPANY_NIF}",
        comp_l1
    ]
    if comp_l2: issuer_parts.append(comp_l2)
    if comp_l3: issuer_parts.append(comp_l3)
    issuer_parts.append(f"IBAN: {COMPANY_IBAN}")
    issuer_html = "<br/>".join(issuer_parts)
    issuer = Paragraph(issuer_html, styles["Normal"])

    client_addr = client[3] or ""
    cli_l1, cli_l2, cli_l3 = split_address_lines(client_addr)
    client_parts = [
        "<b>Client</b>",
        f"{client[1]} — {client[2]}",
        cli_l1
    ]
    if cli_l2: client_parts.append(cli_l2)
    if cli_l3: client_parts.append(cli_l3)
    client_html = "<br/>".join(client_parts)
    client_block = Paragraph(client_html, styles["Normal"])

    parties = Table([[issuer, client_block]], colWidths=[CONTENT_W / 2.0, CONTENT_W / 2.0], hAlign="LEFT")
    parties.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbfbfb")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e5e5")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elems.append(parties)
    elems.append(Spacer(0, 6 * mm))

    return elems


def _items_and_totals_table(styles, items: List[Tuple[str, float, float, float]], inv) -> Table:
    """
    Build ONE table that contains:
      - Header row for items
      - Items rows
      - A divider row (line above)
      - Totals labels row (Base / IVA / IRPF / TOTAL)
      - Totals values row
    Using the same COL_WIDTHS so every vertical line matches perfectly.
    """
    base, iva, irpf, total = inv[4], inv[5], inv[6], inv[7]

    data = []

    # Header row
    data.append([
        Paragraph("<b>Concepte</b>", styles["TableHeader"]),
        Paragraph("<b>Quant.</b>", styles["TableHeader"]),
        Paragraph("<b>Preu</b>", styles["TableHeader"]),
        Paragraph("<b>Total</b>", styles["TableHeader"]),
    ])

    # Item rows
    for desc, qty, unit_price, line_total in items:
        data.append([
            Paragraph(str(desc).replace("\n", "<br/>"), styles["Wrap"]),
            Paragraph(f"{qty:.2f}", styles["Right"]),
            Paragraph(to_money(unit_price), styles["Right"]),
            Paragraph(to_money(line_total), styles["Right"]),
        ])

    # Totals labels row
    data.append([
        Paragraph("Base imposable", styles["MutedCenter"]),
        Paragraph("IVA (21%)", styles["MutedCenter"]),
        Paragraph("IRPF (15%)", styles["MutedCenter"]),
        Paragraph("<b>TOTAL</b>", styles["MutedCenter"]),
    ])

    # Totals values row
    data.append([
        Paragraph(to_money(base), styles["BigRight"]),
        Paragraph(to_money(iva), styles["BigRight"]),
        Paragraph(f"- {to_money(irpf)}", styles["BigRight"]),
        Paragraph(f"<b>{to_money(total)}</b>", styles["BigRight"]),
    ])

    tbl = Table(data, colWidths=COL_WIDTHS, repeatRows=1, hAlign="LEFT")

    n_rows = len(data)
    header_row = 0
    totals_labels_row = n_rows - 2
    totals_values_row = n_rows - 1

    tbl.setStyle(TableStyle([
        # Header background
        ("BACKGROUND", (0, header_row), (-1, header_row), colors.HexColor("#efefef")),

        # Grid for entire table
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cfcfcf")),

        # Divider above totals labels (a slightly thicker line to separate sections)
        ("LINEABOVE", (0, totals_labels_row), (-1, totals_labels_row), 0.5, colors.HexColor("#cfcfcf")),

        # Backgrounds for totals area
        ("BACKGROUND", (0, totals_labels_row), (-1, totals_labels_row), colors.HexColor("#f7f7f7")),
        ("BACKGROUND", (3, totals_values_row), (3, totals_values_row), colors.HexColor("#f0f0f0")),  # TOTAL cell

        # Alignment
        ("ALIGN", (1, header_row + 1), (-1, totals_labels_row - 1), "RIGHT"),  # numbers in item rows
        ("ALIGN", (0, totals_labels_row), (-1, totals_labels_row), "CENTER"),   # labels centered
        ("ALIGN", (0, totals_values_row), (-1, totals_values_row), "RIGHT"),    # values right

        # Paddings (match items)
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),

        # Slightly larger padding for totals values for emphasis
        ("TOPPADDING", (0, totals_values_row), (-1, totals_values_row), 6),
        ("BOTTOMPADDING", (0, totals_values_row), (-1, totals_values_row), 6),
    ]))

    return tbl


def _notes_block(styles, notes: str) -> List:
    if not notes:
        return []
    para = Paragraph(f"<b>Notes</b><br/>{notes}", styles["Wrap"])
    box = Table([[para]], colWidths=[CONTENT_W], hAlign="LEFT")
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fbfbfb")),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e5e5e5")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return [Spacer(0, 6 * mm), box]


# ---------- document build ----------

def export_invoice(inv, items, client) -> str:
    """
    inv: (id, number, date, client_id, base, iva, irpf, total, notes)
    items: list of (description, qty, unit_price, line_total)
    client: (id, name, nif, address, email, phone)
    """
    number = inv[1]
    out_path = _pdf_path(number)

    styles = getSampleStyleSheet()
    styles["Title"].fontSize = 18
    styles["Title"].spaceAfter = 0
    styles["Title"].alignment = 0  # LEFT
    styles.add(ParagraphStyle(name="Right", parent=styles["Normal"], alignment=2))
    styles.add(ParagraphStyle(name="TableHeader", parent=styles["Normal"], alignment=1))
    styles.add(ParagraphStyle(name="Wrap", parent=styles["Normal"], wordWrap="CJK"))
    styles.add(ParagraphStyle(name="MutedCenter", parent=styles["Normal"], fontSize=9, textColor=colors.HexColor("#666666"), alignment=1))
    styles.add(ParagraphStyle(name="BigRight", parent=styles["Normal"], fontSize=12, alignment=2))

    doc = SimpleDocTemplate(
        out_path,
        pagesize=PAGE_SIZE,
        leftMargin=LM, rightMargin=RM,
        topMargin=TM, bottomMargin=BM
    )

    story = []
    story += _header(styles, inv, client)
    story.append(_items_and_totals_table(styles, items, inv))  # <— single table for both
    story += _notes_block(styles, inv[8])

    doc.build(story)
    return out_path
