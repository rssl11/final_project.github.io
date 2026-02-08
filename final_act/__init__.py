from flask import Flask
from flask_mysqldb import MySQL
from flask_mail import Mail

mysql = MySQL()
mail = Mail()

def create_app():
    app = Flask(__name__)
    
    # --- Database Config ---
    app.config['MYSQL_HOST'] = 'localhost'
    app.config['MYSQL_USER'] = 'root'
    app.config['MYSQL_PASSWORD'] = '' # Default XAMPP password
    app.config['MYSQL_DB'] = 'flask_game_system'
    app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
    app.config['SECRET_KEY'] = 'super_secret_key_123'

    # --- SMTP Email Config (Gmail Example) ---
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'rasseldizon44@gmail.com' # CHANGE THIS
    app.config['MAIL_PASSWORD'] = 'your_app_password'    # CHANGE THIS

    mysql.init_app(app)
    mail.init_app(app)

    # --- Blueprints ---
    from .blueprints.auth import auth_bp
    from .blueprints.admin import admin_bp
    from .blueprints.views import views_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(views_bp)

    # --- Prevent Back Button Caching ---
    @app.after_request
    def add_header(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    return app