import os
import sqlite3
from datetime import datetime
from config import Config

def migrate_database():
    """
    Adds a created_at column to the delivery_transaction table
    and sets it to the same value as the date column
    """
    # Get the database path
    db_uri = Config.SQLALCHEMY_DATABASE_URI
    db_path = db_uri.replace('sqlite:///', '')
    
    print(f"Database URI: {db_uri}")
    print(f"Migrating database at: {db_path}")
    
    # Check if the file exists
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at {db_path}")
        print(f"Current working directory: {os.getcwd()}")
        
        # Try relative path
        relative_path = os.path.join(os.getcwd(), 'instance', 'dairy.db')
        if os.path.exists(relative_path):
            print(f"Found database at: {relative_path}")
            db_path = relative_path
        else:
            print(f"Database not found at {relative_path}")
            return
    
    # Connect to SQLite directly
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if delivery_transaction table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='delivery_transaction'")
    delivery_table_exists = cursor.fetchone() is not None
    
    if not delivery_table_exists:
        print("Error: delivery_transaction table does not exist")
        return
    
    # Check if created_at column exists in delivery_transaction
    cursor.execute("PRAGMA table_info(delivery_transaction)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    print(f"Columns in delivery_transaction table: {column_names}")
    
    # Add created_at column if it doesn't exist
    if 'created_at' not in column_names:
        print("Adding created_at column to delivery_transaction table...")
        cursor.execute("ALTER TABLE delivery_transaction ADD COLUMN created_at TIMESTAMP")
        
        # Update created_at to be equal to date for existing records
        print("Updating created_at to match date column...")
        cursor.execute("UPDATE delivery_transaction SET created_at = date")
        
        conn.commit()
        print("Column added and updated successfully.")
    else:
        print("created_at column already exists.")
    
    # For debugging: show some records after update
    cursor.execute("""
    SELECT id, date, created_at FROM delivery_transaction LIMIT 5
    """)
    sample_records = cursor.fetchall()
    print("\nSample records after update:")
    for record in sample_records:
        print(f"ID: {record[0]}, date: {record[1]}, created_at: {record[2]}")
    
    # Close the connection
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate_database() 