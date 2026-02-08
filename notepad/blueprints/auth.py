from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from utils import load_json, save_json, hash_password, verify_password, generate_otp
import datetime
import os
import time
import re

from utils import load_json as load_data, save_json as save_data

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERS_FILE = os.path.join(BASE_DIR, "data", "users.json")
NOTES_FILE = os.path.join(BASE_DIR, "data", "notes.json")

auth_bp = Blueprint('auth_bp', __name__, template_folder='../templates')


# ---------------- Register ----------------
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = load_data(USERS_FILE)
        errors = {}

        form_data = {
            'username': request.form.get('username', '').strip(),
            'firstname': request.form.get('firstname', '').strip(),
            'middlename': request.form.get('middlename', '').strip(),
            'lastname': request.form.get('lastname', '').strip(),
            'province': request.form.get('province', '').strip(),
            'city': request.form.get('city', '').strip(),
            'barangay': request.form.get('barangay', '').strip(),
            'contact': request.form.get('contact', '').strip(),
            'birthday': request.form.get('birthday', '').strip(),
            'email': request.form.get('email', '').strip(),
            'password': request.form.get('password', '').strip(),
            'confirm_password': request.form.get('confirm_password', '').strip(),
            'age': request.form.get('age', '').strip(),
            'zip_code': request.form.get('zip_code', '').strip()
        }

        # --- Validation Checks (Collect Errors in the dictionary) ---
        
        # 1. Username validation
        if not form_data['username']:
            errors['username'] = 'Username is required.'
        elif re.match(r'^([A-Za-z])\1{2,}$', form_data['username']):
            errors['username'] = 'Username cannot be made of repeating letters.'
        elif not re.match(r'^[a-zA-Z][a-zA-Z0-9._]*$', form_data['username']):
            errors['username'] = 'Invalid username format.'
        elif len(form_data['username'].replace(' ', '')) < 2:
            errors['username'] = 'Username must be at least 2 characters long.'
        elif any(u.get('username') == form_data['username'] for u in data):
            errors['username'] = 'Username already exists.'
        
        
        # 2. First name validation
        if not re.match(r'^[A-Z][a-zA-Z\s]*$', form_data['firstname']):
            errors['firstname'] = 'Invalid first name (must start with capital letter, letters/spaces only).'
        elif len(form_data['firstname'].replace(' ', '')) < 3:
            errors['firstname'] = 'First name must be at least 3 characters long.'
        elif re.match(r'^([A-Za-z])\1{2,}$', form_data['firstname']):
            errors['firstname'] = 'First name cannot be made of repeating letters.'

        # 3. Middle name (optional)
        if form_data['middlename']:
            if not re.match(r'^[A-Z][a-zA-Z\s]*$', form_data['middlename']):
                errors['middlename'] = 'Middle name must start with a capital letter and contain only letters and spaces.'
            elif re.match(r'^([A-Za-z])\1{2,}$', form_data['middlename']):
                errors['middlename'] = 'Middle name cannot be made of repeating letters.'

        # 4. Last name
        if not re.match(r'^[A-Z][a-zA-Z\s]*$', form_data['lastname']):
            errors['lastname'] = 'Invalid last name (must start with capital letter, letters/spaces only).'
        elif len(form_data['lastname'].replace(' ', '')) < 3:
            errors['lastname'] = 'Last name must be at least 3 characters long.'
        elif re.match(r'^([A-Za-z])\1{2,}$', form_data['lastname']):
            errors['lastname'] = 'Last name cannot be made of repeating letters.'

        # 5. Contact number validation
        if not re.match(r'^09\d{9}$', form_data['contact']):
            errors['contact'] = 'Invalid contact number (must start with 09 and have 11 digits).'
        elif re.match(r'^09(\d)\1{8}$', form_data['contact']):
            errors['contact'] = 'Contact number digits cannot all be the same.'
        # ✅ FIX: Check for contact number uniqueness
        elif any(u.get('contact') == form_data['contact'] for u in data):
             errors['contact'] = 'Contact number is already in use.'


        # 6. Email validation
        ALLOWED_DOMAINS_PATTERN = r'(com|net|org|edu|gov|ph|co\.ph|edu\.ph|org\.ph|gmail\.com|yahoo\.com|outlook\.com|lu\.edu\.ph)'
        EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.' + ALLOWED_DOMAINS_PATTERN + r'$'
        if not re.match(EMAIL_REGEX, form_data['email']):
            errors['email'] = 'Invalid email address.'
        elif any(u.get('email') == form_data['email'] for u in data):
            errors['email'] = 'Email already exists.'

        # 7. Location validation (Province & City required)
        if not form_data['province']:
             errors['province'] = 'Province is required.'
        if not form_data['city']:
             errors['city'] = 'City is required.'
        
        # 8. Password confirmation check (use 'password' for field-level error)
        if form_data['password'] != form_data['confirm_password']:
            errors['password'] = 'Passwords do not match.'
        elif len(form_data['password']) < 8:
             errors['password'] = 'Password must be at least 8 characters long.'
        
        # 9. Age validation
        try:
            birth_date = datetime.datetime.strptime(form_data['birthday'], "%Y-%m-%d")
            age = (datetime.datetime.now() - birth_date).days // 365
            if age < 18:
                errors['birthday'] = "You must be at least 18 years old to register."
        except (ValueError, TypeError):
             errors['birthday'] = "Invalid or missing birth date."

        
        # --- Process Errors ---
        if errors:
            flash('Please fix the errors below.', 'error')
            return render_template('register.html', form=form_data, errors=errors)


        # --- Success ---
        hashed_password = hash_password(form_data['password'])
        final_user_data = {**form_data, 'password': hashed_password}
        data.append(final_user_data)
        save_data(USERS_FILE, data)
        flash('Registration successful.', 'success')
        return redirect(url_for('auth_bp.login'))
        
    return render_template('register.html', errors={})


# ---------------- Login ----------------
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    data = load_json(USERS_FILE)

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '').strip()
        
        errors = {}

        if not email:
            errors['email'] = 'Email is required.'
        if not password:
            errors['password'] = 'Password is required.'
        
        # 1. If fields are missing, re-render with the errors
        if errors:
            return render_template(
                'login.html', 
                errors=errors, 
                entered_email=email, 
                entered_password=password
            )
            
        # 2. Authenticate using HASHED password
        user = next((u for u in data if u['email'] == email), None)
        
        if user and verify_password(password, user['password']):
            session['username'] = user['email']
            flash('Login successful.', "success")
            return redirect(url_for('main.home'))
        else:
            flash('Invalid email or password.', "error") 
            
            return render_template(
                'login.html', 
                errors={}, 
                entered_email=email, 
                entered_password=password
            ) 

    return render_template('login.html', errors={})

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('auth_bp.login'))

@auth_bp.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form.get('username', '').strip()
        data = load_json(USERS_FILE)

        errors = {}
        
        # 1. Validation for required email field
        if not email:
            errors['email'] = 'Email is required.' 
        
        # 2. Process field errors
        if errors:
             return render_template('forgot.html', errors=errors, entered_email=email)

        # 3. Check if email exists
        user = next((u for u in data if u['email'] == email), None)
        
        # FIX: Display "Email not found" as a field-level error
        if not user:
            errors['email'] = 'Email not found.'
            return render_template('forgot.html', errors=errors, entered_email=email)

        # Load existing OTP data from session
        otp_data = session.get('otp_data', {})
        now = time.time()

        # Check if existing OTP for this email is still valid
        if email in otp_data and now < otp_data[email]['expires_at']:
            otp = otp_data[email]['otp']
        else:
            otp = generate_otp()
            otp_data[email] = {
                'otp': otp,
                'expires_at': now + 60
            }
            session['otp_data'] = otp_data

        # Save references for verification
        session['reset_email'] = email
        session['reset_otp'] = otp
        session['otp_timestamp'] = otp_data[email]['expires_at'] - 60

        return redirect(url_for('auth_bp.otp_verify'))

    return render_template('forgot.html', errors={})

@auth_bp.route('/otp_verify', methods=['GET', 'POST'])
def otp_verify():
    if request.method == 'POST':
        entered_otp = request.form.get('otp', '').strip()

        # Retrieve OTP session data
        stored_otp = session.get('reset_otp')
        email = session.get('reset_email')
        otp_time = session.get('otp_timestamp')
        
        # Calculate remaining time for re-rendering if OTP is invalid
        remaining = 0
        if otp_time:
            elapsed = time.time() - otp_time
            remaining = max(0, 60 - int(elapsed))

        # --- 1. Validate session existence ---
        if not stored_otp or not email or not otp_time:
            flash("Session expired. Please request a new OTP.", "error")
            return redirect(url_for('auth_bp.forgot'))

        # --- 2. Check for Expiration
        if remaining <= 0:
            flash("OTP expired. Please generate a new one.", "error")
            return redirect(url_for('auth_bp.forgot'))

        # --- 3. Verify entered OTP ---
        if entered_otp != stored_otp:
            # ✅ FIX: Pass the error message to the template context instead of flashing
            error_message = "Invalid OTP. Please try again."
            
            return render_template(
                'otp_verify.html', 
                otp_time=remaining, 
                entered_otp=entered_otp,
                otp_error=error_message # Pass the specific error text
            )

        # --- 4. OTP is correct ---
        flash("OTP verified successfully. You may now reset your password.", "success")
        return redirect(url_for('auth_bp.reset_password'))
    
    # --- For GET request: calculate remaining time for OTP timer ---
    if 'otp_timestamp' in session:
        elapsed = time.time() - session['otp_timestamp']
        remaining = max(0, 60 - int(elapsed))
    else:
        remaining = 0

    return render_template('otp_verify.html', otp_time=remaining)

@auth_bp.route('/resend_otp', methods=['POST'])
def resend_otp():
    email = session.get('reset_email')
    
    # 1. Check for expired session email
    if not email:
        flash("Session expired. Please re-enter your email.")
        return redirect(url_for('auth_bp.forgot'))

    data = load_json(USERS_FILE)
    user = next((u for u in data if u['email'] == email), None)
    
    # 2. FIX: Display "Email not found" as a field-level error on the /forgot page
    if not user:
        # NOTE: This requires rendering the forgot.html template and passing the error
        errors = {'email': 'Email not found.'}
        flash('Session expired, please re-enter your email.', 'error') # Flash general error
        return redirect(url_for('auth_bp.forgot')) # Redirect to restart the process and show the flash message

    # 3. Generate new OTP if user is found
    otp = generate_otp()
    session['reset_otp'] = otp
    session['otp_timestamp'] = time.time()

    flash("New OTP Generated")
    return redirect(url_for('auth_bp.otp_verify'))

@auth_bp.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        pw = request.form.get('password').strip()
        confirm_pw = request.form.get('confirm_password').strip()
        email = session.get('reset_email')
        
        # 1. Check if passwords match (Existing check)
        if pw != confirm_pw:
            flash("Passwords don't match.", "error")
            return redirect(url_for('auth_bp.reset_password'))
        
        # Password length check
        if len(pw) < 8:
            flash("Password must be at least 8 characters long.", "error")
            return redirect(url_for('auth_bp.reset_password'))

        # 2. Check session integrity
        if not email:
            flash("Session expired. Please try again.", "error")
            return redirect(url_for('auth_bp.forgot'))

        data = load_json(USERS_FILE)
        
        # 3. Find user and perform password comparison
        user_found = False
        for user in data:
            if user['email'] == email:
                user_found = True
                
                # Check new password against current HASHED password
                current_password_hash = user.get('password') 
                
                if verify_password(pw, current_password_hash):
                    flash("The new password cannot be the same as your current password.", "warning")
                    return redirect(url_for('auth_bp.reset_password'))
                
                # Update password with the new hash
                user['password'] = hash_password(pw)
                break
        
        if not user_found:
            flash("User not found.", "error")
            return redirect(url_for('auth_bp.forgot'))

        save_json(USERS_FILE, data)

        # Clear session data
        session.pop('reset_otp', None)
        session.pop('reset_email', None)
        session.pop('otp_timestamp', None)

        flash("Password reset successful. Please log in.", "success")
        return redirect(url_for('auth_bp.login'))

    return render_template('reset_password.html')

@auth_bp.route('/resend_profile_otp', methods=['POST'])
def resend_profile_otp():
    email = session.get('username')
    if not email:
        flash("Session expired. Please log in again.", "error")
        return redirect(url_for('auth_bp.login'))
    
    # Check if there's pending profile data to update
    if 'pending_profile' not in session:
        flash("No pending profile changes to verify. Please try updating again.", "warning")
        return redirect(url_for('main.profile'))

    # Generate new OTP
    otp = generate_otp()
    session['profile_otp'] = otp
    session['profile_otp_time'] = time.time()

    flash("A new OTP has been generated.", "info")
    return redirect(url_for('main.profile_otp_verify'))