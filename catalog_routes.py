import os
import cloudinary
import cloudinary.uploader
from flask import Blueprint, render_template, request, redirect, url_for, g, flash, jsonify
from database import get_db

catalog_bp = Blueprint("catalog", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

CATEGORIES = [
    "Intraocular Lenses",
    "Eye Machines",
    "Eye Gel",
]


def _allowed(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _admin_required():
    user = g.get("user")
    return user and user.get("role") == "admin"


def _save_file(file):
    result = cloudinary.uploader.upload(file)
    return result["secure_url"]


def _img_url(filename):
    """Return usable URL — Cloudinary or local static fallback."""
    if filename and (filename.startswith("http://") or filename.startswith("https://")):
        return filename
    return url_for("static", filename=f"uploads/catalog/{filename}")


# ── Public catalog list ─────────────────────────────────────────────────────
@catalog_bp.route("/catalog")
def catalog():
    con = get_db()
    cur = con.cursor()
    # Add sort_order column if missing (safe migration)
    cur.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='catalog_items' AND column_name='sort_order'
            ) THEN
                ALTER TABLE catalog_items ADD COLUMN sort_order INTEGER DEFAULT 0;
                UPDATE catalog_items SET sort_order = id;
            END IF;
        END $$
    """)
    con.commit()

    cur.execute("""
        SELECT id, name, category, description, model_no, image_filename
        FROM catalog_items
        ORDER BY category, sort_order ASC, id ASC
    """)
    rows = cur.fetchall()
    cur.close()
    con.close()

    grouped = {}
    for row in rows:
        cat = row[2]
        grouped.setdefault(cat, []).append({
            "id": row[0], "name": row[1], "category": row[2],
            "description": row[3], "model_no": row[4], "image_filename": row[5],
        })

    cat_filter = request.args.get("cat", "").strip()
    CAT_MAP = {"iols": "Intraocular Lenses", "eye-machines": "Eye Machines", "eye-gel": "Eye Gel"}
    active_cat = CAT_MAP.get(cat_filter, "")

    return render_template("catalog.html", grouped=grouped, categories=CATEGORIES, active_cat=active_cat)


# ── Public catalog detail ───────────────────────────────────────────────────
@catalog_bp.route("/catalog/<int:item_id>")
def catalog_detail(item_id):
    con = get_db()
    cur = con.cursor()
    cur.execute("""
        SELECT id, name, category, description, model_no, image_filename
        FROM catalog_items WHERE id = %s
    """, (item_id,))
    row = cur.fetchone()
    if not row:
        cur.close(); con.close()
        return redirect(url_for("catalog.catalog"))

    item = {
        "id": row[0], "name": row[1], "category": row[2],
        "description": row[3], "model_no": row[4], "image_filename": row[5],
    }
    cur.execute("""
        SELECT image_filename FROM catalog_item_images
        WHERE item_id = %s ORDER BY sort_order, id
    """, (item_id,))
    extra_rows = [r[0] for r in cur.fetchall()]
    cur.close(); con.close()

    all_images = [item["image_filename"]]
    for fn in extra_rows:
        if fn not in all_images:
            all_images.append(fn)

    return render_template("catalog_detail.html", item=item, all_images=all_images)


# ── Admin: catalog manager ──────────────────────────────────────────────────
@catalog_bp.route("/admin/catalog")
def catalog_admin():
    if not _admin_required():
        return redirect(url_for("auth.login"))

    con = get_db()
    cur = con.cursor()

    # Ensure sort_order column exists
    cur.execute("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name='catalog_items' AND column_name='sort_order'
            ) THEN
                ALTER TABLE catalog_items ADD COLUMN sort_order INTEGER DEFAULT 0;
                UPDATE catalog_items SET sort_order = id;
            END IF;
        END $$
    """)
    con.commit()

    cur.execute("""
        SELECT id, name, category, description, model_no, image_filename, created_at
        FROM catalog_items ORDER BY category, sort_order ASC, id ASC
    """)
    items_raw = cur.fetchall()

    cur.execute("SELECT item_id, COUNT(*) FROM catalog_item_images GROUP BY item_id")
    img_counts = {r[0]: r[1] for r in cur.fetchall()}
    cur.close(); con.close()

    items = [
        {
            "id": r[0], "name": r[1], "category": r[2],
            "description": r[3], "model_no": r[4],
            "image_filename": r[5], "created_at": r[6],
            "extra_image_count": img_counts.get(r[0], 0),
        }
        for r in items_raw
    ]

    return render_template("admin/catalog_admin.html", items=items, categories=CATEGORIES)


# ── Admin: reorder products (AJAX) ──────────────────────────────────────────
@catalog_bp.route("/admin/catalog/reorder", methods=["POST"])
def catalog_reorder():
    if not _admin_required():
        return jsonify({"error": "Unauthorized"}), 403

    data = request.get_json()
    ordered_ids = data.get("ids", [])  # list of item IDs in new order

    if not ordered_ids:
        return jsonify({"error": "No IDs provided"}), 400

    con = get_db()
    cur = con.cursor()
    for position, item_id in enumerate(ordered_ids):
        cur.execute(
            "UPDATE catalog_items SET sort_order = %s WHERE id = %s",
            (position, item_id)
        )
    con.commit()
    cur.close(); con.close()

    return jsonify({"success": True, "saved": len(ordered_ids)})


# ── Admin: add new product ───────────────────────────────────────────────────
@catalog_bp.route("/admin/catalog/add", methods=["POST"])
def catalog_add():
    if not _admin_required():
        return redirect(url_for("auth.login"))

    name        = request.form.get("name", "").strip()
    category    = request.form.get("category", "").strip()
    description = request.form.get("description", "").strip()
    model_no    = request.form.get("model_no", "").strip()
    files       = request.files.getlist("images")
    valid_files = [f for f in files if f and f.filename]

    if not name or not category or not valid_files:
        flash("Name, category and at least one image are required.", "error")
        return redirect(url_for("catalog.catalog_admin"))

    for f in valid_files:
        if not _allowed(f.filename):
            flash(f'"{f.filename}" is not an allowed image type.', "error")
            return redirect(url_for("catalog.catalog_admin"))

    cover_filename = _save_file(valid_files[0])

    con = get_db()
    cur = con.cursor()

    # New item gets sort_order = current max + 1 (appended at end)
    cur.execute("SELECT COALESCE(MAX(sort_order), -1) FROM catalog_items WHERE category = %s", (category,))
    max_order = cur.fetchone()[0]

    cur.execute("""
        INSERT INTO catalog_items (name, category, description, model_no, image_filename, sort_order)
        VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
    """, (name, category, description or None, model_no or None, cover_filename, max_order + 1))
    item_id = cur.fetchone()[0]

    for i, f in enumerate(valid_files):
        filename = cover_filename if i == 0 else _save_file(f)
        cur.execute("""
            INSERT INTO catalog_item_images (item_id, image_filename, sort_order)
            VALUES (%s, %s, %s)
        """, (item_id, filename, i))

    con.commit()
    cur.close(); con.close()

    count = len(valid_files)
    flash(f'"{name}" added with {count} image{"s" if count > 1 else ""}.', "success")
    return redirect(url_for("catalog.catalog_admin"))


# ── Admin: add more images to existing product ──────────────────────────────
@catalog_bp.route("/admin/catalog/<int:item_id>/add-images", methods=["POST"])
def catalog_add_images(item_id):
    if not _admin_required():
        return redirect(url_for("auth.login"))

    files = request.files.getlist("images")
    valid_files = [f for f in files if f and f.filename]

    if not valid_files:
        flash("Please select at least one image.", "error")
        return redirect(url_for("catalog.catalog_admin"))

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT COALESCE(MAX(sort_order), -1) FROM catalog_item_images WHERE item_id = %s", (item_id,))
    next_order = cur.fetchone()[0] + 1

    for i, f in enumerate(valid_files):
        if not _allowed(f.filename): continue
        filename = _save_file(f)
        cur.execute("""
            INSERT INTO catalog_item_images (item_id, image_filename, sort_order)
            VALUES (%s, %s, %s)
        """, (item_id, filename, next_order + i))

    con.commit()
    cur.close(); con.close()
    flash(f"{len(valid_files)} image(s) added.", "success")
    return redirect(url_for("catalog.catalog_admin"))


# ── Admin: delete a single image ────────────────────────────────────────────
@catalog_bp.route("/admin/catalog/image/<int:image_id>/delete", methods=["POST"])
def catalog_delete_image(image_id):
    if not _admin_required():
        return redirect(url_for("auth.login"))

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT image_filename, item_id FROM catalog_item_images WHERE id = %s", (image_id,))
    row = cur.fetchone()
    if row:
        try:
            public_id = row[0].split("/")[-1].split(".")[0]
            cloudinary.uploader.destroy(public_id)
        except Exception:
            pass
        cur.execute("DELETE FROM catalog_item_images WHERE id = %s", (image_id,))
        con.commit()
    cur.close(); con.close()
    flash("Image removed.", "success")
    return redirect(url_for("catalog.catalog_admin"))


# ── Admin: delete entire product ─────────────────────────────────────────────
@catalog_bp.route("/admin/catalog/delete/<int:item_id>", methods=["POST"])
def catalog_delete(item_id):
    if not _admin_required():
        return redirect(url_for("auth.login"))

    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT image_filename FROM catalog_item_images WHERE item_id = %s", (item_id,))
    for (fn,) in cur.fetchall():
        try: cloudinary.uploader.destroy(fn.split("/")[-1].split(".")[0])
        except Exception: pass

    cur.execute("SELECT image_filename FROM catalog_items WHERE id = %s", (item_id,))
    row = cur.fetchone()
    if row:
        try: cloudinary.uploader.destroy(row[0].split("/")[-1].split(".")[0])
        except Exception: pass
        cur.execute("DELETE FROM catalog_items WHERE id = %s", (item_id,))
        con.commit()

    cur.close(); con.close()
    flash("Product deleted.", "success")
    return redirect(url_for("catalog.catalog_admin"))
