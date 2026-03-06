from flask import Blueprint, request, jsonify, render_template, redirect, g, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor
from database import get_db

inventory_bp = Blueprint("inventory", __name__)


# -----------------------------
# ADD LENS
# -----------------------------
@inventory_bp.route("/add-lens", methods=["POST"])
def add_lens():
    if not g.user:
        return redirect(url_for("auth.login"))

    name = request.form.get("name", "").strip()
    if not name:
        flash("Lens name is required", "danger")
        return redirect(url_for("inventory.inventory_page"))

    con = get_db()
    cur = con.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("SELECT id FROM lenses WHERE name = %s", (name,))
        if cur.fetchone():
            flash("Lens already exists", "danger")
            return redirect(url_for("inventory.inventory_page"))

        cur.execute("INSERT INTO lenses (name) VALUES (%s)", (name,))
        con.commit()
        flash("Lens added successfully!", "success")

    except psycopg2.Error as e:
        con.rollback()
        flash(f"Database error: {e.pgerror or str(e)}", "danger")
    finally:
        cur.close()
        con.close()

    return redirect(url_for("inventory.inventory_page"))


# -----------------------------
# ADD DOCTOR
# -----------------------------
@inventory_bp.route("/add-doctor", methods=["POST"])
def add_doctor():
    if not g.user:
        return redirect(url_for("auth.login"))

    name = request.form.get("name", "").strip()
    if not name:
        flash("Doctor name is required", "danger")
        return redirect(url_for("inventory.inventory_page"))

    con = get_db()
    cur = con.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("SELECT id FROM doctors WHERE name = %s", (name,))
        if cur.fetchone():
            flash("Doctor already exists!", "danger")
            return redirect(url_for("inventory.inventory_page"))

        cur.execute("INSERT INTO doctors (name) VALUES (%s)", (name,))
        con.commit()
        flash("Doctor added successfully!", "success")

    except psycopg2.Error as e:
        con.rollback()
        flash(f"Database error: {e.pgerror or str(e)}", "danger")
    finally:
        cur.close()
        con.close()

    return redirect(url_for("inventory.inventory_page"))


# -----------------------------
# INVENTORY PAGE
# -----------------------------
@inventory_bp.route("/")
def inventory_page():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 403

    con = get_db()
    cur = con.cursor(cursor_factory=RealDictCursor)

    try:
        # Lenses
        cur.execute("SELECT id, name FROM lenses ORDER BY name")
        lenses = cur.fetchall()

        # Doctors
        cur.execute("SELECT id, name FROM doctors ORDER BY name")
        doctors = cur.fetchall()

        # ==========================
        # FILTERED INVENTORY STOCK
        # ==========================
        lens_filter = request.args.get("inv_lens_id")
        power_filter = request.args.get("inv_power", "").strip()

        stock_query = """
            SELECT l.id, l.name, s.power, s.quantity_available
            FROM inventory_stock s
            JOIN lenses l ON l.id = s.lens_id
            WHERE 1=1
        """
        stock_params = []

        if lens_filter:
            stock_query += " AND l.id = %s"
            stock_params.append(int(lens_filter))

        if power_filter:
            stock_query += " AND s.power = %s"
            stock_params.append(power_filter)

        stock_query += " ORDER BY l.name, s.power"

        cur.execute(stock_query, stock_params)
        stock = cur.fetchall()

        # ==========================
        # CALCULATE TOTAL COUNTS
        # ==========================
        total_stock_count = sum(s['quantity_available'] for s in stock) if stock else 0

        lens_totals: dict[str, float] = {}
        for s in stock:
            name = s['name']
            if name not in lens_totals:
                lens_totals[name] = 0
            lens_totals[name] += s['quantity_available']

        lens_totals_list = [{'name': k, 'total': v} for k, v in sorted(lens_totals.items())]

        # -------------------------
        # STAFF DELIVERY FILTER LOGIC
        # -------------------------
        staff_query = """
            SELECT
                ed.username,
                l.name AS lens_name,
                d.name AS doctor_name,
                ed.power,
                ed.quantity,
                ed.action,
                ed.created_at
            FROM employee_deliveries ed
            LEFT JOIN lenses l ON l.id = ed.lens_id
            LEFT JOIN doctors d ON d.id = ed.doctor_id
        """

        conditions = []
        params = []

        # If user is NOT admin → show only their records
        if g.user["role"] != "admin":
            conditions.append("ed.username = %s")
            params.append(g.user["username"])

        # Admin can filter staff
        emp = request.args.get("emp")
        if emp and g.user["role"] == "admin":
            conditions.append("ed.username = %s")
            params.append(emp)

        emp_doc = request.args.get("emp_doc")
        emp_lens = request.args.get("emp_lens")
        emp_date = request.args.get("emp_date")

        if emp_doc:
            conditions.append("ed.doctor_id = %s")
            params.append(emp_doc)

        if emp_lens:
            conditions.append("ed.lens_id = %s")
            params.append(emp_lens)

        if emp_date:
            conditions.append("DATE(ed.created_at) = %s")
            params.append(emp_date)

        if conditions:
            staff_query += " WHERE " + " AND ".join(conditions)

        staff_query += " ORDER BY ed.created_at DESC, ed.id DESC"

        cur.execute(staff_query, params)
        staff_deliveries = cur.fetchall()

        # Staff Dropdown List
        cur.execute("""
            SELECT DISTINCT username
            FROM employee_deliveries
            ORDER BY username
        """)
        staff_list = cur.fetchall()

        return render_template(
            "inventory.html",
            user=g.user,
            lenses=lenses,
            doctors=doctors,
            stock=stock,
            staff_deliveries=staff_deliveries,
            staff_list=staff_list,
            total_stock_count=total_stock_count,
            lens_totals=lens_totals_list
        )

    finally:
        cur.close()
        con.close()


# -----------------------------
# STOCK IN / OUT
# -----------------------------
@inventory_bp.route("/stock-in", methods=["POST"])
def stock_in():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.form

    try:
        lens_id = int(data.get("lens_id", ""))
        power = data.get("power", "").strip()
        quantity = float(data.get("quantity", ""))
        transaction_type = data.get("type", "IN").upper()

        if quantity <= 0:
            raise ValueError("Quantity must be positive")

    except Exception as e:
        flash(f"Invalid input: {str(e)}", "danger")
        return redirect(url_for("inventory.inventory_page"))

    con = get_db()
    cur = con.cursor(cursor_factory=RealDictCursor)

    try:
        if transaction_type == "IN":

            cur.execute("""
                INSERT INTO stock_in (lens_id, power, quantity, added_by, created_at)
                VALUES (%s, %s, %s, %s, NOW())
            """, (lens_id, power, quantity, g.user['id']))

            cur.execute("""
                INSERT INTO inventory_stock (lens_id, power, quantity_available)
                VALUES (%s, %s, %s)
                ON CONFLICT (lens_id, power)
                DO UPDATE SET
                    quantity_available =
                    inventory_stock.quantity_available + EXCLUDED.quantity_available
            """, (lens_id, power, quantity))

            cur.execute("""
                INSERT INTO employee_deliveries
                (username, lens_id, doctor_id, power, quantity, action, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """, (
                g.user["username"],
                lens_id,
                None,
                power,
                quantity,
                "IN"
            ))

        elif transaction_type == "OUT":

            doctor_id = data.get("doctor_id")
            if not doctor_id:
                flash("Doctor is required for stock OUT", "danger")
                return redirect(url_for("inventory.inventory_page"))

            cur.execute("""
                SELECT quantity_available
                FROM inventory_stock
                WHERE lens_id = %s AND power = %s
            """, (lens_id, power))

            current = cur.fetchone()

            if not current or current["quantity_available"] < quantity:
                flash("Not enough stock available", "danger")
                return redirect(url_for("inventory.inventory_page"))

            cur.execute("""
                INSERT INTO stock_out (lens_id, power, quantity, user_id, doctor_id, delivery_date)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (lens_id, power, quantity, g.user['id'], doctor_id))

            cur.execute("""
                INSERT INTO employee_deliveries
                (username, lens_id, doctor_id, power, quantity, action, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
            """, (
                g.user["username"],
                lens_id,
                doctor_id,
                power,
                quantity,
                "OUT"
            ))

            cur.execute("""
                UPDATE inventory_stock
                SET quantity_available = quantity_available - %s
                WHERE lens_id = %s AND power = %s
            """, (quantity, lens_id, power))

        else:
            flash("Invalid transaction type", "danger")
            return redirect(url_for("inventory.inventory_page"))

        con.commit()
        flash("Transaction processed successfully!", "success")

    except psycopg2.Error as e:
        con.rollback()
        flash(f"Database error: {e.pgerror or str(e)}", "danger")
    finally:
        cur.close()
        con.close()

    return redirect(
        url_for(
            "inventory.inventory_page",
            doctor_id=request.form.get("doctor_id") or "",
            lens_id=request.form.get("lens_id") or "",
            type=request.form.get("type") or ""
        )
)

# -----------------------------
# low-stock-alert
# -----------------------------

@inventory_bp.route("/low-stock-alert")
def low_stock_alert():
    if not g.user:
        return redirect(url_for("auth.login"))

    con = get_db()
    cur = con.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
            SELECT l.name, s.power, s.quantity_available
            FROM inventory_stock s
            JOIN lenses l ON l.id = s.lens_id
            WHERE s.quantity_available > 0
            ORDER BY l.name, s.power
        """)
        stock = cur.fetchall()

        # Apply alert rules
        alerted_items = []
        for item in stock:
            power = float(item['power']) if item['power'] else 0
            qty = item['quantity_available']
            alert = False

            if 1 <= power <= 5 and qty < 5:
                alert = True
            elif 5 < power <= 18 and qty < 15:
                alert = True
            elif 18 < power <= 23 and qty < 50:
                alert = True
            elif 23 < power <= 37 and qty < 7:
                alert = True

            alerted_items.append({
                'name': item['name'],
                'power': item['power'],
                'quantity': qty,
                'alert': alert
            })

        return render_template("low_stock_alert.html", items=alerted_items)

    finally:
        cur.close()
        con.close()


# -----------------------------
# API STOCK
# -----------------------------
@inventory_bp.route("/api/stock")
def view_stock():
    con = get_db()
    cur = con.cursor(cursor_factory=RealDictCursor)

    try:
        cur.execute("""
            SELECT l.name, l.brand, s.power,
                   s.quantity_available, s.reorder_level
            FROM inventory_stock s
            JOIN lenses l ON l.id = s.lens_id
            ORDER BY l.name, s.power
        """)

        rows = cur.fetchall()

        return jsonify(rows)

    except psycopg2.Error as e:
        return jsonify({"error": e.pgerror or str(e)}), 500
    finally:
        cur.close()
        con.close()

