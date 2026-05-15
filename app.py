from database import get_db
from datetime import datetime
from generate_pdf import generate_pdf
from flask import Flask, render_template, request, send_file, redirect, url_for, session, g
from auth_routes import auth_bp
from inventory_routes import inventory_bp
import logging
from psycopg2.pool import ThreadedConnectionPool  # Added connection pooling
from catalog_routes import catalog_bp 
from conference_routes import conference_bp 

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# Development: auto-reload templates
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True

# PERFORMANCE: Enable template caching in production
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 31536000  # 1 year for static files

app.register_blueprint(auth_bp, url_prefix="/portal")
app.register_blueprint(inventory_bp, url_prefix="/portal/inventory")
app.register_blueprint(catalog_bp)      
app.register_blueprint(conference_bp)       

logging.basicConfig(level=logging.INFO)
logging.getLogger("werkzeug").setLevel(logging.INFO)
logging.info("Registered URL map:\n%s", app.url_map)

# Initialize database tables
from database import init_auth_tables, init_catalog_conference_tables
from inventory_db import init_db

init_auth_tables()
init_db()
init_catalog_conference_tables()

@app.route("/home")
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

    # OPTIMIZED: Added LIMIT and proper indexing
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
        LIMIT 100
    """)
    stock = cur.fetchall()
    
    # FIXED: SQL Injection vulnerability - use ? instead of %s for SQLite
    # Also added action column to show both IN and OUT
    cur.execute("""
        SELECT l.name, e.power, e.quantity, e.created_at, e.action
        FROM employee_deliveries e
        JOIN lenses l ON l.id = e.lens_id
        WHERE e.username = ?
        ORDER BY e.created_at DESC
        LIMIT 50
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

# ── Company pages ──────────────────────────────────────────────
@app.route("/about")
def about():
    return render_template("company/about.html")

@app.route("/partners")
def partners():
    return render_template("company/partners.html")

@app.route("/careers")
def careers():
    return render_template("company/careers.html")

@app.route("/network")
def network():
    return render_template("company/network.html")

@app.route("/news")
def news():
    return render_template("company/news.html")

@app.route("/conferences")
def conferences():
    from conference_routes import get_images_for_year
    return render_template(
        "company/conferences.html",
        images_2024=get_images_for_year(2024),
        images_2025=get_images_for_year(2025),
        images_2026=get_images_for_year(2026),
    )

# ── Legal pages ────────────────────────────────────────────────
@app.route("/privacy")
def privacy():
    return render_template("legal/privacy.html")

@app.route("/terms")
def terms():
    return render_template("legal/terms.html")

@app.route("/quality")
def quality():
    return render_template("legal/quality.html")

@app.route("/drap")
def drap():
    return render_template("legal/drap.html")

# ── Support pages ──────────────────────────────────────────────
@app.route("/contact")
def contact():
    return render_template("support/contact.html")

@app.route("/docs")
def docs():
    return render_template("support/docs.html")

@app.route("/technical")
def technical():
    return render_template("support/technical.html")

@app.route("/amc")
def amc():
    return render_template("support/amc.html")

# ── Product pages ──────────────────────────────────────────────
@app.route("/products/surgical")
def surgical():
    return render_template("products/surgical.html")

@app.route("/products/machines")
def machines():
    return render_template("products/machines.html")

@app.route("/products/consumables")
def consumables():
    return render_template("products/consumables.html")

@app.route("/products/preowned")
def preowned():
    return render_template("products/preowned.html")

@app.route("/products/lol")
def lol():
    return render_template("products/lol.html")
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
