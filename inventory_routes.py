# inventory_routes.py
from flask import Blueprint, request, jsonify, render_template, redirect, g, url_for, flash
import psycopg2
from psycopg2.extras import RealDictCursor
from inventory_db import get_db

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
        selected_lens = request.args.get("lens_id")
        selected_power = request.args.get("power")

        cur.execute("SELECT id, name FROM lenses ORDER BY name")
        lenses = cur.fetchall()

        cur.execute("SELECT id, name FROM doctors ORDER BY name")
        doctors = cur.fetchall()

        # Stock Query
        query = """
            SELECT l.id, l.name, s.power, s.quantity_available
            FROM inventory_stock s
            JOIN lenses l ON l.id = s.lens_id
        """
        conditions = []
        params = []

        if selected_lens:
            conditions.append("l.id = %s")
            params.append(selected_lens)

        if selected_power:
            conditions.append("s.power = %s")
            params.append(selected_power)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY l.name, s.power"

        cur.execute(query, params)
        stock = cur.fetchall()
        # Recent Transactions
        cur.execute("""
            SELECT
                l.name AS lens_name,
                si.power,
                NULL::text AS doctor_name,
                si.quantity,
                'IN' AS action,
                si.created_at AS date_time
            FROM stock_in si
            JOIN lenses l ON l.id = si.lens_id

            UNION ALL

            SELECT
                l.name AS lens_name,
                so.power,
                d.name AS doctor_name,
                so.quantity,
                'OUT' AS action,
                so.created_at AS date_time
            FROM stock_out so
            JOIN lenses l ON l.id = so.lens_id
            LEFT JOIN doctors d ON d.id = so.doctor_id

            ORDER BY date_time DESC
            LIMIT 50
        """)
        recent = cur.fetchall()

        # -----------------------------
        # STAFF DELIVERY ACTIVITY
        # -----------------------------
        cur.execute("""
            SELECT
                ed.username,
                l.name AS lens_name,
                d.name AS doctor_name,
                ed.power,
                ed.quantity,
                ed.action,
                ed.created_at
            FROM employee_deliveries ed
            JOIN lenses l ON l.id = ed.lens_id
            LEFT JOIN doctors d ON d.id = ed.doctor_id
            ORDER BY ed.created_at DESC
        """)
        staff_deliveries = cur.fetchall()

        return render_template(
            "inventory.html",
            user=g.user,
            lenses=lenses,
            doctors=doctors,
            stock=stock,
            recent=recent,
            staff_deliveries=staff_deliveries
        )
        # -----------------------------
# STAFF DELIVERY ACTIVITY
# -----------------------------


# -----------------------------
# STOCK IN / OUT
# -----------------------------
@inventory_bp.route("/stock-in", methods=["POST"])
def stock_in():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 403

    data = request.form

    try:
        lens_id = int(data.get("lens_id"))
        power = data.get("power", "").strip()
        quantity = int(data.get("quantity"))
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
                INSERT INTO stock_in (lens_id, power, quantity, added_by)
                VALUES (%s, %s, %s, %s)
            """, (lens_id, power, quantity, g.user['id']))

            cur.execute("""
                INSERT INTO inventory_stock (lens_id, power, quantity_available)
                VALUES (%s, %s, %s)
                ON CONFLICT (lens_id, power)
                DO UPDATE SET
                    quantity_available =
                    inventory_stock.quantity_available + EXCLUDED.quantity_available
            """, (lens_id, power, quantity))

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
                VALUES (%s, %s, %s, %s, %s, CURRENT_DATE)
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

    return redirect(url_for("inventory.inventory_page") + "#inventory-levels")


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
