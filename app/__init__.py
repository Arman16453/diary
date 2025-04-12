from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

# Initialize SQLAlchemy
db = SQLAlchemy()

def create_app():
    # Create and configure the app
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'your-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///dairy.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize plugins
    db.init_app(app)
    
    # Setup login manager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)
    
    from app.models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    from app.routes.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)
    
    from app.routes.main import main as main_blueprint
    app.register_blueprint(main_blueprint)
    
    from app.routes.milk_seller import milk_seller as milk_seller_blueprint
    app.register_blueprint(milk_seller_blueprint)
    
    from app.routes.bike_milk_seller import bike_milk_seller as bike_milk_seller_blueprint
    app.register_blueprint(bike_milk_seller_blueprint)
    
    from app.routes.dairy_holder import dairy_holder as dairy_holder_blueprint
    app.register_blueprint(dairy_holder_blueprint)
    
    from app.routes.milk_buyer import milk_buyer as milk_buyer_blueprint
    app.register_blueprint(milk_buyer_blueprint)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    return app 