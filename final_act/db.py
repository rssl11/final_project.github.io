import sqlite3
import click
from flask import current_app, g
from flask.cli import with_appcontext

def get_db():
    """Connects to the database defined in the app configuration."""
    if 'db' not in g:
        # Connect to the SQLite database defined in the app config
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        # Allows accessing columns by name instead of index
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    """Closes the database connection."""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Clears existing data and creates new tables from schema.sql."""
    db = get_db()
    
    # current_app.open_resource looks for files relative to the final_act package
    with current_app.open_resource('schema.sql') as f:
        # Execute all SQL statements in the schema.sql file
        db.executescript(f.read().decode('utf8'))
    
    # Optional: Insert an initial admin user (replace 'admin_hash' with a real hash)
    from werkzeug.security import generate_password_hash
    admin_password_hash = generate_password_hash('adminpass') 
    
    # Insert an initial admin user into the 'users' table
    try:
        db.execute(
            "INSERT INTO users (username, email, password_hash, first_name, status) VALUES (?, ?, ?, ?, ?)",
            ('admin', 'admin@example.com', admin_password_hash, 'Admin User', 'active')
        )
        db.commit()
    except sqlite3.IntegrityError:
        # If the admin user already exists, just pass
        pass


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Clears the existing data and creates new tables."""
    init_db()
    click.echo('Initialized the database.')

def init_app(app):
    """Registers the close_db and init_db functions with the Flask application."""
    # Ensure database connection is closed after response
    app.teardown_appcontext(close_db)
    # Add the 'init-db' command to the Flask CLI
    app.cli.add_command(init_db_command)