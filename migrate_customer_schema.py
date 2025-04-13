import os
import sqlite3
from datetime import datetime
from app import db
from config import Config

def migrate_database():
    """
    Migrates the database schema to support the new Customer model 
    and adds customer_id field to DeliveryTransaction
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
            
            # List files in instance directory
            instance_dir = os.path.join(os.getcwd(), 'instance')
            if os.path.exists(instance_dir):
                print(f"Listing files in instance directory:")
                for file in os.listdir(instance_dir):
                    print(f"- {file}")
                    
                    # Use the first .db file found
                    if file.endswith('.db'):
                        db_path = os.path.join(instance_dir, file)
                        print(f"Using database: {db_path}")
                        break
            else:
                print(f"Instance directory not found")
                print(f"Searching for .db files in current directory:")
                for file in os.listdir(os.getcwd()):
                    if file.endswith('.db'):
                        print(f"- {file}")
                        db_path = os.path.join(os.getcwd(), file)
                        print(f"Using database: {db_path}")
                        break
                
                if not os.path.exists(db_path):
                    print("No database file found. Migration aborted.")
                    return
    
    # Connect to SQLite directly
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # List all tables in the database
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"Tables in database: {[table[0] for table in tables]}")
    
    # Check if the customer table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='customer'")
    customer_table_exists = cursor.fetchone() is not None
    
    # Create Customer table if it doesn't exist
    if not customer_table_exists:
        print("Creating Customer table...")
        cursor.execute('''
        CREATE TABLE customer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            phone TEXT NOT NULL,
            email TEXT,
            bike_seller_id INTEGER NOT NULL,
            daily_quantity REAL DEFAULT 0.0,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (bike_seller_id) REFERENCES user (id)
        )
        ''')
        print("Customer table created successfully.")
    
    # Check if delivery_transaction table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='delivery_transaction'")
    delivery_table_exists = cursor.fetchone() is not None
    
    if not delivery_table_exists:
        print("Error: delivery_transaction table does not exist")
        return
    
    # Check if customer_id column exists in delivery_transaction
    cursor.execute("PRAGMA table_info(delivery_transaction)")
    columns = cursor.fetchall()
    column_names = [column[1] for column in columns]
    print(f"Columns in delivery_transaction table: {column_names}")
    
    # Add customer_id column if it doesn't exist
    if 'customer_id' not in column_names:
        print("Adding customer_id column to delivery_transaction table...")
        cursor.execute("ALTER TABLE delivery_transaction ADD COLUMN customer_id INTEGER")
        conn.commit()
        print("Column added successfully.")
    
    # Migrate existing data - create customers from delivery transactions
    print("Migrating existing customers from delivery transactions...")
    
    # Get all unique customer data from delivery_transaction
    cursor.execute('''
    SELECT DISTINCT bike_seller_id, customer_name, customer_address
    FROM delivery_transaction
    ''')
    unique_customers = cursor.fetchall()
    print(f"Found {len(unique_customers)} unique customers to migrate")
    
    # Dictionary to track created customers
    customer_mapping = {}  # (bike_seller_id, customer_name, customer_address) -> customer_id
    
    # Create Customer records
    for bike_seller_id, customer_name, customer_address in unique_customers:
        print(f"Processing customer: {customer_name} for bike seller {bike_seller_id}")
        # Parse phone number and daily quantity from address if they exist
        phone = ""
        daily_quantity = 0.0
        address = customer_address
        
        if " | Phone:" in address:
            parts = address.split(" | Phone:")
            address = parts[0].strip()
            
            # Extract phone
            phone_part = parts[1]
            if " | Daily qty:" in phone_part:
                phone_value, qty_part = phone_part.split(" | Daily qty:")
                phone = phone_value.strip()
                
                # Extract daily quantity
                try:
                    qty_value = qty_part.replace(" L", "").strip()
                    daily_quantity = float(qty_value)
                except ValueError:
                    daily_quantity = 0.0
            else:
                phone = phone_part.strip()
        elif " | Daily qty:" in address:
            parts = address.split(" | Daily qty:")
            address = parts[0].strip()
            
            # Extract daily quantity
            try:
                qty_value = parts[1].replace(" L", "").strip()
                daily_quantity = float(qty_value)
            except ValueError:
                daily_quantity = 0.0
        
        # Check if name indicates inactive status
        is_active = not customer_name.startswith('[INACTIVE]')
        if not is_active:
            # Remove [INACTIVE] prefix
            customer_name = customer_name.replace('[INACTIVE] ', '').strip()
        
        # Create a new customer record
        cursor.execute('''
        INSERT INTO customer (name, address, phone, bike_seller_id, daily_quantity, is_active, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            customer_name, 
            address, 
            phone, 
            bike_seller_id, 
            daily_quantity, 
            is_active, 
            datetime.utcnow(), 
            datetime.utcnow()
        ))
        
        # Get the ID of the newly created customer
        customer_id = cursor.lastrowid
        print(f"Created customer with ID {customer_id}")
        
        # Store mapping for updating delivery transactions
        customer_mapping[(bike_seller_id, customer_name, customer_address)] = customer_id
    
    conn.commit()
    print(f"Created {len(customer_mapping)} customer records.")
    
    # Update delivery_transaction records with customer IDs
    for (bike_seller_id, customer_name, customer_address), customer_id in customer_mapping.items():
        cursor.execute('''
        UPDATE delivery_transaction 
        SET customer_id = ? 
        WHERE bike_seller_id = ? AND customer_name = ? AND customer_address = ?
        ''', (customer_id, bike_seller_id, customer_name, customer_address))
        
        # Get count of updated rows
        cursor.execute('''
        SELECT COUNT(*) FROM delivery_transaction 
        WHERE bike_seller_id = ? AND customer_name = ? AND customer_address = ?
        ''', (bike_seller_id, customer_name, customer_address))
        count = cursor.fetchone()[0]
        print(f"Updated {count} transactions for customer {customer_name} (ID: {customer_id})")
    
    conn.commit()
    print("Updated delivery_transaction records with customer IDs.")
    
    # Create index on customer_id in delivery_transaction
    cursor.execute('''
    CREATE INDEX IF NOT EXISTS idx_delivery_customer_id 
    ON delivery_transaction(customer_id)
    ''')
    
    # Close the connection
    conn.close()
    print("Migration completed successfully.")

if __name__ == "__main__":
    migrate_database() 