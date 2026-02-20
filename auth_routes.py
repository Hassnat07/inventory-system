# auth_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, session
from database import validate_user

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = validate_user(username, password)

        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            elif user["role"] == "team":
                return redirect(url_for("inventory.inventory_page"))
            else:
                return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid credentials")

    return render_template("login.html")



@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
