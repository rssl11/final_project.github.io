from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils import add_note, load_notes, update_note, soft_delete_note, load_users, restore_note, permanently_delete_note, update_user_profile
import time, random

main_bp = Blueprint("main", __name__)

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **kw):
        if "username" not in session:
            return redirect(url_for("auth.login"))
        return fn(*a, **kw)
    return wrapper

@main_bp.route("/")
def index():
    if "username" in session:
        return redirect(url_for("main.home"))
    return redirect(url_for("auth.login"))

@main_bp.route("/home", methods=("GET","POST"))
@login_required
def home():
    user = session["username"]
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","").strip()
        if not title:
            flash("title required", "error"); return redirect(url_for("main.home"))
        add_note(user, title, content)
        return redirect(url_for("main.home"))
    notes = [n for n in load_notes() if n["owner"] == user and n["status"] == "active"]
    return render_template("home.html", notes=sorted(notes, key=lambda x: x["updated_at"], reverse=True))

@main_bp.route("/note/edit/<int:note_id>", methods=("GET","POST"))
@login_required
def edit_note(note_id):
    user = session["username"]
    notes = load_notes()
    note = next((n for n in notes if n["id"]==note_id and n["owner"]==user), None)
    if not note:
        flash("note not found", "error"); return redirect(url_for("main.home"))
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","").strip()
        if not title:
            flash("title required", "error"); return render_template("edit_note.html", note=note)
        update_note(user, note_id, title, content)
        return redirect(url_for("main.home"))
    return render_template("edit_note.html", note=note)

@main_bp.route("/note/delete/<int:note_id>", methods=("POST",))
@login_required
def delete_note(note_id):
    user = session["username"]
    soft_delete_note(user, note_id)
    return redirect(url_for("main.home"))

@main_bp.route("/archive")
@login_required
def archive():
    user = session["username"]
    notes = [n for n in load_notes() if n["owner"]==user and n["status"]=="archived"]
    return render_template("archive.html", notes=sorted(notes, key=lambda x: x["updated_at"], reverse=True))

@main_bp.route("/archive/restore/<int:note_id>", methods=("POST",))
@login_required
def archive_restore(note_id):
    user = session["username"]
    restore_note(user, note_id)
    return redirect(url_for("main.archive"))

@main_bp.route("/archive/delete/<int:note_id>", methods=("POST",))
@login_required
def archive_delete(note_id):
    user = session["username"]
    permanently_delete_note(user, note_id)
    return redirect(url_for("main.archive"))

# Profile area
@main_bp.route("/profile", methods=("GET","POST"))
@login_required
def profile():
    user = session["username"]
    users = load_users()
    profile = users[user]["profile"]
    if request.method == "POST":
        # For profile updates require OTP verification flow similar to forgot password
        # Trigger OTP for profile update (displayed for demo). Real app: email/SMS.
        updated = {
            "first_name": request.form.get("first_name","").strip(),
            "middle_name": request.form.get("middle_name","").strip(),
            "last_name": request.form.get("last_name","").strip(),
            "dob": request.form.get("dob","").strip(),
            "contact": request.form.get("contact","").strip(),
            "address": request.form.get("address","").strip(),
            "email": request.form.get("email","").strip()
        }
        # store pending update in session and issue OTP
        otp = "%06d" % random.randint(0,999999)
        session["profile_update"] = {
            "username": user,
            "new_profile": updated,
            "otp": otp,
            "expires_at": time.time() + 180
        }
        flash(f"OTP for profile update (demo): {otp}", "info")
        return redirect(url_for("main.profile_verify"))
    return render_template("profile.html", profile=profile)

@main_bp.route("/profile/verify", methods=("GET","POST"))
@login_required
def profile_verify():
    info = session.get("profile_update")
    if not info or info.get("username") != session.get("username"):
        flash("no pending profile update", "error"); return redirect(url_for("main.profile"))
    if request.method == "POST":
        entered = request.form.get("otp","").strip()
        if time.time() > info["expires_at"]:
            session.pop("profile_update", None)
            flash("otp expired", "error"); return redirect(url_for("main.profile"))
        if entered != info["otp"]:
            flash("invalid otp", "error"); return render_template("otp_verify.html")
        update_user_profile(info["username"], info["new_profile"])
        session.pop("profile_update", None)
        flash("profile updated", "info")
        return redirect(url_for("main.profile"))
    return render_template("otp_verify.html")
