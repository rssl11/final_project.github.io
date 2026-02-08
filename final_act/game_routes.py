from flask import Blueprint, redirect, url_for, flash, session
import subprocess
import os
import sys
from db_config import get_db_connection

# Define the blueprint
games_bp = Blueprint('games_bp', __name__)

# List of allowed games matching your filenames in the 'games' folder
ALLOWED_GAMES = ['shape_catcher', 'spacewar']

@games_bp.route('/play_game/<game_name>')
def play_game(game_name):
    # 1. Security Check: Ensure user is logged in
    if 'user_id' not in session:
        flash("You must be logged in to play.", "error")
        return redirect(url_for('auth_bp.login'))

    # 2. Validation: Ensure the game is in our allowed list
    if game_name not in ALLOWED_GAMES:
        flash("Game not found.", "error")
        return redirect_back()

    # --- NEW: DATABASE PERMISSION CHECK ---
    # Convert url name (shape_catcher) to DB name (Shape Catcher)
    db_game_name = "Shape Catcher" if game_name == "shape_catcher" else "Space War"
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Check if a restriction exists for this user and game
    cursor.execute("SELECT has_access FROM game_access WHERE user_id=%s AND game_name=%s", 
                   (session['user_id'], db_game_name))
    access_record = cursor.fetchone()
    conn.close()

    # If a record exists AND it is set to 0 (False), block the game
    if access_record and access_record['has_access'] == 0:
        flash("You are not able to play this game. Access restricted by Admin.", "error")
        return redirect_back()
    # --------------------------------------

    # 3. Locate the Game File
    base_dir = os.path.dirname(os.path.abspath(__file__))
    game_path = os.path.join(base_dir, 'games', f'{game_name}.py')

    print(f"DEBUG: Looking for game at: {game_path}")

    # 4. Launch the Game
    if os.path.exists(game_path):
        try:
            # subprocess.Popen launches the game as a separate window 
            subprocess.Popen([sys.executable, game_path])
            flash(f"Launching {db_game_name}...", "success")
        except Exception as e:
            flash(f"Error launching game: {e}", "error")
    else:
        print(f"ERROR: Could not find game file at {game_path}")
        flash(f"Game file missing. Please check server console.", "error")

    return redirect_back()

def redirect_back():
    """Helper to redirect to the correct dashboard based on role."""
    if session.get('role') == 'admin':
        return redirect(url_for('views_bp.admin_dashboard'))
    return redirect(url_for('views_bp.user_dashboard'))