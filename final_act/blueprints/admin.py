from flask import Blueprint, render_template, session, redirect, url_for, flash
from final_act import mysql

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.before_request
def check_admin():
    if not session.get('loggedin') or session.get('role') != 'admin':
        return redirect(url_for('auth.login'))

@admin_bp.route('/dashboard')
def dashboard():
    cursor = mysql.connection.cursor()
    
    # 1. User Management
    cursor.execute("SELECT * FROM users WHERE role='user'")
    users = cursor.fetchall()
    
    # 2. System Logs
    cursor.execute("SELECT * FROM system_logs ORDER BY timestamp DESC LIMIT 20")
    logs = cursor.fetchall()
    
    # 3. Top Players (Shape Catcher)
    cursor.execute("""
        SELECT u.username, s.score, s.played_at FROM game_scores s 
        JOIN users u ON s.user_id = u.id 
        WHERE s.game_name='Shape Catcher' ORDER BY s.score DESC LIMIT 5
    """)
    top_shape = cursor.fetchall()

    # 4. Top Players (Space War)
    cursor.execute("""
        SELECT u.username, s.score, s.played_at FROM game_scores s 
        JOIN users u ON s.user_id = u.id 
        WHERE s.game_name='Space War' ORDER BY s.score DESC LIMIT 5
    """)
    top_space = cursor.fetchall()
    
    # 5. Game Access Map
    game_access_map = {}
    for u in users:
        cursor.execute("SELECT * FROM game_access WHERE user_id=%s", (u['id'],))
        game_access_map[u['id']] = {row['game_name']: row['is_enabled'] for row in cursor.fetchall()}

    cursor.close()
    return render_template('admin/dashboard.html', users=users, logs=logs, 
                           top_shape=top_shape, top_space=top_space, 
                           access=game_access_map)

@admin_bp.route('/toggle_status/<int:id>/<string:action>')
def toggle_status(id, action):
    status = 'inactive' if action == 'block' else 'active'
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE users SET status=%s WHERE id=%s", (status, id))
    
    # Log it
    cursor.execute("INSERT INTO system_logs (admin_id, action, target_user) VALUES (%s, %s, %s)", 
                   (session['id'], f"Admin {action}ed user {id}", str(id)))
    
    mysql.connection.commit()
    flash(f"User {action}ed.", "success")
    return redirect(url_for('admin.dashboard'))

@admin_bp.route('/toggle_game/<int:uid>/<string:game>/<int:state>')
def toggle_game(uid, game, state):
    cursor = mysql.connection.cursor()
    cursor.execute("UPDATE game_access SET is_enabled=%s WHERE user_id=%s AND game_name=%s", 
                   (state, uid, game))
    mysql.connection.commit()
    return redirect(url_for('admin.dashboard'))