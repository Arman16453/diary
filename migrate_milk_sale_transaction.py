import sqlite3
from datetime import datetime
import os

def create_milk_sale_transaction_table():
    """
    Create the milk_sale_transaction table that is missing from the database.
    """
    print("Starting migration: Creating milk_sale_transaction table...")
    print(f"Current working directory: {os.getcwd()}")
    
    db_path = 'app.db'
    print(f"Looking for database at: {os.path.abspath(db_path)}")
    
    if not os.path.exists(db_path):
        print(f"WARNING: Database file {db_path} does not exist!")
        db_path = 'instance/app.db'
        print(f"Trying alternative path: {os.path.abspath(db_path)}")
        
        if not os.path.exists(db_path):
            print(f"ERROR: Database file {db_path} does not exist!")
            return False
    
    # Connect to the database
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        print(f"Successfully connected to database: {db_path}")
        
        # Check if the table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='milk_sale_transaction'")
        if cursor.fetchone():
            print("Table milk_sale_transaction already exists. Skipping creation.")
        else:
            # Create the milk_sale_transaction table
            print("Creating milk_sale_transaction table...")
            cursor.execute('''
            CREATE TABLE milk_sale_transaction (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                dairy_holder_id INTEGER NOT NULL,
                buyer_id INTEGER,
                buyer_name VARCHAR(100) NOT NULL,
                milk_type VARCHAR(50) NOT NULL,
                quantity FLOAT NOT NULL,
                price_per_liter FLOAT NOT NULL,
                total_amount FLOAT NOT NULL,
                fat_percentage FLOAT,
                snf_percentage FLOAT,
                date DATETIME NOT NULL,
                is_paid BOOLEAN NOT NULL DEFAULT 0,
                payment_date DATETIME,
                notes TEXT,
                FOREIGN KEY (dairy_holder_id) REFERENCES user (id),
                FOREIGN KEY (buyer_id) REFERENCES user (id)
            )
            ''')
            print("Table milk_sale_transaction created successfully.")
        
        # Commit the changes and close the connection
        conn.commit()
        conn.close()
        print("Migration completed successfully.")
        return True
    except Exception as e:
        print(f"ERROR during migration: {str(e)}")
        return False

if __name__ == "__main__":
    create_milk_sale_transaction_table()
    print("Migration script execution completed.") 