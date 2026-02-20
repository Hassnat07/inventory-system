# inventory_routes.py
from flask import Blueprint, request, jsonify, render_template, redirect, g, url_for, flash
import sqlite3
from inventory_db import get_db

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@inventory_bp.route("/add-lens", methods=["POST"])
def add_lens():
    if not g.user:
        return redirect(url_for("auth.login"))

    name = request.form.get("name", "").strip()
    if not name:
        flash("Lens name is required", "danger")
        return redirect("/inventory")

    con = get_db()
    cur = con.cursor()

    cur.execute("SELECT id FROM lenses WHERE name = ?", (name,))
    if cur.fetchone():
        flash("Lens already exists", "danger")
        con.close()
        return redirect("/inventory")

    cur.execute("INSERT INTO lenses (name) VALUES (?)", (name,))
    con.commit()
    con.close()

    flash("Lens added successfully!", "success")
    return redirect("/inventory")


@inventory_bp.route("/add-doctor", methods=["POST"])
def add_doctor():
    if not g.user:
        return redirect(url_for("auth.login"))

    name = request.form.get("name", "").strip()

    if not name:
        flash("Doctor name is required", "danger")
        return redirect("/inventory")

    con = get_db()
    cur = con.cursor()

    cur.execute("SELECT id FROM doctors WHERE name = ?", (name,))
    existing = cur.fetchone()

    if existing:
        flash("Doctor already exists!", "danger")
        con.close()
        return redirect("/inventory")

    try:
        cur.execute("INSERT INTO doctors (name) VALUES (?)", (name,))
        con.commit()
        flash("Doctor added successfully!", "success")
    except Exception as e:
        con.rollback()
        flash(f"Error: {str(e)}", "danger")
    finally:
        con.close()

    return redirect("/inventory")



@inventory_bp.route("/")
def inventory_page():
    if not g.user:
        return jsonify({"error": "Unauthorized"}), 403

    con = get_db()
    cur = con.cursor()

    selected_lens = request.args.get("lens_id")
    selected_power = request.args.get("power")

    cur.execute("SELECT id, name FROM lenses ORDER BY name")
    lenses = cur.fetchall()

    cur.execute("SELECT id, name FROM doctors ORDER BY name")
    doctors = cur.fetchall()

    # Current stock
    query = """
        SELECT l.id, l.name, s.power, s.quantity_available
        FROM inventory_stock s
        JOIN lenses l ON l.id = s.lens_id
    """
    conditions = []
    params = []

    if selected_lens:
        conditions.append("l.id = ?")
        params.append(selected_lens)
    if selected_power:
        conditions.append("s.power = ?")
        params.append(selected_power)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY l.name, s.power COLLATE NOCASE"

    cur.execute(query, params)
    stock = cur.fetchall()

    # Recent transactions — explicit column order to match template
    recent_query = """
    SELECT
        lens_name,
        power,
        doctor_name,
        quantity,
        action,
        date_time
    FROM (
        SELECT 
            l.name AS lens_name,
            si.power,
            NULL AS doctor_name,
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
    )
    ORDER BY date_time DESC
    LIMIT 50
    """

    cur.execute(recent_query)
    recent = cur.fetchall()

    # Staff Delivery Activity — only team members
    cur.execute("""
        SELECT 
            username,
            lens_name,
            power,
            quantity,
            created_at,
            doctor_name,
            action
        FROM (
            -- STOCK IN (ONLY TEAM)
            SELECT
                u.username AS username,
                l.name AS lens_name,
                si.power AS power,
                si.quantity AS quantity,
                si.created_at AS created_at,
                NULL AS doctor_name,
                'IN' AS action
            FROM stock_in si
            JOIN lenses l ON l.id = si.lens_id
            JOIN users u ON u.id = si.added_by
            WHERE u.role = 'team'

            UNION ALL

            -- STOCK OUT (ONLY TEAM)
            SELECT
                u.username AS username,
                l.name AS lens_name,
                so.power AS power,
                so.quantity AS quantity,
                so.created_at AS created_at,
                d.name AS doctor_name,
                'OUT' AS action
            FROM stock_out so
            JOIN lenses l ON l.id = so.lens_id
            JOIN users u ON u.id = so.user_id
            LEFT JOIN doctors d ON d.id = so.doctor_id
            WHERE u.role = 'team'
        )
        ORDER BY created_at DESC
    """)
    employee_log = cur.fetchall()

    print("STAFF DATA:", employee_log)

    # Debug print — keep this for now; remove later when stable
    print("\n=== DEBUG: Recent transactions ===")
    if recent:
        first = recent[0]
        print("Row type:", type(first).__name__)
        print("Has keys attribute:", hasattr(first, 'keys'))
        if hasattr(first, 'keys'):
            print("Keys:", list(first.keys()))
            print("Sample row dict:", dict(first))
            print("Quantity value:", first["quantity"])
        else:
            print("Row as tuple:", tuple(first))
            print("Quantity (position 3):", first[3])
    else:
        print("No recent rows")
    print("===================================\n")

    con.close()

    return render_template(
        "inventory.html",
        user=g.user,
        lenses=lenses,
        doctors=doctors,
        stock=stock,
        recent=recent,
        employee_log=employee_log
    )


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
    except (ValueError, TypeError) as e:
        flash(f"Invalid input: {str(e)}", "danger")
        return redirect("/inventory")

    con = get_db()
    cur = con.cursor()

    try:
        if transaction_type == "IN":
            cur.execute("""
                INSERT INTO stock_in (lens_id, power, quantity, added_by)
                VALUES (?, ?, ?, ?)
            """, (lens_id, power, quantity, g.user["id"]))

            cur.execute("""
                INSERT INTO inventory_stock (lens_id, power, quantity_available)
                VALUES (?, ?, ?)
                ON CONFLICT(lens_id, power)
                DO UPDATE SET quantity_available = quantity_available + excluded.quantity_available
            """, (lens_id, power, quantity))

        elif transaction_type == "OUT":
            doctor_id = data.get("doctor_id")
            if not doctor_id:
                flash("Doctor is required for stock OUT", "danger")
                return redirect("/inventory")

            # Safety check: enough stock?
            cur.execute("""
                SELECT quantity_available FROM inventory_stock 
                WHERE lens_id = ? AND power = ?
            """, (lens_id, power))
            current = cur.fetchone()
            if not current or current["quantity_available"] < quantity:
                flash("Not enough stock available", "danger")
                return redirect("/inventory")

            cur.execute("""
                INSERT INTO stock_out (lens_id, power, quantity, user_id, doctor_id, delivery_date)
                VALUES (?, ?, ?, ?, ?, DATE('now'))
            """, (lens_id, power, quantity, g.user["id"], doctor_id))

            cur.execute("""
                UPDATE inventory_stock
                SET quantity_available = quantity_available - ?
                WHERE lens_id = ? AND power = ?
            """, (quantity, lens_id, power))

        else:
            flash("Invalid transaction type (must be IN or OUT)", "danger")
            return redirect("/inventory")

        con.commit()
        flash(f"{transaction_type} transaction processed successfully!", "success")

    except Exception as e:
        con.rollback()
        flash(f"Transaction failed: {str(e)}", "danger")
    finally:
        con.close()

    return redirect("/inventory#inventory-levels")


@inventory_bp.route("/api/stock")
def view_stock():
    con = get_db()
    cur = con.cursor()
    try:
        cur.execute("""
            SELECT l.name, l.brand, s.power, s.quantity_available, s.reorder_level
            FROM inventory_stock s
            JOIN lenses l ON l.id = s.lens_id
            ORDER BY l.name, s.power
        """)
        rows = cur.fetchall()

        return jsonify([
            {
                "lens": r["name"],
                "brand": r["brand"] or "N/A",
                "power": r["power"],
                "quantity": r["quantity_available"],
                "reorder": r["reorder_level"]
            } for r in rows
        ])
    finally:
        con.close()