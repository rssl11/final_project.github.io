import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils import add_note, load_notes, update_note, soft_delete_note, load_users, restore_note, permanently_delete_note, update_user_profile,generate_otp,update_note_owner
import time, random
import re,datetime


main_bp = Blueprint("main", __name__)

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **kw):
        if "username" not in session:
            return redirect(url_for("auth_bp.login"))
        return fn(*a, **kw)
    return wrapper

@main_bp.route("/")
def index():
    if "username" in session:
        return redirect(url_for("main.home"))
    return redirect(url_for("auth_bp.login"))

@main_bp.route("/home", methods=("GET","POST"))
@login_required
def home():
    user = session["username"]
    if request.method == "POST":
        title = request.form.get("title","").strip()
        content = request.form.get("content","").strip()
        if not title:
            flash("Title is required!", "error")
            return redirect(url_for("main.home"))
        add_note(user, title, content)
        flash("Note added successfully!", "success")
        return redirect(url_for("main.home"))
    notes = [n for n in load_notes() if n["owner"] == user and n["status"] == "active"]
    return render_template("home.html", notes=sorted(notes, key=lambda x: x["updated_at"], reverse=True))

@main_bp.route("/note/edit/<int:note_id>", methods=("GET", "POST"))
@login_required
def edit_note(note_id):
    user = session["username"]
    notes = load_notes()
    note = next((n for n in notes if n["id"] == note_id and n["owner"] == user), None)

    if not note:
        flash("Note not found.", "error")
        return redirect(url_for("main.home"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title:
            flash("Title is required!", "error")
            return render_template("edit_note.html", note=note)

        # 🟡 Check if no changes were made
        if title == note["title"] and content == note["content"]:
            flash("No changes detected.", "warning")
            return redirect(url_for("main.edit_note", note_id=note_id))

        # ✅ Update note if there are changes
        update_note(user, note_id, title, content)
        flash("Note updated successfully!", "success")
        return redirect(url_for("main.home"))

    return render_template("edit_note.html", note=note)


@main_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    users = load_users()
    user_email = session["username"]
    user = next((u for u in users if u["email"] == user_email), None)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("main.profile"))

    if request.method == "POST":
        # Cancel button clicked
        if "cancel" in request.form:
            flash("Edit cancelled.", "info")
            return redirect(url_for("main.profile"))

        new_email = request.form.get("email", "").strip()
        if not new_email:
            flash("Email is required to generate OTP", "error")
            return render_template("edit_profile.html", user=user)

        # Save pending changes
        pending_profile = {
            "username": request.form.get("username","").strip(),
            "firstname": request.form.get("firstname","").strip(),
            "middlename": request.form.get("middlename","").strip(),
            "lastname": request.form.get("lastname","").strip(),
            "province": request.form.get("province","").strip(),
            "city": request.form.get("city","").strip(),
            "barangay": request.form.get("barangay","").strip(),
            "zip_code": request.form.get("zip_code","").strip(),
            "birthday": request.form.get("birthday","").strip(),
            "email": new_email,
            "contact": request.form.get("contact","").strip(),
            "password": user["password"]
        }
        session['pending_profile'] = pending_profile

        # Generate OTP
        otp = generate_otp()
        session['profile_otp'] = otp
        session['profile_otp_time'] = time.time()
        flash("OTP generated. Please enter it to edit your profile.", "info")
        return redirect(url_for("main.profile_otp_verify"))

    # GET request - display editable profile
    return render_template("edit_profile.html", user=user)


@main_bp.route("/note/delete/<int:note_id>", methods=("POST",))
@login_required
def delete_note(note_id):
    user = session["username"]
    soft_delete_note(user, note_id)
    flash("Note archived successfully!", "info")
    return redirect(url_for("main.home"))

@main_bp.route("/archive")
@login_required
def archive():
    user = session["username"]
    notes = [n for n in load_notes() if n["owner"] == user and n["status"] == "archived"]
    return render_template(
        "archive.html",
        notes=sorted(notes, key=lambda x: x["updated_at"], reverse=True),
        user=user
    )

@main_bp.route("/archive/restore/<int:note_id>", methods=("POST",))
@login_required
def archive_restore(note_id):
    user = session["username"]
    restore_note(user, note_id)
    flash("Note restored successfully!", "success")
    return redirect(url_for("main.archive"))


@main_bp.route("/archive/delete/<int:note_id>", methods=("POST",))
@login_required
def archive_delete(note_id):
    user = session["username"]
    permanently_delete_note(user, note_id)
    flash("Note deleted permanently!", "error")
    return redirect(url_for("main.archive"))

# main.py (Updated @main_bp.route("/profile", ...) function)
@main_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    users = load_users()
    user_email = session["username"]

    user = next((u for u in users if u["email"] == user_email), None)
    if not user:
        flash("User not found.", "error")
        return redirect(url_for("main.home"))

    if request.method == "POST":
        
        # Collect updated data and initialize error tracking
        new_email = request.form.get("email", "").strip() 
        errors = {}
        NAME_REGEX = r'^[A-Z][a-zA-Z\s]*$'
        
        updated_profile = {
            "username": request.form.get("username", "").strip(),
            "firstname": request.form.get("firstname", "").strip(),
            "middlename": request.form.get("middlename", "").strip(),
            "lastname": request.form.get("lastname", "").strip(),
            "province": request.form.get("province", "").strip(),
            "city": request.form.get("city", "").strip(),
            "barangay": request.form.get("barangay", "").strip(),
            "contact": request.form.get("contact", "").strip(),
            "birthday": request.form.get("birthday", "").strip(),
            "age": request.form.get("age", "").strip(),
            "zip_code": request.form.get("zip_code", "").strip(),
            "email": new_email, 
            "password": user["password"]
        }

        # --- CRITICAL FIX: Explicit Checks for Empty Required Fields ---
        if not updated_profile['username']:
            errors['username'] = 'Username is required.'
        if not updated_profile['firstname']:
            errors['firstname'] = 'First name is required.'
        if not updated_profile['lastname']:
            errors['lastname'] = 'Last name is required.'
        if not updated_profile['contact']:
            errors['contact'] = 'Contact number is required.'
        if not updated_profile['birthday']:
            errors['birthday'] = 'Birth date is required.'
        if not updated_profile['email']:
            errors['email'] = 'Email is required.'
        # ---------------------------------------------------------------
        
        # --- Existing Validation Checks (Modified to respect 'is required' errors) ---
        
        # 1. Name Validation (First Name)
        if 'firstname' not in errors and not re.match(NAME_REGEX, updated_profile['firstname']):
            errors['firstname'] = 'Invalid format (Must start with capital letter, letters/spaces only).'
        
        # 2. Name Validation (Middle Name - Optional but must be valid if present)
        if updated_profile['middlename'] and not re.match(NAME_REGEX, updated_profile['middlename']):
            errors['middlename'] = 'Invalid format (Must start with capital letter, letters/spaces only).'
        
        # 3. Name Validation (Last Name)
        if 'lastname' not in errors and not re.match(NAME_REGEX, updated_profile['lastname']):
            errors['lastname'] = 'Invalid last name (Must start with capital letter, letters/spaces only).'

        # 4. Contact Number Validation
        new_contact = updated_profile['contact']
        
        # Check 1: Format
        if 'contact' not in errors and not re.match(r'^09\d{9}$', new_contact):
            errors['contact'] = 'Invalid contact number (Must start with 09 and have 11 digits).'
        # Check 2: Repeating Digits
        elif 'contact' not in errors and re.match(r'^09(\d)\1{8}$', new_contact):
            errors['contact'] = 'Contact number digits cannot all be the same.'
        # ✅ FIX: Check 3: Uniqueness (only against other users)
        elif 'contact' not in errors and any(u.get('contact') == new_contact for u in users if u.get('email') != user_email):
            errors['contact'] = 'Contact number is already in use by another account.'
        
        # 5. Location Validation
        if not updated_profile['province']:
             errors['province'] = 'Province is required.'
        if not updated_profile['city']:
             errors['city'] = 'City is required.'

        # 6. Birthday/Age Validation
        if 'birthday' not in errors and updated_profile['birthday']:
            try:
                birth_date = datetime.datetime.strptime(updated_profile['birthday'], "%Y-%m-%d")
                age = (datetime.datetime.now() - birth_date).days // 365
                
                updated_profile['age'] = str(age)
                if age < 18:
                    errors['birthday'] = "You must be at least 18 years old to update your profile."
            except (ValueError, TypeError):
                 errors['birthday'] = "Invalid or missing birth date."
        
        # 7. Email Check (If email changed, check for existing user)
        if 'email' not in errors and updated_profile['email']:
            email_changed = new_email != user_email
            if email_changed and any(u.get('email') == new_email for u in users if u.get('email') != user_email):
                errors['email'] = f"Email address {new_email} is already in use."

        # 🛑 Process Errors
        if errors:
            
            return render_template(
                "profile.html", 
                user=updated_profile, 
                user_province=updated_profile['province'],
                user_city=updated_profile['city'],
                user_barangay=updated_profile['barangay'],
                user_zip_code=updated_profile['zip_code'],
                errors=errors
            )

        # 8. Check for no changes (Only run if validation passed)
        keys_to_check = ["username", "firstname", "middlename", "lastname", 
                         "province", "city", "barangay", "contact", "birthday", "age", "zip_code", "email"]
        
        has_changes = any(
            str(user.get(key, "")) != str(updated_profile.get(key, ""))
            for key in keys_to_check
        )

        if not has_changes:
            flash("No changes detected. Profile not saved.", "warning")
            return redirect(url_for("main.profile"))

        # 🟢 If changes exist, proceed to OTP verification flow
        # ... (rest of OTP generation logic remains here) ...
        
        session['pending_profile'] = updated_profile
        
        profile_otp = session.get('profile_otp')
        profile_otp_time = session.get('profile_otp_time')
        now = time.time()
        
        if profile_otp and profile_otp_time and (now - profile_otp_time) < 60:
            otp = profile_otp
        else:
            otp = generate_otp()
            session['profile_otp'] = otp
            session['profile_otp_time'] = now
            
        flash("An OTP is required to confirm changes. Please enter it below.", "info")
        return redirect(url_for("main.profile_otp_verify"))

    # For displaying saved data in HTML dropdowns and inputs (GET request)
    user_province = user.get("province", "")
    user_city = user.get("city", "")
    user_barangay = user.get("barangay", "")
    user_zip_code = user.get("zip_code", "")

    return render_template(
        "profile.html",
        user=user,
        user_province=user_province,
        user_city=user_city,
        user_barangay=user_barangay,
        user_zip_code=user_zip_code,
        errors={}
    )


# main.py

# NOTE: Ensure 'update_note_owner' is imported from utils at the top of main.py
# Example: from utils import ..., update_user_profile, generate_otp, update_note_owner

@main_bp.route("/profile/otp_verify", methods=["GET", "POST"])
@login_required
def profile_otp_verify():
    # Timer variables (60 seconds)
    remaining = 0
    otp_time = session.get("profile_otp_time")
    
    if otp_time:
        elapsed = time.time() - otp_time
        remaining = max(0, 60 - int(elapsed))
    
    # ---------------- POST Request Logic ----------------
    if request.method == "POST":
        entered_otp = request.form.get("otp", "").strip()
        stored_otp = session.get("profile_otp")
        pending_data = session.get("pending_profile")
        old_email = session.get("username") # Get the OLD email address

        if not stored_otp or not otp_time or not pending_data:
            flash("Session expired. Please try updating again.", "error")
            return redirect(url_for("main.profile"))

        # Check for Expiration (60 seconds)
        if remaining <= 0:
            flash("OTP expired. Please generate a new one.", "error")
            session.pop("profile_otp", None)
            session.pop("profile_otp_time", None)
            return redirect(url_for("main.profile"))

        # Invalid OTP Check
        if entered_otp != stored_otp:
            flash("Invalid OTP. Please try again.", "error")
            return render_template("profile_otp_verify.html", otp_time=remaining)

        # OTP verified — apply pending updates
        
        # Get the new email from the pending data
        new_email = pending_data.get('email')

        # 1. Update the user profile in users.json
        # user_email here is the OLD email address (from the session before update)
        update_user_profile(old_email, pending_data) 

        # ------------------- ✅ FIX: Update Notes Ownership -------------------
        if new_email != old_email:
            # Transfer ownership of all notes from the old email to the new email
            # NOTE: This requires the 'update_note_owner' function to be in utils.py
            update_note_owner(old_email, new_email) 
            
            # CRITICAL: Update the session variable to the NEW email
            session['username'] = new_email 
        # ---------------------------------------------------------------------

        # Clear temporary session data
        session.pop("profile_otp", None)
        session.pop("profile_otp_time", None)
        session.pop("pending_profile", None)

        flash("Profile updated successfully.", "success")
        return redirect(url_for("main.profile"))

    # ---------------- GET Request Logic ----------------
    return render_template("profile_otp_verify.html", otp_time=remaining)