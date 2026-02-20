# generate_pdf.py
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from num2words import num2words
import os, sys

def generate_pdf(invoice_no, date_str, customer, items, total, save_path, use_letterhead=True,print_ntn=True):
    

    # ---------------- CONSTANTS ----------------
    width, height = A4
    FOOTER_SAFE_MARGIN = 35 * mm
    MIN_ROWS = 12
    MAX_ROWS_PER_PAGE = 28

    # ---------- WARRANTY (EXACT 4 LINES) ----------
    WARRANTY_LINES = [
        "I, Mehmood-Ul-Hassan, being a person resident in Pakistan, carrying on business at 19A Extension Block, Iteffaq Town",
        "Multan Road, Lahore under the name of M/s Ramay Electromedics do hereby give this warranty that the IOLs described",
        "above as sold by me do not contravene the provisions of Section 23 of Drug Act, 1976",
       
    ]

    # ---------------- PATH ----------------
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    letterhead_path = os.path.join(base_path, "letterhead.png")
    c = canvas.Canvas(save_path, pagesize=A4)

    # ---------------- HELPERS ----------------
    def draw_letterhead():
        if use_letterhead and os.path.exists(letterhead_path):
            try:
                c.drawImage(letterhead_path, 0, 0, width=width, height=height, mask="auto")
            except:
                pass

    # ---------------- HEADER ----------------
    draw_letterhead()

    header_bottom_y = height - 42 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, header_bottom_y - 5 * mm, "INVOICE")

    meta_x = width - 20 * mm
    current_y = header_bottom_y - 12 * mm
    line_height = 6 * mm

    c.setFont("Helvetica-Bold", 11)
    if print_ntn:
        c.drawRightString(meta_x, current_y, "NTN No # 1845815-7")
        current_y -= line_height
    c.drawRightString(meta_x, current_y, f"Invoice No: {invoice_no}")
    current_y -= line_height
    c.drawRightString(meta_x, current_y, f"Date: {date_str}")

    # ---------------- BILL TO ----------------
    bill_to_x = 20 * mm
    bill_to_y = header_bottom_y - 10 * mm - line_height

    c.setFont("Helvetica-Bold", 12)
    c.drawString(bill_to_x, bill_to_y, "Bill To:")

    c.setFont("Helvetica", 12)
    name_x = bill_to_x + 16 * mm
    c.drawString(name_x, bill_to_y, customer.get("name", ""))

    c.setFont("Helvetica", 10)
    address_lines = customer.get("address", "").split("\n") if customer.get("address") else []
    for i, line in enumerate(address_lines):
        c.drawString(name_x, bill_to_y - 6 * mm - (5 * mm * i), line)

    # ---------------- TABLE ----------------
    col_widths = [15*mm, 70*mm, 25*mm, 20*mm, 25*mm, 30*mm]
    total_width = sum(col_widths)
    table_x = (width - total_width) / 2
    table_top_y = bill_to_y - (len(address_lines) * 5 * mm) - 22 * mm

    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2A2F8D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 1), (-1, -2), 0.35, colors.lightgrey),
        ("BACKGROUND", (0, -1), (-1, -1), colors.whitesmoke),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
    ])

    rows = []
    for idx, it in enumerate(items, start=1):
        rows.append([
            str(idx),
            it["description"],
            it["power"] or "",
            str(it["qty"]),
            f"{it['price']:.2f}",
            f"{it['amount']:.2f}",
        ])

    pages = [rows[i:i + MAX_ROWS_PER_PAGE] for i in range(0, len(rows), MAX_ROWS_PER_PAGE)]

    # ---------------- PAGE LOOP ----------------
    for page_index, page_rows in enumerate(pages):

        if page_index > 0:
            c.showPage()
            draw_letterhead()

        table_data = [["#", "DESCRIPTION", "POWER", "QTY", "RATE", "AMOUNT"]]
        table_data.extend(page_rows)

        if page_index == 0:
            while len(table_data) - 1 < MIN_ROWS:
                table_data.append(["", "", "", "", "", ""])

        if page_index == len(pages) - 1:
            table_data.append(["", "", "", "", "TOTAL", f"{total:.2f}"])

        tbl = Table(table_data, colWidths=col_widths, repeatRows=1)
        tbl.setStyle(style)

        w, h = tbl.wrapOn(c, width, height)
        tbl.drawOn(c, table_x, table_top_y - h)
        table_bottom_y = table_top_y - h

        # ---------------- WARRANTY + AMOUNT ----------------
        if page_index == len(pages) - 1:

            BLOCK_HEIGHT = 45 * mm

            if table_bottom_y - BLOCK_HEIGHT < FOOTER_SAFE_MARGIN:
                c.showPage()
                draw_letterhead()
                start_y = height - 70 * mm
            else:
                start_y = table_bottom_y - 15 * mm

            # Warranty (4 lines)
            c.setFont("Helvetica", 10)
            line_gap = 4.5 * mm
            y = start_y

            for line in WARRANTY_LINES:
                c.drawString(table_x, y, line)
                y -= line_gap

            # Amount in words
            words = f"Rupees {num2words(int(total)).capitalize()} Only."
            c.setFont("Helvetica-Bold", 11)
            c.drawString(
                table_x,
                y - 6 * mm,
                f"Amount (in words): {words}"
            )

            # ---------------- SIGNATURE ----------------
            sig_y = y - 24 * mm
            sig_len = 60 * mm
            sig_x = table_x + total_width - sig_len

            c.line(sig_x, sig_y, sig_x + sig_len, sig_y)
            c.setFont("Helvetica", 9)
            c.drawString(sig_x, sig_y - 6 * mm, "Authorized Signatory")

    # ---------------- SAVE ----------------
    c.showPage()
    c.save()
