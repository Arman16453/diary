import sqlite3
import os
from datetime import datetime

def find_database():
    """Find the correct database file"""
    potential_paths = [
        'instance/dairy.db',
        'instance\\dairy.db',
        './instance/dairy.db',
        '.\\instance\\dairy.db',
        'C:/Users/hp/diary/instance/dairy.db',
        'C:\\Users\\hp\\diary\\instance\\dairy.db',
        'instance/app.db',
        'instance\\app.db',
        './instance/app.db',
        '.\\instance\\app.db',
        'C:/Users/hp/diary/instance/app.db',
        'C:\\Users\\hp\\diary\\instance\\app.db',
        'app.db',
        'dairy.db',
        'C:/Users/hp/diary/app.db',
        'C:/Users/hp/diary/dairy.db'
    ]
    
    found_paths = []
    
    for path in potential_paths:
        if os.path.exists(path):
            abs_path = os.path.abspath(path)
            print(f"Found database at: {abs_path}")
            found_paths.append(abs_path)
    
    if not found_paths:
        print("ERROR: Could not find any database file!")
        return None
    
    # Prefer the instance database with user table
    for path in found_paths:
        if 'instance' in path and 'dairy.db' in path:
            try:
                conn = sqlite3.connect(path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
                if cursor.fetchone():
                    print(f"Using database with user table: {path}")
                    conn.close()
                    return path
                conn.close()
            except Exception as e:
                print(f"Error checking {path}: {str(e)}")
    
    # If no instance database with user table found, use the first instance db
    for path in found_paths:
        if 'instance' in path:
            print(f"Using instance database: {path}")
            return path
    
    # If no instance database found, check other dbs for user table
    for path in found_paths:
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user'")
            if cursor.fetchone():
                print(f"Using database with user table: {path}")
                conn.close()
                return path
            conn.close()
        except Exception as e:
            print(f"Error checking {path}: {str(e)}")
    
    # If all else fails, use the first one
    print(f"Using database: {found_paths[0]}")
    return found_paths[0]

def create_milk_sale_transaction_table(db_path):
    """Create the milk_sale_transaction table if it doesn't exist"""
    print(f"\nChecking milk_sale_transaction table in {db_path}...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if the table already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='milk_sale_transaction'")
    if cursor.fetchone():
        print("Table milk_sale_transaction already exists.")
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
    
    # Verify the table structure
    cursor.execute("PRAGMA table_info(milk_sale_transaction);")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"milk_sale_transaction columns: {', '.join(columns)}")
    
    conn.commit()
    conn.close()
    return True

def migrate_database():
    """
    Main migration function
    """
    print("Starting database migration process...")
    print(f"Current directory: {os.getcwd()}")
    
    # Find the database
    db_path = find_database()
    if not db_path:
        return False
    
    # Try to connect to the database to verify it's valid
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [table[0] for table in cursor.fetchall()]
        print(f"\nFound tables: {', '.join(tables)}")
        
        # Check if this is a valid database with expected tables
        expected_tables = ['user']
        found_expected = any(table in tables for table in expected_tables)
        
        if not found_expected:
            print(f"WARNING: This database doesn't have the 'user' table. It may not be the correct database.")
            choice = input("Continue anyway? (y/n): ")
            if choice.lower() != 'y':
                print("Migration aborted.")
                return False
            
        conn.close()
    except Exception as e:
        print(f"ERROR: Could not connect to database: {str(e)}")
        return False
    
    # Create milk_sale_transaction table
    create_milk_sale_transaction_table(db_path)
    
    print("\nMigration completed successfully.")
    return True

if __name__ == "__main__":
    migrate_database() 