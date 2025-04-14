import sqlite3
import os

def check_database_structure():
    """
    Utility function to check the database structure and tables
    """
    print("Checking database structure...")
    
    # Try to locate the database file
    potential_paths = ['app.db', 'instance/app.db']
    db_path = None
    
    for path in potential_paths:
        if os.path.exists(path):
            db_path = path
            print(f"Found database at: {os.path.abspath(path)}")
            break
    
    if not db_path:
        print("ERROR: Could not find database file!")
        return
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get list of all tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"Found {len(tables)} tables in the database:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Check for specific required tables
        required_tables = [
            'user', 
            'milk_transaction', 
            'delivery_transaction', 
            'purchase_transaction',
            'inventory_transaction',
            'milk_sale_transaction',
            'dairy_stock'
        ]
        
        missing_tables = []
        for table in required_tables:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}';")
            if not cursor.fetchone():
                missing_tables.append(table)
        
        if missing_tables:
            print("\nWARNING: The following required tables are missing:")
            for table in missing_tables:
                print(f"  - {table}")
            print("\nYou may need to create these tables with a migration script.")
        else:
            print("\nAll required tables are present in the database.")
        
        # Check table structure for milk_sale_transaction if it exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='milk_sale_transaction';")
        if cursor.fetchone():
            print("\nChecking structure of milk_sale_transaction table:")
            cursor.execute("PRAGMA table_info(milk_sale_transaction);")
            columns = cursor.fetchall()
            for column in columns:
                # Format: (cid, name, type, notnull, dflt_value, pk)
                print(f"  - {column[1]} ({column[2]})")
        
        # Check table structure for database statistics
        for table in required_tables:
            if table not in missing_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                print(f"Table '{table}' has {count} rows.")
        
        conn.close()
        
    except Exception as e:
        print(f"ERROR checking database: {str(e)}")

if __name__ == "__main__":
    check_database_structure() 