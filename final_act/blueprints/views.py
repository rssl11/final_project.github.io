from flask import Blueprint, render_template, session, redirect, url_for, request, flash
from db_config import get_db_connection
import datetime
import subprocess
import sys
import os
import re 
import socket 
from werkzeug.security import generate_password_hash 

views_bp = Blueprint('views_bp', __name__)

# --- NEW: Helper Function for Email Domain Validation ---
def validate_email_domain(email):
    """
    Checks if the email is structurally valid and attempts to verify if the domain has an A record (existence check).
    """
    # 1. Basic format check (user@domain.tld structure)
    # This regex is strict enough to require at least one dot after the @ and at least two letters after the last dot.
    if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email):
        return False
    
    domain = email.split('@')[-1]
    
    # 2. Simple check for testing domains (to avoid socket errors in development)
    if domain in ['localhost', 'testserver']:
        return True 

    # 3. Domain existence check (A record lookup) - Stricter check
    try:
        # Check if the domain has an A record 
        socket.gethostbyname(domain)
        return True
    except socket.gaierror:
        # If the host name lookup fails (domain doesn't exist or is unreachable)
        return False
    except Exception:
        # Catch all other potential network/OS errors
        return False

# --- CACHE BUSTER ---
@views_bp.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

def is_admin():
    return session.get('role') == 'admin'

# --- LANDING PAGE ---
@views_bp.route('/')
def landing_page():
    if 'user_id' in session:
        if is_admin():
            return redirect(url_for('views_bp.admin_dashboard'))
        return redirect(url_for('views_bp.user_dashboard'))
    return render_template('index.html', access=session.get('role'))

# --- USER DASHBOARD ---
@views_bp.route('/dashboard/user')
def user_dashboard():
    if 'user_id' not in session: 
        flash("Please login first.", "error")
        return redirect(url_for('auth_bp.login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    user = cursor.fetchone()

    cursor.execute("SELECT COUNT(*) as count FROM game_scores WHERE user_id=%s", (session['user_id'],))
    stats = cursor.fetchone()
    games_played = stats['count'] if stats else 0
    
    conn.close()

    if user:
        fname = user.get('firstname', '')
        lname = user.get('lastname', '')
        full_name = f"{fname} {lname}" if fname and lname else (fname if fname else user.get('username'))

        db_pic = user.get('profile_pic')
        profile_pic = url_for('static', filename=f'profile_pics/{db_pic}') if db_pic else "https://images.unsplash.com/photo-1535713875002-d1d0cf377fde?w=500&auto=format&fit=crop&q=60"

        return render_template('dashboard_user.html', 
                               access=session.get('role'), 
                               username=session.get('username'),
                               full_name=full_name,
                               age=user.get('age'),          
                               address=user.get('address'),   
                               profile_pic=profile_pic,
                               games_played=games_played)
    else:
        flash("User data not found.", "error")
        return redirect(url_for('auth_bp.logout'))

# --- ADMIN DASHBOARD ---
@views_bp.route('/dashboard/admin')
def admin_dashboard():
    if 'user_id' not in session: 
        flash("Please login first.", "error")
        return redirect(url_for('auth_bp.login'))

    if not is_admin(): 
        flash("Unauthorized access! You are not an admin.", "error")
        return redirect(url_for('views_bp.user_dashboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    users = []
    logs = []
    game_history = []
    top_shape = []
    top_space = []
    top_space_2p = [] 

    try:
        cursor.execute("SELECT * FROM users")
        all_users = cursor.fetchall()
        users = [u for u in all_users if u.get('role') == 'user']

        cursor.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT 10")
        logs = cursor.fetchall()
        for log in logs:
            ts = str(log.get('timestamp', ''))
            log['timestamp'] = ts if len(ts) > 10 else datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            SELECT s.id, u.username, s.game_name, s.score, s.timestamp 
            FROM game_scores s 
            JOIN users u ON s.user_id = u.id 
            WHERE s.is_deleted = 0
            ORDER BY s.timestamp DESC
            LIMIT 10
        """)
        game_history = cursor.fetchall()

        # Shape Catcher Leaderboard
        cursor.execute("""
            SELECT u.username, MAX(s.score) as score
            FROM game_scores s 
            JOIN users u ON s.user_id = u.id 
            WHERE s.game_name = 'Shape Catcher' AND s.is_deleted = 0
            GROUP BY u.id, u.username
            ORDER BY score DESC 
            LIMIT 5
        """)
        top_shape = cursor.fetchall()

        # Space War Leaderboard
        cursor.execute("""
            SELECT u.username, MAX(s.score) as score
            FROM game_scores s 
            JOIN users u ON s.user_id = u.id 
            WHERE s.game_name = 'Space War' AND s.is_deleted = 0
            GROUP BY u.id, u.username
            ORDER BY score DESC 
            LIMIT 5
        """)
        top_space = cursor.fetchall()

        # Space War 2P Leaderboard
        cursor.execute("""
            SELECT u.username, MAX(s.score) as score
            FROM game_scores s 
            JOIN users u ON s.user_id = u.id 
            WHERE s.game_name = 'Space War 2P' AND s.is_deleted = 0
            GROUP BY u.id, u.username
            ORDER BY score DESC 
            LIMIT 5
        """)
        top_space_2p = cursor.fetchall()

    except Exception as e:
        print(f"Error fetching dashboard data: {e}")
    
    access_permissions = {}
    for user in users:
        access_permissions[user['id']] = { 
            'Shape Catcher': True, 
            'Space War': True,
            'Space War 2P': True 
        }

    try:
        cursor.execute("SELECT * FROM game_access")
        for row in cursor.fetchall():
            u_id = row['user_id']
            g_name = row['game_name']
            if u_id in access_permissions:
                access_permissions[u_id][g_name] = bool(row['has_access'])
    except Exception: pass
        
    conn.close()
    
    return render_template('dashboard_admin.html', 
                           users=users, logs=logs, 
                           game_history=game_history,
                           top_shape=top_shape,
                           top_space=top_space,
                           top_space_2p=top_space_2p,
                           access=access_permissions, 
                           role=session.get('role'))

# --- GAMES LIST ---
@views_bp.route('/games')
def games():
    if 'user_id' not in session: 
        flash("Please login to view games.", "error")
        return redirect(url_for('auth_bp.login'))
    return render_template('games.html', access=session.get('role'))

# --- ARCHIVES ---
@views_bp.route('/dashboard/admin/archives')
def view_archives():
    if not is_admin(): return redirect(url_for('auth_bp.login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    archives = []
    try:
        cursor.execute("""
            SELECT s.id, u.username, s.game_name, s.score, s.timestamp 
            FROM game_scores s 
            JOIN users u ON s.user_id = u.id 
            WHERE s.is_deleted = 1 ORDER BY s.timestamp DESC
        """)
        archives = cursor.fetchall()
    finally: conn.close()
    return render_template('archives.html', archives=archives, role='admin')

# --- ARCHIVE ACTIONS ---
@views_bp.route('/archive_score/<int:score_id>')
def archive_score(score_id):
    if not is_admin(): return redirect(url_for('auth_bp.login'))
    conn = get_db_connection()
    conn.cursor().execute("UPDATE game_scores SET is_deleted = 1 WHERE id = %s", (score_id,))
    conn.commit()
    conn.close()
    flash("Score deleted successfully.", "success") 
    return redirect(url_for('views_bp.admin_dashboard'))

@views_bp.route('/restore_score/<int:score_id>')
def restore_score(score_id):
    if not is_admin(): return redirect(url_for('auth_bp.login'))
    conn = get_db_connection()
    conn.cursor().execute("UPDATE game_scores SET is_deleted = 0 WHERE id = %s", (score_id,))
    conn.commit()
    conn.close()
    flash("Score restored.", "success")
    return redirect(url_for('views_bp.view_archives'))

@views_bp.route('/delete_score_permanent/<int:score_id>')
def delete_score_permanent(score_id):
    if not is_admin(): return redirect(url_for('auth_bp.login'))
    conn = get_db_connection()
    conn.cursor().execute("DELETE FROM game_scores WHERE id = %s", (score_id,))
    conn.commit()
    conn.close()
    flash("Score deleted permanently.", "success")
    return redirect(url_for('views_bp.view_archives'))

# --- MANAGEMENT ACTIONS ---
@views_bp.route('/toggle_account_status/<int:user_id>/<string:new_status>')
def toggle_account_status(user_id, new_status):
    if not is_admin(): return redirect(url_for('auth_bp.login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status=%s WHERE id=%s", (new_status, user_id))
    cursor.execute("SELECT username FROM users WHERE id=%s", (user_id,))
    target = cursor.fetchone()
    log_action = f"{'Banned' if new_status == 'blocked' else 'Unbanned'} User: {target[0]}"
    cursor.execute("INSERT INTO system_logs (user_id, username, role, action_type) VALUES (%s, %s, %s, %s)", 
                   (session['user_id'], session['username'], 'admin', log_action))
    conn.commit()
    conn.close()
    flash(f"User updated: {new_status}", "success")
    return redirect(url_for('views_bp.admin_dashboard'))

@views_bp.route('/toggle_game/<int:uid>/<string:game>/<int:state>')
def toggle_game(uid, game, state):
    if session.get('role') != 'admin': return redirect(url_for('auth_bp.login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM game_access WHERE user_id=%s AND game_name=%s", (uid, game))
    if cursor.fetchone():
        cursor.execute("UPDATE game_access SET has_access=%s WHERE user_id=%s AND game_name=%s", (state, uid, game))
    else:
        cursor.execute("INSERT INTO game_access (user_id, game_name, has_access) VALUES (%s, %s, %s)", (uid, game, state))
    conn.commit()
    conn.close()
    flash(f"{game} toggled.", "success")
    return redirect(url_for('views_bp.admin_dashboard'))

# --- PLAY GAME ROUTE ---
@views_bp.route('/play/<game_name>')
def play_game(game_name):
    if 'user_id' not in session: 
        return redirect(url_for('auth_bp.login'))

    if "2p" in game_name.lower() or "2 player" in game_name.lower():
        target_db_name = "Space War 2P"
        target_script = "space_war_2p.py"
    elif "shape" in game_name.lower():
        target_db_name = "Shape Catcher"
        target_script = "shape_catcher.py"
    else:
        target_db_name = "Space War"
        target_script = "space_war.py"
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT has_access FROM game_access WHERE user_id=%s AND game_name=%s", (session['user_id'], target_db_name))
    record = cursor.fetchone()
    conn.close()
    
    if record and record['has_access'] == 0:
        flash("You are blocked from using this game.", "error")
        return redirect(url_for('views_bp.user_dashboard'))

    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        games_folder = os.path.join(base_dir, 'games')
        script_path = os.path.join(games_folder, target_script)
        
        if os.path.exists(script_path):
            subprocess.Popen([sys.executable, script_path, str(session['user_id'])], cwd=games_folder)
            flash(f"{game_name} Launched!", "success")
        else:
            flash(f"Game file missing: {target_script}", "error")
    except Exception as e:
        flash(f"Launch error: {e}", "error")

    return redirect(url_for('views_bp.user_dashboard'))

# --- ADMIN ADD USER ROUTE (UPDATED VALIDATION) ---
@views_bp.route('/dashboard/admin/add_user', methods=['GET', 'POST'])
def admin_add_user():
    # Security check: Must be logged in and must be Admin
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('auth_bp.login'))

    if request.method == 'POST':
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        errors = []

        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        fname = request.form.get('firstname')
        lname = request.form.get('lastname')
        
        # --- SERVER-SIDE VALIDATION ---
        
        # 1. Name Capitalization Check
        if not fname or not fname.strip() or not fname[0].isalpha() or fname[0].upper() != fname[0]:
            errors.append("First Name must start with a capital letter.")
        if not lname or not lname.strip() or not lname[0].isalpha() or lname[0].upper() != lname[0]:
            errors.append("Last Name must start with a capital letter.")

        # 2. Password Length (Minimum 8 chars)
        if len(password) < 8:
            errors.append("Password must be at least 8 characters long.")

        # 3. Email Domain and Format Check (Stricter validation)
        if not validate_email_domain(email):
            errors.append("Invalid email format or non-existent domain. Please check your email address.")

        # 4. Database Duplicate Check
        cursor.execute("SELECT * FROM users WHERE email=%s OR username=%s", (email, username))
        if cursor.fetchone():
            errors.append('Email or Username already exists.')

        # If any validation errors exist, flash them and stop
        if errors:
            conn.close()
            for error in errors:
                flash(error, 'error')
            return render_template('admin_add_user.html', access=session.get('role'))
        
        # If no errors, proceed with user creation
        hashed_password = generate_password_hash(password)
        
        try:
            cursor.execute("""
                INSERT INTO users (username, email, password, firstname, lastname, role, status) 
                VALUES (%s, %s, %s, %s, %s, 'user', 'active')
            """, (username, email, hashed_password, fname, lname))
            conn.commit()
            flash('New user created successfully!', 'success')
            conn.close()
            return redirect(url_for('views_bp.admin_dashboard'))
        except Exception as e:
            flash(f"Error creating user: {e}", "error")
            conn.close()

    return render_template('admin_add_user.html', access=session.get('role'))

@views_bp.route('/edit_profile', methods=['POST'])
def edit_profile():
    if 'user_id' not in session: return redirect(url_for('auth_bp.login'))
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE users 
            SET firstname=%s, lastname=%s, email=%s, age=%s, address=%s 
            WHERE id=%s
        """, (
            request.form.get('firstname'), request.form.get('lastname'), request.form.get('email'), 
            request.form.get('age'), request.form.get('address'), session['user_id']
        ))
        conn.commit()
        flash("Profile Updated Successfully", "success")
    except Exception as e:
        flash(f"Error: {e}", "error")
    finally:
        conn.close()
    return redirect(url_for('views_bp.profile'))

@views_bp.route('/profile')
def profile():
    if 'user_id' not in session: return redirect(url_for('auth_bp.login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users WHERE id=%s", (session['user_id'],))
    user = cursor.fetchone()
    conn.close()
    return render_template('profile.html', user=user, access=session.get('role'))

@views_bp.route('/confirm_edit_profile')
def confirm_edit_profile():
    return render_template('confirm_edit_profile.html', access=session.get('role'))

@views_bp.route('/blog', methods=['GET', 'POST'])
def blog():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST' and is_admin():
        cursor.execute("INSERT INTO blogs (author_id, title, content) VALUES (%s, %s, %s)", 
                       (session['user_id'], request.form.get('title'), request.form.get('content')))
        conn.commit() 
        return redirect(url_for('views_bp.blog'))
    
    try:
        cursor.execute("SELECT b.*, u.firstname FROM blogs b JOIN users u ON b.author_id = u.id ORDER BY created_at DESC")
        posts = cursor.fetchall()
    except: posts = []
    conn.close()
    return render_template('blog.html', posts=posts, is_admin=is_admin(), access=session.get('role'))