from routes.chat import chat_bp
from routes.tasks import tasks_bp
from routes.auth import auth_bp
from flask import Flask, redirect, url_for
from flask_login import LoginManager
from models import db, User
from config import Config
import os

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Register blueprints

app.register_blueprint(auth_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(chat_bp)

# Root route


@app.route('/')
def index():
    """Redirect to dashboard or login"""
    return redirect(url_for('tasks.dashboard'))


# Create tables if they don't exist
with app.app_context():
    db.create_all()
    print("✓ Database tables created/verified")

# Run the app
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
