"""
invoice_app.py
Clean Corporate Invoice Generator (Tkinter + SQLite + ReportLab)
Per-customer invoice numbering that increments by STEP (3).
"""

import os
import sqlite3
from datetime import datetime
from tkinter import *
from tkinter import ttk, messagebox, filedialog
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from PIL import Image

# optional nicer words output
try:
    from num2words import num2words
except Exception:
    num2words = None

DB_FILE = "invoices.db"
LOGO_FILENAME = "logo.png"
STEP = 3
DEFAULT_START = 560


# -------------------------
# Database helpers
# -------------------------
def init_db():
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT,
        next_invoice_no INTEGER
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_no INTEGER,
        date TEXT,
        customer_id INTEGER,
        total REAL,
        amount_words TEXT,
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS invoice_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER,
        product_id INTEGER,
        description TEXT,
        power TEXT,
        qty INTEGER,
        price REAL,
        amount REAL,
        FOREIGN KEY(invoice_id) REFERENCES invoices(id),
        FOREIGN KEY(product_id) REFERENCES products(id)
    );
    """)
    con.commit()
    con.close()


def get_customer_next_invoice_no(customer_id):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("SELECT next_invoice_no FROM customers WHERE id=?", (customer_id,))
    r = cur.fetchone()
    if r and r[0] is not None:
        con.close()
        return int(r[0])

    cur.execute("SELECT MAX(invoice_no) FROM invoices WHERE customer_id=?", (customer_id,))
    r2 = cur.fetchone()
    con.close()
    if r2 and r2[0] is not None:
        return int(r2[0]) + STEP

    return DEFAULT_START


def update_customer_next_invoice_no(customer_id, next_no):
    con = sqlite3.connect(DB_FILE)
    cur = con.cursor()
    cur.execute("UPDATE customers SET next_invoice_no=? WHERE id=?", (next_no, customer_id))
    con.commit()
    con.close()


# -------------------------
# Utility: number to words
# -------------------------
def rupees_in_words(amount):
    try:
        if num2words:
            words = num2words(int(round(amount)), lang='en')
            return f"Rupees {words.capitalize()} Only."
        else:
            return f"Rupees {int(round(amount)):,} Only."
    except Exception:
        return f"Rupees {int(round(amount)):,} Only."

def format_power(value: str) -> str:
    """
    Converts:
      8   -> 8.0D
      7.5 -> 7.5D
      ""  -> ""
    """
    value = value.strip()
    if not value:
        return ""

    try:
        num = float(value)
        if num.is_integer():
            return f"{int(num)}.0D"
        return f"{num}D"
    except ValueError:
        return value



# -------------------------
# PDF GENERATION (YOUR CURRENT VERSION) — unchanged
# -------------------------
def generate_pdf(invoice_no, date_str, customer, items, total, save_path, use_letterhead=True,print_ntn=True):
    import os, sys
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib import colors
    from num2words import num2words

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








# -------------------------
# GUI APPLICATION
# -------------------------
class InvoiceApp:

    # ----------------------------------------------------------
    # ✅ FIXED AUTO-FILL PRICE & DESCRIPTION WHEN PRODUCT SELECTED
    # ----------------------------------------------------------
    
    def on_product_selected(self, event=None):
        label = self.product_combo.get()
        if not label:
            return

        prod_id, prod_name, prod_price = self.products.get(label, (None, "", 0.0))
        self.desc_entry.delete(0, END)
        self.price_entry.delete(0, END)
        self.desc_entry.insert(0, prod_name)
        self.price_entry.insert(0, f"{prod_price:.2f}")


    # ----------------------------------------------------------

    def __init__(self, root):
        self.use_letterhead_var = BooleanVar(value=True)
        self.print_ntn_var = BooleanVar(value=True)
        self.root = root
        root.title("Invoice Generator - Local (Clean Corporate)")
        root.geometry("1000x640")
        self.conn = sqlite3.connect(DB_FILE)

        self.invoice_no_var = StringVar()
        self.date_var = StringVar(value=datetime.today().strftime("%d/%m/%Y"))
        self.total_var = StringVar(value="0.00")
        self.items = []

        self.create_widgets()
        self.refresh_customers()
        self.refresh_products()

        if not self.invoice_no_var.get():
            self.invoice_no_var.set(str(DEFAULT_START))

    def create_widgets(self):

        main = Frame(self.root, padx=10, pady=8)
        main.pack(fill=BOTH, expand=True)

        meta = Frame(main)
        meta.pack(fill=X, pady=4)
        Label(meta, text="Invoice No:").pack(side=LEFT)
        Entry(meta, textvariable=self.invoice_no_var, width=10).pack(side=LEFT, padx=6)
        Label(meta, text="Date:").pack(side=LEFT)
        Entry(meta, textvariable=self.date_var, width=14).pack(side=LEFT, padx=6)

        cust_frame = LabelFrame(main, text="Customer", pady=6)
        cust_frame.pack(fill=X, pady=6)
        left = Frame(cust_frame)
        left.pack(side=LEFT, fill=X, expand=True)

        self.customer_combo = ttk.Combobox(left, values=[], state="readonly", width=60)
        self.customer_combo.pack(side=LEFT, padx=6, pady=4)
        self.customer_combo.bind("<<ComboboxSelected>>", self.on_customer_selected)

        Button(left, text="Add Customer", command=self.add_customer_dialog).pack(side=LEFT, padx=6)
        Button(left, text="Delete Customer", fg="red",command=self.delete_customer).pack(side=LEFT, padx=6)


        prod_frame = LabelFrame(main, text="Products / Items", pady=6)
        prod_frame.pack(fill=X, pady=6)
        p_top = Frame(prod_frame)
        p_top.pack(fill=X)

        self.product_combo = ttk.Combobox(p_top, values=[], state="readonly", width=40)
        self.product_combo.pack(side=LEFT, padx=6)
        self.product_combo.bind("<<ComboboxSelected>>", self.on_product_selected)

        Button(p_top, text="Add Product", command=self.add_product_dialog).pack(side=LEFT, padx=6)

        item_fields = Frame(prod_frame)
        item_fields.pack(fill=X, pady=4)

        Label(item_fields, text="Description").grid(row=0, column=0, padx=4)
        self.desc_entry = Entry(item_fields, width=40)
        self.desc_entry.grid(row=0, column=1, padx=4)

        Label(item_fields, text="Power").grid(row=0, column=2, padx=4)
        self.power_entry = Entry(item_fields, width=10)
        self.power_entry.grid(row=0, column=3, padx=4)

        Label(item_fields, text="Qty").grid(row=0, column=4, padx=4)
        self.qty_entry = Entry(item_fields, width=6)
        self.qty_entry.grid(row=0, column=5, padx=4)

        Label(item_fields, text="Price").grid(row=0, column=6, padx=4)
        self.price_entry = Entry(item_fields, width=10)
        self.price_entry.grid(row=0, column=7, padx=4)

        Button(prod_frame, text="Add Item to Invoice", command=self.add_item).pack(pady=6)

        cols = ("#", "Description", "Power", "Qty", "Price", "Amount")
        self.tree = ttk.Treeview(main, columns=cols, show="headings", height=8)

        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, anchor=CENTER)

        self.tree.pack(fill=X, pady=6)

        btn_row = Frame(main)
        btn_row.pack(fill=X)
        Button(btn_row, text="Remove Selected Item", command=self.remove_selected).pack(side=LEFT, padx=6)
        Button(btn_row, text="Clear Items", command=self.clear_items).pack(side=LEFT, padx=6)
        bottom = Frame(main)
        bottom.pack(fill=X, pady=8)
        Checkbutton(
            bottom,
            text="Print on Letterhead",
            variable=self.use_letterhead_var
        ).pack(side=LEFT, padx=10)

        Checkbutton(
            bottom,
            text="Print NTN No",
            variable=self.print_ntn_var
            ).pack(side=LEFT, padx=10)



        Label(bottom, text="Total:").pack(side=LEFT, padx=6)
        Entry(bottom, textvariable=self.total_var, width=12, state="readonly").pack(side=LEFT)
        Button(bottom, text="Save & Generate PDF", command=self.save_and_generate).pack(side=RIGHT, padx=6)
        bottom = Frame(main)
        bottom.pack(fill=X, pady=8)

    # ---------------- CUSTOMER / PRODUCTS ----------------

    def refresh_customers(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, name FROM customers ORDER BY name;")
        rows = cur.fetchall()

        self.customers = {f"{r[1]} (#{r[0]})": r[0] for r in rows}
        vals = list(self.customers.keys())
        self.customer_combo['values'] = vals

        if vals:
            self.customer_combo.current(0)
            self.on_customer_selected()

    def refresh_products(self):
        cur = self.conn.cursor()
        cur.execute("SELECT id, name, price FROM products ORDER BY name;")
        rows = cur.fetchall()

        self.products = {}
        for r in rows:
            label = f"{r[1]} - {r[2]:.2f} (#{r[0]})"
            self.products[label] = (r[0], r[1], r[2])

        vals = list(self.products.keys())
        self.product_combo['values'] = vals

        if vals:
            self.product_combo.current(0)

    # ----------------------------------------------------
    # ADD CUSTOMER DIALOG — unchanged
    # ----------------------------------------------------

    def add_customer_dialog(self):
        self.invoice_no_var.set("")

        d = Toplevel(self.root)
        d.title("Add Customer")

        Label(d, text="Name:").grid(row=0, column=0, padx=6, pady=6)
        name_e = Entry(d, width=50)
        name_e.grid(row=0, column=1, padx=6, pady=6)

        Label(d, text="Address:").grid(row=1, column=0, padx=6, pady=6)
        addr_e = Entry(d, width=50)
        addr_e.grid(row=1, column=1, padx=6, pady=6)

        Label(d, text="Start Invoice No (optional):").grid(row=2, column=0, padx=6, pady=6)
        start_e = Entry(d, width=20)
        start_e.grid(row=2, column=1, padx=6, pady=6, sticky=W)

        def save():
            name = name_e.get().strip()
            addr = addr_e.get().strip()
            start_val = start_e.get().strip()

            next_inv = None
            if start_val:
                try:
                    next_inv = int(start_val)
                except:
                    messagebox.showerror("Error", "Start Invoice No must be an integer")
                    return

            if not name:
                messagebox.showerror("Error", "Customer name required")
                return

            cur = self.conn.cursor()
            cur.execute("INSERT INTO customers (name,address,next_invoice_no) VALUES (?,?,?)",
                        (name, addr, next_inv))
            self.conn.commit()
            d.destroy()

            self.refresh_customers()

            cur.execute("SELECT id FROM customers WHERE name=? ORDER BY id DESC LIMIT 1", (name,))
            r = cur.fetchone()
            if r:
                new_id = r[0]

                for lab, cid in self.customers.items():
                    if cid == new_id:
                        self.customer_combo.set(lab)
                        break

                if next_inv is not None:
                    self.invoice_no_var.set(str(next_inv))
                else:
                    self.invoice_no_var.set(str(get_customer_next_invoice_no(new_id)))

        Button(d, text="Save", command=save).grid(row=3, column=1, sticky=E, padx=6, pady=6)

    # ----------------------------------------------------
    # ADD PRODUCT DIALOG — unchanged
    # ----------------------------------------------------

    def add_product_dialog(self):
        d = Toplevel(self.root)
        d.title("Add Product")

        Label(d, text="Name:").grid(row=0, column=0, padx=6, pady=6)
        name_e = Entry(d, width=40)
        name_e.grid(row=0, column=1, padx=6, pady=6)

        Label(d, text="Price:").grid(row=1, column=0, padx=6, pady=6)
        price_e = Entry(d, width=15)
        price_e.grid(row=1, column=1, padx=6, pady=6)

        def save():
            name = name_e.get().strip()

            try:
                price = float(price_e.get().strip())
            except:
                messagebox.showerror("Error", "Enter valid numeric price")
                return

            if not name:
                messagebox.showerror("Error", "Product name required")
                return

            cur = self.conn.cursor()
            cur.execute("INSERT INTO products (name,price) VALUES (?,?)", (name, price))
            self.conn.commit()
            d.destroy()
            self.refresh_products()

        Button(d, text="Save", command=save).grid(row=2, column=1, sticky=E, padx=6, pady=6)

    # ----------------------------------------------------
    # ITEM MANAGEMENT — unchanged
    # ----------------------------------------------------

    def add_item(self):
        desc = self.desc_entry.get().strip()
        raw_power = self.power_entry.get().strip()
        power = ""
        if raw_power:
            try:
                power = f"{float(raw_power):.1f}D"
            except ValueError:
                messagebox.showerror("Error", "Power must be numeric (e.g. 8 or 7.5)")
                return

        try:
            qty = int(self.qty_entry.get().strip())
        except:
            messagebox.showerror("Error", "Qty must be integer")
            return

        try:
            price = float(self.price_entry.get().strip())
        except:
            messagebox.showerror("Error", "Price must be numeric")
            return

        if not desc:
            messagebox.showerror("Error", "Description required")
            return

        amount = qty * price
        item = {"description": desc, "power": power, "qty": qty, "price": price, "amount": amount}

        self.items.append(item)
        self.refresh_items_view()

        #self.desc_entry.delete(0, END)
        self.power_entry.delete(0, END)
        self.qty_entry.delete(0, END)
        #self.price_entry.delete(0, END)
        self.on_product_selected()

    def refresh_items_view(self):
        for r in self.tree.get_children():
            self.tree.delete(r)

        total = 0.0
        for idx, it in enumerate(self.items, start=1):
            total += it['amount']
            self.tree.insert("", END, values=(
                idx,
                it['description'],
                it['power'],
                it['qty'],
                f"{it['price']:.2f}",
                f"{it['amount']:.2f}"
            ))

        self.total_var.set(f"{total:.2f}")

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return

        idx = self.tree.index(sel[0])
        del self.items[idx]
        self.refresh_items_view()

    def clear_items(self):
        if messagebox.askyesno("Confirm", "Clear all items?"):
            self.items = []
            self.refresh_items_view()

    # ----------------------------------------------------
    # CUSTOMER SELECTION
    # ----------------------------------------------------

    def on_customer_selected(self, event=None):
        label = self.customer_combo.get()

        if not label:
            self.invoice_no_var.set("")
            return

        cust_id = self.customers.get(label)
        if not cust_id:
            self.invoice_no_var.set("")
            return

        next_no = get_customer_next_invoice_no(cust_id)
        self.invoice_no_var.set(str(next_no))

    # ----------------------------------------------------
    # SAVE & GENERATE — unchanged
    # ----------------------------------------------------

    def save_and_generate(self):
        import shutil

        cust_label = self.customer_combo.get()
        cust_id = self.customers.get(cust_label)

        if not cust_id:
            messagebox.showerror("Error", "Select or add a customer")
            return

        if not self.items:
            messagebox.showerror("Error", "Add at least one item")
            return

        try:
            invoice_no = int(self.invoice_no_var.get())
        except:
            messagebox.showerror("Error", "Invalid invoice number")
            return

        date_str = self.date_var.get()
        total = float(self.total_var.get())
        amount_words = rupees_in_words(total)

        cur = self.conn.cursor()

        def do_insert():
            cur.execute(
                "INSERT INTO invoices (invoice_no,date,customer_id,total,amount_words) VALUES (?,?,?,?,?)",
                (invoice_no, date_str, cust_id, total, amount_words),
            )
            invoice_id = cur.lastrowid

            for it in self.items:
                cur.execute(
                    """INSERT INTO invoice_items (invoice_id, product_id, description, power, qty, price, amount)
                       VALUES (?,?,?,?,?,?,?)""",
                    (invoice_id, None, it["description"], it["power"], it["qty"], it["price"], it["amount"]),
                )

            self.conn.commit()
            return invoice_id

        # First try inserting
        try:
            invoice_id = do_insert()
            update_customer_next_invoice_no(cust_id, invoice_no + STEP)

        except sqlite3.IntegrityError:
            try:
                self.conn.rollback()
            except:
                pass

            resp = messagebox.askquestion(
                "Invoice Exists",
                f"Invoice number {invoice_no} already exists.\n\n"
                "Yes = Replace (delete old invoice)\n"
                "No = Cancel and change manually.",
                icon="warning"
            )

            if resp != "yes":
                return

            cur.execute("SELECT id FROM invoices WHERE invoice_no=? LIMIT 1", (invoice_no,))
            row = cur.fetchone()

            if not row:
                messagebox.showerror("Error", "Invoice not found for deletion.")
                return

            existing_id = row[0]

            try:
                with self.conn:
                    self.conn.execute("DELETE FROM invoice_items WHERE invoice_id=?", (existing_id,))
                    self.conn.execute("DELETE FROM invoices WHERE id=?", (existing_id,))
            except Exception as e:
                messagebox.showerror("Error", f"Deletion failed: {e}")
                return

            try:
                invoice_id = do_insert()
            except:
                messagebox.showerror("Error", "Insert failed even after deletion.")
                return
        update_customer_next_invoice_no(cust_id, invoice_no + STEP)

        # Prepare customer dict for PDF
        cur.execute("SELECT name, address FROM customers WHERE id=?", (cust_id,))
        row = cur.fetchone()
        customer = {"name": row[0], "address": row[1] or ""}

        default_name = f"Invoice_{invoice_no}.pdf"
        path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF Files", "*.pdf")]
        )

        if not path:
            return

        try:
            generate_pdf(invoice_no, date_str, customer, self.items, total, path,use_letterhead=self.use_letterhead_var.get(),print_ntn=self.print_ntn_var.get())
            messagebox.showinfo("Success", f"PDF Generated:\n{path}")
        except Exception as e:
            messagebox.showwarning("PDF Error", str(e))

        self.items = []
        self.refresh_items_view()
        self.invoice_no_var.set(str(get_customer_next_invoice_no(cust_id)))

    def delete_customer(self):
        label = self.customer_combo.get()
        if not label:
            messagebox.showerror("Error", "Select a customer first")
            return
        cust_id = self.customers.get(label)
        if not cust_id:
            return
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM invoices WHERE customer_id=?", (cust_id,))
        count = cur.fetchone()[0]
        if count > 0:
            messagebox.showwarning(
                "Not Allowed",
                "This customer has invoices.\nCannot delete."
                )
            return
        if not messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete:\n\n{label}?"
            ):
            return
        cur.execute("DELETE FROM customers WHERE id=?", (cust_id,))
        self.conn.commit()
        self.refresh_customers()
        self.invoice_no_var.set("")
        messagebox.showinfo("Deleted", "Customer deleted successfully")     

# -------------------------
# MAIN
# -------------------------
def main():
    init_db()
    root = Tk()
    app = InvoiceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
