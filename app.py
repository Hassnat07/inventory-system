
from database import get_db
from datetime import datetime
from generate_pdf import generate_pdf
from flask import Flask, render_template, request, send_file, redirect, url_for, session, g
from auth_routes import auth_bp
from inventory_routes import inventory_bp
import logging

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Added for session security

# Development: auto-reload templates and clear Jinja cache in debug mode
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

app.register_blueprint(auth_bp, url_prefix="/portal")
app.register_blueprint(inventory_bp, url_prefix="/portal/inventory")

# Basic logging for debugging route mapping and incoming requests
logging.basicConfig(level=logging.INFO)
logging.getLogger("werkzeug").setLevel(logging.INFO)
logging.info("Registered URL map:\n%s", app.url_map)

# Initialize database tables
from database import init_auth_tables
from inventory_db import init_db

init_auth_tables()
init_db()

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/admin")
def admin_dashboard():
    user = g.get("user")
    if not user or user.get("role") != "admin":
        return redirect(url_for("auth.login"))
    return render_template("admin_dashboard.html")

@app.route("/team")
def team_dashboard():
    user = g.get("user")
    if not user or user.get("role") != "team":
        return redirect(url_for("auth.login"))

    con = get_db()
    cur = con.cursor()

    cur.execute("""
        SELECT l.name, s.power,
               COALESCE(SUM(
                   CASE WHEN s.type='IN' THEN s.quantity ELSE -s.quantity END
               ),0) AS qty
        FROM stock_transactions s
        JOIN lenses l ON l.id = s.lens_id
        GROUP BY l.name, s.power
        HAVING SUM(
            CASE WHEN s.type='IN' THEN s.quantity ELSE -s.quantity END
        ) > 0
        ORDER BY l.name
    """)
    stock = cur.fetchall()
    cur.execute("""
    SELECT l.name, e.power, e.quantity, e.created_at
    FROM employee_deliveries e
    JOIN lenses l ON l.id = e.lens_id
    WHERE e.username = %s
    ORDER BY e.created_at DESC
""", (user["username"],))
    my_deliveries = cur.fetchall()

    con.close()

    return render_template(
        "team_dashboard.html",
        stock=stock,
        my_deliveries=my_deliveries,
        username=user["username"]
    )

@app.before_request
def load_logged_in_user():
    logging.info("Incoming request: path=%s endpoint=%s method=%s", request.path, request.endpoint, request.method)
    g.user = None
    # In debug mode clear Jinja cache to ensure template edits appear immediately
    try:
        if app.debug:
            app.jinja_env.cache.clear()
    except Exception:
        pass

    if "user_id" in session:
        g.user = {
            "id": session.get("user_id"),
            "username": session.get("username"),
            "role": session.get("role")
        }


@app.route("/invoice", methods=["GET", "POST"])
def invoice():
    if request.method == "POST":
        customer_name = request.form["customer"]
        total = float(request.form["total"])

        use_letterhead = "letterhead" in request.form
        print_ntn = "ntn" in request.form

        pdf_path = "invoice.pdf"

        generate_pdf(
            invoice_no=560,
            date_str=datetime.today().strftime("%d/%m/%Y"),
            customer={"name": customer_name, "address": ""},
            items=[],
            total=total,
            save_path=pdf_path,
            use_letterhead=use_letterhead,
            print_ntn=print_ntn
        )
        return send_file(pdf_path, as_attachment=True)
    return render_template("invoice.html")

if __name__ == "__main__":
    app.run(debug=True)
    
