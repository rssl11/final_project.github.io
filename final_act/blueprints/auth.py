from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
import bcrypt
import random
import smtplib
import re
import time
import os
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from db_config import get_db_connection

auth_bp = Blueprint('auth_bp', __name__)

# --- SMTP CONFIGURATION (REQUIRED) ---
display_name = "hahaha"
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_EMAIL = 'authallica@gmail.com' 
SMTP_PASSWORD = 'bnwx alzi gteh qdgo' 

# --- NEW: CACHE BUSTER (Prevents Back Button Issues) ---
@auth_bp.after_request
def add_header(response):
    """
    Tells the browser NOT to save the page in history/cache.
    This ensures that clicking 'Back' forces a reload, checking session status again.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# --- NEW: Load User into 'g' Global Object ---
@auth_bp.before_app_request
def load_logged_in_user():
    user_id = session.get('user_id')

    if user_id is None:
        g.user = None
    else:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        
        if user_data and user_data.get('status') == 'blocked':
            session.clear()
            g.user = None
        else:
            g.user = user_data
            
        conn.close()

# --- Helper: Send OTP via SMTP ---
def send_email_otp(to_email):
    otp = str(random.randint(100000, 999999))
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = to_email
        msg['Subject'] = "Your Verification OTP"

        body = f"""
        <h3>Verification Required</h3>
        <p>Your One-Time Password (OTP) is:</p>
        <h2 style="color: #2c3e50;">{otp}</h2>
        <p>Do not share this code with anyone.</p>
        <p>This code expires in 3 minutes.</p>
        """
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return otp
    except Exception as e:
        print(f"SMTP ERROR: {e}")
        return None

# --- Helper: Log System Event ---
def log_system_event(user_id, username, role, action_type):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        sql = """
            INSERT INTO system_logs (user_id, username, role, action_type) 
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (user_id, username, role, action_type))
        
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"LOGGING ERROR: {e}")

# --- NEW: Form Validation Function ---
def validate_form_data(form_data, check_password=True):
    errors = {}
    
    # 1. Name Validation (First letter capital)
    if 'firstname' in form_data:
        fname = form_data['firstname'].strip()
        if not fname:
            errors['firstname'] = "First name is required."
        elif not fname[0].isupper():
            errors['firstname'] = "First name must start with a capital letter."
            
    if 'lastname' in form_data:
        lname = form_data['lastname'].strip()
        if not lname:
            errors['lastname'] = "Last name is required."
        elif not lname[0].isupper():
            errors['lastname'] = "Last name must start with a capital letter."

    # 2. Email Validation (Regex + Blocked Domains)
    if 'email' in form_data:
        email = form_data['email'].strip()
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not email:
            errors['email'] = "Email is required."
        elif not re.match(email_pattern, email):
            errors['email'] = "Invalid email format."
        else:
            # Domain check
            try:
                domain = email.split('@')[1]
                blocked_domains = ['gmail.co', 'gmailcom', 'patatas.com', 'yahoo.co']
                if domain in blocked_domains:
                    errors['email'] = f"The domain '{domain}' is not accepted."
            except IndexError:
                errors['email'] = "Invalid email format."

    # 3. Phone Number (11 digits, starts with 09)
    if 'contact' in form_data:
        contact = form_data['contact'].strip()
        if not re.match(r'^09\d{9}$', contact):
            errors['contact'] = "Phone number must start with 09 and contain exactly 11 digits."

    # 4. Age Calculation & Validation (18-80)
    if 'birthday' in form_data and form_data['birthday']:
        try:
            birth_date = datetime.strptime(form_data['birthday'], '%Y-%m-%d').date()
            today = date.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
            
            if age < 18:
                errors['birthday'] = f"You are only {age} years old. Must be 18+."
            elif age > 80:
                errors['birthday'] = f"Age limit exceeded. Must be under 80 (You are {age})."
        except ValueError:
            errors['birthday'] = "Invalid birthdate format."
    else:
        if 'age' in form_data:
             try:
                age_val = int(form_data['age'])
                if age_val < 18: errors['age'] = "Must be 18+."
                if age_val > 80: errors['age'] = "Must be under 80."
             except: pass

    # 5. Password Validation (Min 8 chars)
    if check_password and 'password' in form_data:
        password = form_data['password'].strip()
        if len(password) < 8:
            errors['password'] = "Password must be at least 8 characters long."

    return errors

# --- RESEND OTP ROUTE (NEW) ---
@auth_bp.route('/resend_otp/<context>')
def resend_otp(context):
    # Only block non-logged in users if it's NOT a password reset
    if 'user_id' not in session and context != 'reset':
        return redirect(url_for('auth_bp.login'))
    
    email = None
    session_key_otp = ''
    session_key_expire = ''
    
    # Determine context (Forgot Password or Edit Profile)
    if context == 'reset':
        email = session.get('reset_email')
        session_key_otp = 'reset_otp'
        session_key_expire = 'reset_otp_expire'
    elif context == 'edit':
        data = session.get('edit_data')
        email = data.get('email') if data else None
        if not email and g.user:
            email = g.user.get('email')
        session_key_otp = 'edit_otp'
        session_key_expire = 'edit_otp_expire'
    else:
        flash("Invalid request.", "error")
        return redirect(url_for('views_bp.user_dashboard'))

    if email:
        otp = send_email_otp(email)
        if otp:
            # Update Session with NEW OTP and NEW Time (3 minutes from now)
            session[session_key_otp] = otp
            session[session_key_expire] = (datetime.now() + timedelta(minutes=3)).timestamp()
            flash("A new OTP has been sent!", "success")
        else:
            flash("Error sending email.", "error")
    else:
        flash("Email not found for resend.", "error")

    # Redirect back to the correct verification page
    if context == 'reset':
        return redirect(url_for('auth_bp.verify_forgot_password'))
    else:
        return redirect(url_for('auth_bp.verify_edit_profile'))

# --- LOGIN ---
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    # 1. NEW: Check if already logged in. If so, redirect to dashboard.
    if 'user_id' in session:
        if session.get('role') == 'admin':
            return redirect(url_for('views_bp.admin_dashboard'))
        return redirect(url_for('views_bp.user_dashboard'))

    form_data = {}
    errors = {}

    if request.method == 'POST':
        form_data = request.form
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cursor.fetchone()
        conn.close()

        if user:
            db_password = user['password']
            if isinstance(db_password, str):
                db_password_bytes = db_password.encode('utf-8')
            else:
                db_password_bytes = db_password

            if bcrypt.checkpw(password.encode('utf-8'), db_password_bytes):
                if user.get('status') == 'blocked':
                    flash("Account is blocked.", "error")
                    return redirect(url_for('auth_bp.login'))
                
                session['user_id'] = user['id']
                session['role'] = user['role']
                session['firstname'] = user['firstname']
                session['username'] = user['username']
                
                log_system_event(user['id'], user['username'], user['role'], 'Login')
                
                flash("Login Successful!", "success")
                if user['role'] == 'admin':
                    return redirect(url_for('views_bp.admin_dashboard'))
                return redirect(url_for('views_bp.user_dashboard'))
            else:
                errors['password'] = "Incorrect password."
        else:
            errors['username'] = "Username not found."
            
    return render_template('login.html', errors=errors, form=form_data)

@auth_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session: return redirect(url_for('auth_bp.login'))
    if session.get('role') == 'admin': return redirect(url_for('views_bp.admin_dashboard'))
    return redirect(url_for('views_bp.user_dashboard'))

@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    username = session.get('username')
    role = session.get('role')
    if user_id:
        log_system_event(user_id, username, role, 'Logout')
    session.clear()
    flash("Logged out successfully.", "success")
    # Redirect directly to login page
    return redirect(url_for('auth_bp.login'))

# --- REGISTER ---
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('views_bp.user_dashboard'))

    form_data = {}
    errors = {}

    if request.method == 'POST':
        form_data = request.form
        errors = validate_form_data(form_data, check_password=True)
        
        password = form_data.get('password', '').strip()
        confirm_password = form_data.get('confirm_password', '').strip()
        if password != confirm_password:
            errors['password'] = "Passwords do not match."
            
        username = form_data.get('username', '').strip()
        if not username: errors['username'] = "Username is required."

        if not errors:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
                if cursor.fetchone():
                    errors['username'] = "Username is already taken."
                
                cursor.execute("SELECT id FROM users WHERE email = %s", (form_data['email'],))
                if cursor.fetchone():
                    errors['email'] = "Email is already registered."

                if not errors:
                    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                    default_role = 'user'
                    
                    # --- HANDLE PROFILE PIC ---
                    profile_pic_name = 'default.jpg' # Default value
                    if 'profile_pic' in request.files:
                        file = request.files['profile_pic']
                        if file and file.filename != '':
                            filename = secure_filename(file.filename)
                            _, ext = os.path.splitext(filename)
                            # Generate unique name (using username + timestamp) to avoid session id issues before login
                            new_filename = f"new_user_{int(time.time())}{ext}"
                            
                            upload_folder = os.path.join('static', 'profile_pics')
                            if not os.path.exists(upload_folder):
                                os.makedirs(upload_folder)
                            
                            file.save(os.path.join(upload_folder, new_filename))
                            profile_pic_name = new_filename

                    # UPDATED SQL TO INCLUDE profile_pic
                    sql = """INSERT INTO users (username, firstname, middlename, lastname, province, city, barangay, zip_code, contact, birthdate, age, email, password, role, profile_pic) 
                             VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
                    
                    birth_date = datetime.strptime(form_data['birthday'], '%Y-%m-%d').date()
                    today = date.today()
                    final_age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

                    val = (username, form_data['firstname'], form_data.get('middlename'), form_data['lastname'], 
                           form_data['province'], form_data['city'], form_data['barangay'], form_data['zip_code'], 
                           form_data['contact'], form_data['birthday'], final_age, form_data['email'], hashed, default_role, profile_pic_name)
                    
                    cursor.execute(sql, val)
                    conn.commit()
                    
                    new_user_id = cursor.lastrowid
                    log_system_event(new_user_id, username, default_role, 'Register')
                    
                    flash("Registration Successful! Please Login.", "success")
                    return redirect(url_for('auth_bp.login'))

            except Exception as e:
                print(f"REGISTER ERROR: {e}")
                flash(f"Error during registration: {e}", "error")
                return render_template('register.html', form=form_data, errors={'general': str(e)})
            finally:
                if 'conn' in locals() and conn.is_connected():
                    conn.close()

    return render_template('register.html', form=form_data, errors=errors)
# --- FORGOT PASSWORD ---
@auth_bp.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        validation_errors = validate_form_data({'email': email}, check_password=False)
        if 'email' in validation_errors:
            flash(validation_errors['email'], "error")
            return render_template('forgot_password.html')

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            otp = send_email_otp(email)
            if otp:
                session['reset_email'] = email
                session['reset_otp'] = otp
                # Set Expiration (3 minutes from now)
                session['reset_otp_expire'] = (datetime.now() + timedelta(minutes=3)).timestamp()
                
                flash(f"An OTP has been sent to {email}", "info")
                return redirect(url_for('auth_bp.verify_forgot_password'))
            else:
                flash("Error sending email. Check server logs.", "error")
        else:
            flash("Email not found.", "error")
            
    return render_template('forgot_password.html')

@auth_bp.route('/verify_forgot_password', methods=['GET', 'POST'])
def verify_forgot_password():
    expiry = session.get('reset_otp_expire')
    
    if request.method == 'POST':
        user_otp = request.form.get('otp')
        
        # Check Expiration
        if not expiry or datetime.now().timestamp() > expiry:
            flash("OTP has expired. Please resend.", "error")
            return redirect(url_for('auth_bp.verify_forgot_password'))

        if user_otp == session.get('reset_otp'):
            flash("OTP Verified.", "success")
            session['reset_verified'] = True
            session.pop('reset_otp_expire', None) # Cleanup expiry
            return redirect(url_for('auth_bp.reset_password_final'))
        else:
            flash("Invalid OTP", "error")
            
    # Pass timestamp to template
    return render_template('verify_forgot_password.html', expire_timestamp=expiry)

@auth_bp.route('/reset_password_final', methods=['GET', 'POST'])
def reset_password_final():
    if not session.get('reset_verified'): return redirect(url_for('auth_bp.forgot_password'))
    if request.method == 'POST':
        if request.form.get('password') == request.form.get('confirm_password'):
            hashed = bcrypt.hashpw(request.form.get('password').encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET password=%s WHERE email=%s", (hashed, session['reset_email']))
            conn.commit()
            conn.close()
            session.pop('reset_email', None)
            session.pop('reset_otp', None)
            session.pop('reset_verified', None)
            session.pop('reset_otp_expire', None)
            flash("Password updated!", "success")
            return redirect(url_for('auth_bp.login'))
        else:
            flash("Passwords mismatch.", "error")
    return render_template('reset_password_final.html')

# --- EDIT PROFILE + OTP (FILE UPLOAD ADDED) ---
@auth_bp.route('/edit_profile_action', methods=['POST'])
def edit_profile_action():
    if 'user_id' not in session: return redirect(url_for('auth_bp.login'))
    
    form_data = request.form.to_dict()
    errors = validate_form_data(form_data, check_password=False)
    
    # --- HANDLE FILE UPLOAD ---
    # Store filename in form_data BEFORE validation checks
    if 'profile_pic' in request.files:
        file = request.files['profile_pic']
        if file and file.filename != '':
            filename = secure_filename(file.filename)
            _, ext = os.path.splitext(filename)
            new_filename = f"user_{session['user_id']}_{int(time.time())}{ext}"
            
            # Use os.path.abspath to ensure correct path relative to this file
            base_dir = os.path.dirname(os.path.abspath(__file__)) # Directory of auth.py
            # Go up one level to root, then into static/profile_pics
            upload_folder = os.path.join(os.path.dirname(base_dir), 'static', 'profile_pics')
            
            if not os.path.exists(upload_folder):
                os.makedirs(upload_folder)
            
            file.save(os.path.join(upload_folder, new_filename))
            form_data['profile_pic'] = new_filename # Add to dictionary

    if errors:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
        user = cursor.fetchone()
        conn.close()
        if user: user.update(form_data)
        return render_template('profile.html', user=user, errors=errors, access=session.get('role'))

    # Store validated data (including filename) into session
    session['edit_data'] = form_data
    
    if form_data.get('birthday'):
        birth_date = datetime.strptime(form_data['birthday'], '%Y-%m-%d').date()
        today = date.today()
        final_age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        session['edit_data']['age'] = final_age

    email = request.form.get('email')
    if not email and g.user:
        email = g.user.get('email')

    if email:
        otp = send_email_otp(email)
        if otp:
            session['edit_otp'] = otp
            session['edit_otp_expire'] = (datetime.now() + timedelta(minutes=3)).timestamp()
            return redirect(url_for('auth_bp.verify_edit_profile'))
        else:
            flash("Failed to send verification email.", "error")
            return redirect(url_for('views_bp.profile'))
    else:
        flash("User email not found.", "error")
        return redirect(url_for('views_bp.profile'))

@auth_bp.route('/verify_edit_profile', methods=['GET', 'POST'])
def verify_edit_profile():
    expiry = session.get('edit_otp_expire')

    if request.method == 'POST':
        otp = request.form.get('otp')
        if not expiry or datetime.now().timestamp() > expiry:
            flash("OTP has expired. Please resend.", "error")
            return redirect(url_for('auth_bp.verify_edit_profile'))

        if otp == session.get('edit_otp'):
            data = session.get('edit_data')
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                # Retrieve filename from session data, or keep old one
                current_pic = g.user.get('profile_pic', 'default.jpg')
                new_pic = data.get('profile_pic', current_pic)

                sql = """UPDATE users SET username=%s, firstname=%s, middlename=%s, lastname=%s, 
                         birthdate=%s, age=%s, contact=%s, province=%s, city=%s, barangay=%s, zip_code=%s,
                         profile_pic=%s WHERE id=%s"""
                val = (data.get('username'), data.get('firstname'), data.get('middlename'), data.get('lastname'),
                       data.get('birthdate'), data.get('age'), data.get('contact'), data.get('province'),
                       data.get('city'), data.get('barangay'), data.get('zip_code'), 
                       new_pic, 
                       session['user_id'])
                
                cursor.execute(sql, val)
                conn.commit()
                
                # Update Session Data immediately
                session['username'] = data.get('username')
                session['firstname'] = data.get('firstname')
                
                log_system_event(session['user_id'], session.get('username'), session.get('role'), 'Profile Update')
                
                session.pop('edit_otp_expire', None)
                flash("Profile updated successfully", "success")
                return redirect(url_for('views_bp.confirm_edit_profile'))
            except Exception as e:
                flash(f"Error: {e}", "error")
                return redirect(url_for('views_bp.profile'))
            finally:
                conn.close()
        else:
            flash("Invalid OTP", "error")
            
    return render_template('verify_edit_profile.html', expire_timestamp=expiry)