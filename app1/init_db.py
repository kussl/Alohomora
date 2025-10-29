#!/usr/bin/env python3

from dbconnector import DBConnector
import os
import sys

def main():
    # Get database name from command line argument or use default
    db_name = sys.argv[1] if len(sys.argv) > 1 else "app1db.db"
    
    print(f"Initializing database: {db_name}")
    
    # Initialize database connector (this will create the database and table)
    db_connector = DBConnector(db_name)
    
    # Check if database file was created
    if os.path.exists(db_name):
        print(f"✓ Database file '{db_name}' created successfully")
        
        # Test database connection
        conn = db_connector.get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sessions';")
            result = cursor.fetchone()
            if result:
                print("✓ Sessions table created successfully")
            else:
                print("✗ Sessions table not found")
            conn.close()
        else:
            print("✗ Failed to connect to database")
    else:
        print(f"✗ Database file '{db_name}' not created")
    
    print("Database initialization complete.")

if __name__ == "__main__":
    main()