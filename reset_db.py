from app import create_app, db
from app.models.user import User, UserRole
from app.models.transactions import MilkTransaction, DeliveryTransaction, PurchaseTransaction, DairyStock
import os

def reset_db():
    app = create_app()
    with app.app_context():
        # Drop all tables
        db.drop_all()
        print("Database dropped successfully")
        
        # Create all tables
        db.create_all()
        print("Database created successfully")
        
        # Create admin user
        admin = User(
            name="Admin User",
            email="admin@dairyapp.com",
            password="password",  # In a real app, you'd hash this
            role="admin"
        )
        
        # Create test users for each role
        milk_seller = User(
            name="Milk Seller",
            email="seller@dairyapp.com",
            password="password",  # In a real app, you'd hash this
            role=UserRole.MILK_SELLER,
            phone="9876543210",
            address="123 Farm Road"
        )
        
        bike_milk_seller = User(
            name="Bike Milk Seller",
            email="bike@dairyapp.com",
            password="password",  # In a real app, you'd hash this
            role=UserRole.BIKE_MILK_SELLER,
            phone="9876543211",
            address="456 Delivery Street"
        )
        
        dairy_holder = User(
            name="Dairy Holder",
            email="dairy@dairyapp.com",
            password="password",  # In a real app, you'd hash this
            role=UserRole.DAIRY_HOLDER,
            phone="9876543212",
            address="789 Dairy Avenue"
        )
        
        milk_buyer = User(
            name="Milk Buyer",
            email="buyer@dairyapp.com",
            password="password",  # In a real app, you'd hash this
            role=UserRole.MILK_BUYER,
            phone="9876543213",
            address="321 Purchase Lane"
        )
        
        # Create a test user with multi-role access
        multi_role_user = User(
            name="Demo User",
            email="demo@dairyapp.com",
            password="password",  # In a real app, you'd hash this
            role="multi_role",
            phone="9876543214",
            address="999 Demo Street"
        )
        
        # Add users to database
        db.session.add(admin)
        db.session.add(milk_seller)
        db.session.add(bike_milk_seller)
        db.session.add(dairy_holder)
        db.session.add(milk_buyer)
        db.session.add(multi_role_user)
        db.session.commit()
        
        print("Test users created successfully")

if __name__ == "__main__":
    # Check if the database file exists and delete it
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'dairy.db')
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Deleted existing database: {db_path}")
        
    reset_db()
    print("Database reset completed successfully") 