import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

# Initialize extensions
db = SQLAlchemy()

# Custom Jinja filters
def slice_filter(iterable, start, end=None):
    return iterable[start:end]

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize database
    db.init_app(app)
    
    # Ensure the instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    # Initialize login manager
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Add custom filters to Jinja environment
    app.jinja_env.filters['slice'] = slice_filter
    
    from app.models.user import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Register blueprints
    from app.routes.main import main
    from app.routes.auth import auth
    from app.routes.milk_seller import milk_seller
    from app.routes.bike_milk_seller import bike_milk_seller
    from app.routes.dairy_holder import dairy_holder
    from app.routes.milk_buyer import milk_buyer
    
    app.register_blueprint(main)
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(milk_seller, url_prefix='/milk-seller')
    app.register_blueprint(bike_milk_seller, url_prefix='/bike-milk-seller')
    app.register_blueprint(dairy_holder, url_prefix='/dairy-holder')
    app.register_blueprint(milk_buyer, url_prefix='/milk-buyer')
    
    return app

# Import models at the end to avoid circular imports
from app.models.user import User, UserRole
from app.models.transaction import Transaction
from app.models.delivery import Delivery
from app.models.purchase_transaction import PurchaseTransaction
from app.models.customer import Customer 