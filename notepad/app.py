from flask import Flask
from blueprints.auth import auth_bp
from blueprints.main import main_bp
import os

def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET', 'change-me-to-a-strong-secret')

    # Register blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(main_bp, url_prefix="/")

    # ------------------------------
    # Prevent browser caching (important for logout/back button)
    # ------------------------------
    @app.after_request
    def add_no_cache_headers(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response
    # ------------------------------

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
