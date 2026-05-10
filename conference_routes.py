import os
import cloudinary
import cloudinary.uploader
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from database import get_db

conference_bp = Blueprint("conferences", __name__)

# ── Configure Cloudinary from environment variables ──
import cloudinary
cloudinary.config(True)  # Auto-reads CLOUDINARY_URL from environment

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

CONFERENCE_YEARS = [
    {"year": 2024, "title": "Stallin Conference 2024", "location": "Lahore, Punjab"},
    {"year": 2025, "title": "Stallin Conference 2025", "location": "Lahore, Punjab"},
    {"year": 2026, "title": "Stallin Conference 2026", "location": "Peshawar, KPK"},
]


def _admin_required():
    user = g.get("user")
    return user and user.get("role") == "admin"


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _save_file(file):
    try:
        result = cloudinary.uploader.upload(
            file,
            folder="conferences",        # organizes in Cloudinary
            resource_type="image",
            timeout=60                   # explicit timeout
        )
        return result["secure_url"]
    except Exception as e:
        raise RuntimeError(f"Cloudinary upload failed: {e}")


# ── Upload images for a year ──
@conference_bp.route("/admin/conferences/<int:year>/add-images", methods=["POST"])
def add_conference_images(year):
    if not _admin_required():
        return redirect(url_for("auth.login"))

    files = request.files.getlist("images")
    caption = request.form.get("caption", "").strip()

    con = get_db()
    cur = con.cursor()
    cur.execute(
        "SELECT COALESCE(MAX(sort_order), -1) FROM conference_images WHERE year = %s",
        (year,)
    )
    max_order = cur.fetchone()[0]

    saved = 0
    errors = 0
    for f in files:
        if f and f.filename and _allowed(f.filename):
            try:
                filename = _save_file(f)
                max_order += 1
                cur.execute(
                    "INSERT INTO conference_images (year, image_filename, caption, sort_order) VALUES (%s, %s, %s, %s)",
                    (year, filename, caption or None, max_order)
                )
                saved += 1
            except Exception as e:
                errors += 1
                flash(f"Failed to upload {f.filename}: {e}", "error")

    con.commit()
    cur.close()
    # Don't call con.close() if get_db() returns a pooled connection

    if saved:
        flash(f"{saved} image{'s' if saved > 1 else ''} uploaded to {year}.", "success")
    if errors:
        flash(f"{errors} file(s) failed to upload.", "error")
    if not saved and not errors:
        flash("No valid images were uploaded.", "error")

    return redirect(url_for("conferences.admin_conferences"))
