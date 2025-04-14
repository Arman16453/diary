import os
import sys
import sqlite3
from datetime import datetime

def migrate_database():
    """
    Creates the milk_sale_transaction table for tracking milk sales by dairy holders.
    """
    print("Starting database migration...")
    
    # Get the path to the database
    db_path = 'app.db'
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        sys.exit(1)
    
    # Connect to the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if the milk_sale_transaction table already exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='milk_sale_transaction'")
        if cursor.fetchone():
            print("The milk_sale_transaction table already exists. Skipping table creation.")
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
                date TIMESTAMP NOT NULL,
                is_paid BOOLEAN NOT NULL DEFAULT 0,
                payment_date TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (dairy_holder_id) REFERENCES user (id),
                FOREIGN KEY (buyer_id) REFERENCES user (id)
            )
            ''')
            
            print("Successfully created milk_sale_transaction table!")
        
        # Commit the changes
        conn.commit()
        print("Migration completed successfully!")
    
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        conn.rollback()
        sys.exit(1)
    
    finally:
        # Close the connection
        conn.close()

if __name__ == "__main__":
    migrate_database() 