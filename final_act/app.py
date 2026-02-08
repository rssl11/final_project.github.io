from flask import Flask
from blueprints.auth import auth_bp
from blueprints.views import views_bp
from game_routes import games_bp 
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)  

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(views_bp)
app.register_blueprint(games_bp)

@app.after_request
def add_header(response):
    """
    Forces the browser to not cache any page. 
    If the user clicks 'Back', the browser must ask the server for the page again.
    Since the user is logged out, the server will reject them.
    """
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5000)