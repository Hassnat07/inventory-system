import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from database import get_db

conference_bp = Blueprint("conferences", __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static", "uploads", "conferences")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

CONFERENCE_YEARS = [
    {"year": 2024, "title": "Stallin Conference 2024", "location": "Lahore, Punjab"},
    {"year": 2025, "title": "Stallin Conference 2025", "location": "Lahore, Punjab"},
    {"year": 2026, "title": "Stallin Conference 2026", "location": "Peshawar, KPK"},
]


def _admin_required():
    user = g.get("user")
    return user and user.get("role") == "admin"


def _save_file(file):
    ext = file.filename.rsplit(".", 1)[1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return filename


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Public: fetch images for a given year (used by conferences page) ──
def get_images_for_year(year):
    con = get_db()
    cur = con.cursor()
    cur.execute(
        "SELECT id, image_filename, caption FROM conference_images WHERE year = %s ORDER BY sort_order, id",
        (year,)
    )
    rows = cur.fetchall()
    cur.close()
    con.close()
    return [{"id": r[0], "filename": r[1], "caption": r[2]} for r in rows]


# ── Admin panel ──
@conference_bp.route("/admin/conferences")
def admin_conferences():
    if not _admin_required():
        return redirect(url_for("auth.login"))

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT year, COUNT(*) FROM conference_images GROUP BY year")
    counts = {row[0]: row[1] for row in cur.fetchall()}

    images_by_year = {}
    for conf in CONFERENCE_YEARS:
        y = conf["year"]
        cur.execute(
            "SELECT id, image_filename, caption, sort_order FROM conference_images WHERE year = %s ORDER BY sort_order, id",
            (y,)
        )
        images_by_year[y] = [
            {"id": r[0], "filename": r[1], "caption": r[2], "sort_order": r[3]}
            for r in cur.fetchall()
        ]

    cur.close()
    con.close()

    return render_template(
        "admin/conferences_admin.html",
        conferences=CONFERENCE_YEARS,
        images_by_year=images_by_year,
        counts=counts,
    )


# ── Upload images for a year ──
@conference_bp.route("/admin/conferences/<int:year>/add-images", methods=["POST"])
def add_conference_images(year):
    if not _admin_required():
        return redirect(url_for("auth.login"))

    files = request.files.getlist("images")
    caption = request.form.get("caption", "").strip()

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT COALESCE(MAX(sort_order), -1) FROM conference_images WHERE year = %s", (year,))
    max_order = cur.fetchone()[0]

    saved = 0
    for f in files:
        if f and f.filename and _allowed(f.filename):
            filename = _save_file(f)
            max_order += 1
            cur.execute(
                "INSERT INTO conference_images (year, image_filename, caption, sort_order) VALUES (%s, %s, %s, %s)",
                (year, filename, caption or None, max_order)
            )
            saved += 1

    con.commit()
    cur.close()
    con.close()

    if saved:
        flash(f"{saved} image{'s' if saved > 1 else ''} uploaded to {year}.", "success")
    else:
        flash("No valid images were uploaded.", "error")

    return redirect(url_for("conferences.admin_conferences"))


# ── Delete a single image ──
@conference_bp.route("/admin/conferences/image/<int:image_id>/delete", methods=["POST"])
def delete_conference_image(image_id):
    if not _admin_required():
        return redirect(url_for("auth.login"))

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT image_filename FROM conference_images WHERE id = %s", (image_id,))
    row = cur.fetchone()

    if row:
        filepath = os.path.join(UPLOAD_FOLDER, row[0])
        if os.path.exists(filepath):
            os.remove(filepath)
        cur.execute("DELETE FROM conference_images WHERE id = %s", (image_id,))
        con.commit()
        flash("Image deleted.", "success")

    cur.close()
    con.close()
    return redirect(url_for("conferences.admin_conferences"))
