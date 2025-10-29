from dbconnector import *
import sqlite3
import uuid
import datetime

def create_session_db(conn,db_name="replica1_sessions.db"):
    """
    Creates an SQLite database and tables to store web user sessions, system registry, and groups.
    """
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT,
            created_at TEXT,
            last_accessed_at TEXT,
            expires_at TEXT,
            data TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_id TEXT PRIMARY KEY,
            group_name TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS systems (
            system_id TEXT PRIMARY KEY,
            system_name TEXT NOT NULL,
            group_id TEXT,
            public_key TEXT NOT NULL,
            callback_url TEXT,
            created_at TEXT NOT NULL,
            last_seen_at TEXT,
            FOREIGN KEY (group_id) REFERENCES groups(group_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_functions (
            function_id TEXT PRIMARY KEY,
            system_id TEXT NOT NULL,
            group_id TEXT,
            function_name TEXT NOT NULL,
            url TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (system_id) REFERENCES systems(system_id),
            FOREIGN KEY (group_id) REFERENCES groups(group_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workflows (
            workflow_id TEXT PRIMARY KEY,
            system_id TEXT NOT NULL,
            group_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            workflow_data TEXT NOT NULL,
            FOREIGN KEY (system_id) REFERENCES systems(system_id),
            FOREIGN KEY (group_id) REFERENCES groups(group_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workflow_edges (
            edge_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            from_function_id TEXT NOT NULL,
            to_function_id TEXT NOT NULL,
            group_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id),
            FOREIGN KEY (from_function_id) REFERENCES system_functions(function_id),
            FOREIGN KEY (to_function_id) REFERENCES system_functions(function_id),
            FOREIGN KEY (group_id) REFERENCES groups(group_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS shared_tokens (
            token_id TEXT PRIMARY KEY,
            system_id TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            function_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            token_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_verified_at TEXT,
            metadata TEXT,
            FOREIGN KEY (system_id) REFERENCES systems(system_id),
            FOREIGN KEY (function_id) REFERENCES system_functions(function_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workflow_instances (
            instance_id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            session_id TEXT,
            status TEXT NOT NULL DEFAULT 'in_progress',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT,
            metadata TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workflow_instance_steps (
            step_id TEXT PRIMARY KEY,
            instance_id TEXT NOT NULL,
            function_id TEXT NOT NULL,
            system_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            started_at TEXT,
            completed_at TEXT,
            result_data TEXT,
            error_message TEXT,
            FOREIGN KEY (instance_id) REFERENCES workflow_instances(instance_id),
            FOREIGN KEY (function_id) REFERENCES system_functions(function_id),
            FOREIGN KEY (system_id) REFERENCES systems(system_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print(f"Database '{db_name}' and tables created successfully.")

def table_exists(conn, table_name):
    """
    Checks if a table exists in an SQLite database.

    Args:
        table_name (str): The name of the table to check.

    Returns:
        bool: True if the table exists, False otherwise.
    """
    try:
        cursor = conn.cursor()

        # Query sqlite_master to check for the table
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        
        # Fetch the result; if a row is returned, the table exists
        result = cursor.fetchone()
        return result is not None
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        return False
            
if __name__ == "__main__":
   db_name = "replica1_sessions.db"

   # Example usage:
   # 1. Connect to the database
   DBC = DBConnector(db_name) 
   
   connection = DBC.get_db_connection()
   create_session_db(connection, db_name)
   
   sessions = DBC.fetch_all_sessions()
   print(sessions)

   connection.close()
   print("\nDatabase connection closed.")