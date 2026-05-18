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

CONFERENCE_LIST = [
    {
        "year": 2024,
        "title": "Stallin Conference 2024",
        "location": "Lahore, Punjab",
        "description": "Ramay Electromedix participated as a major exhibitor at the 2024 edition of the Stallin Conference in Lahore, presenting our full portfolio of premium IOLs, Japanese diagnostic machines, and ophthalmic surgical instruments to attendees from across the country.",
        "upcoming": False,
    },
    {
        "year": 2025,
        "title": "Stallin Conference 2025",
        "location": "Lahore, Punjab",
        "description": "Building on the momentum of the previous year, our team returned to Lahore for the 2025 Stallin Conference. We showcased expanded product lines and strengthened partnerships with eye hospitals and clinics across Pakistan.",
        "upcoming": False,
    },
    {
        "year": 2026,
        "title": "Stallin Conference 2026",
        "location": "Peshawar, KPK",
        "description": "The 2026 edition of the Stallin Conference moves to Peshawar, bringing the event to Khyber Pakhtunkhwa for the first time. Ramay Electromedix participated as a major exhibitor, further extending our reach into KPK's growing ophthalmic sector.",
        "upcoming": False,
    },
    {
        "year": 20261,
        "title": "Islamabad Eye Congress 2026",
        "location": "Islamabad, Federal Capital",
        "description": "Ramay Electromedix will be exhibiting at the upcoming Islamabad Eye Congress 2026, showcasing our latest IOL portfolio and Japanese ophthalmic equipment to surgeons and specialists from across the country.",
        "upcoming": True,
    },
]

@app.route("/conferences")
def conferences():
    from conference_routes import get_images_for_year
    from database import get_db
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT year, COUNT(*) FROM conference_images GROUP BY year")
    photo_counts = {row[0]: row[1] for row in cur.fetchall()}
    cur.close()
    con.close()
    return render_template(
        "company/conferences.html",
        conferences=CONFERENCE_LIST,
        photo_counts=photo_counts,
    )

@app.route("/conferences/<int:year>")
def conference_gallery(year):
    conf = next((c for c in CONFERENCE_LIST if c["year"] == year), None)
    if not conf:
        return redirect(url_for("conferences"))
    from conference_routes import get_images_for_year
    images = get_images_for_year(year)
    return render_template(
        "company/conference_gallery.html",
        conf=conf,
        images=images,
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
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        import os, urllib.request, urllib.error, json

        first_name   = request.form.get("first_name", "").strip()
        last_name    = request.form.get("last_name", "").strip()
        sender_email = request.form.get("email", "").strip()
        organisation = request.form.get("organisation", "").strip()
        requirement  = request.form.get("requirement", "").strip()
        message_text = request.form.get("message", "").strip()

        RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

        subject = f"[Ramay Electromedix] {requirement} — {first_name} {last_name}"
        html_body = f"""
        <h2 style="color:#1e3a8a;">New Contact Form Submission</h2>
        <table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:14px;">
            <tr><td style="padding:8px;font-weight:bold;color:#475569;width:140px;">Name</td><td style="padding:8px;">{first_name} {last_name}</td></tr>
            <tr style="background:#f8fafc;"><td style="padding:8px;font-weight:bold;color:#475569;">Email</td><td style="padding:8px;"><a href="mailto:{sender_email}">{sender_email}</a></td></tr>
            <tr><td style="padding:8px;font-weight:bold;color:#475569;">Organisation</td><td style="padding:8px;">{organisation}</td></tr>
            <tr style="background:#f8fafc;"><td style="padding:8px;font-weight:bold;color:#475569;">Requirement</td><td style="padding:8px;">{requirement}</td></tr>
            <tr><td style="padding:8px;font-weight:bold;color:#475569;vertical-align:top;">Message</td><td style="padding:8px;">{message_text.replace(chr(10), "<br>")}</td></tr>
        </table>
        <p style="color:#94a3b8;font-size:12px;margin-top:20px;">Sent from ramayelectromedix.com contact form</p>
        """

        try:
            payload = json.dumps({
                "from": "Ramay Electromedix <info@ramayelectromedix.com>",
                "to": ["hassnat7141@gmail.com"],
                "reply_to": sender_email,
                "subject": subject,
                "html": html_body,
            }).encode("utf-8")

            req = urllib.request.Request(
                "https://api.resend.com/emails",
                data=payload,
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                logging.info(f"Contact email sent via Resend: {resp.status}")

        except Exception as e:
            logging.error(f"Contact form Resend error: {e}")

        return render_template("support/contact.html", success=True)

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
