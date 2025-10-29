#!/usr/bin/env python3
"""
Initialize replica database with all required tables
"""

from dbcreator import create_session_db
from dbconnector import DBConnector
import os
import sys

def main():
    # Get database name from command line argument or use default
    db_name = sys.argv[1] if len(sys.argv) > 1 else "replica1_sessions.db"
    
    print(f"Initializing replica database: {db_name}")
    
    # Create database with all tables
    DBC = DBConnector(db_name)
    connection = DBC.get_db_connection()
    create_session_db(connection, db_name)
    
    print("✅ Replica database initialized successfully")
    print("The database now includes all required tables:")
    print("  - sessions")
    print("  - groups") 
    print("  - systems")
    print("  - system_functions")
    print("  - workflows")
    print("  - workflow_edges")
    print("  - shared_tokens")
    print("  - workflow_instances")
    print("  - workflow_instance_steps")

if __name__ == "__main__":
    main()