from app import create_app, db
from app.models.transactions import MilkSaleTransaction
from datetime import datetime
import os

def test_database_connection():
    """Test if the app can connect to the database and access milk_sale_transaction table"""
    app = create_app()
    
    # Print application configuration
    print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
    print(f"Instance path: {app.instance_path}")
    
    # Check if database file exists
    db_path = os.path.join(app.instance_path, 'dairy.db')
    if os.path.exists(db_path):
        print(f"Database exists at {db_path} ({os.path.getsize(db_path) / 1024:.2f} KB)")
    else:
        print(f"WARNING: Database file not found at {db_path}")
    
    # Test querying the milk_sale_transaction table
    with app.app_context():
        try:
            # Check if table exists by trying to query it
            transactions_count = MilkSaleTransaction.query.count()
            print(f"Successfully connected to database and found {transactions_count} milk sale transactions.")
            
            # Add a test transaction if the table is empty
            if transactions_count == 0:
                print("Adding a test milk sale transaction...")
                test_transaction = MilkSaleTransaction(
                    dairy_holder_id=1,  # Assuming user ID 1 exists
                    buyer_name="Test Buyer",
                    milk_type="cow",
                    quantity=10.0,
                    price_per_liter=50.0,
                    total_amount=500.0,
                    fat_percentage=3.5,
                    snf_percentage=8.5,
                    date=datetime.utcnow(),
                    is_paid=True,
                    payment_date=datetime.utcnow(),
                    notes="Test transaction"
                )
                
                db.session.add(test_transaction)
                db.session.commit()
                print("Test transaction added successfully.")
            
            # Verify the milk_sale_transaction table structure
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            columns = inspector.get_columns('milk_sale_transaction')
            print("\nMilk Sale Transaction Table Columns:")
            for column in columns:
                print(f"  - {column['name']} ({column['type']})")
                
            return True
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
            return False

if __name__ == "__main__":
    test_database_connection() 