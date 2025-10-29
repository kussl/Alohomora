import sqlite3

class DBConnector:
    def __init__(self, db_name):
        self.db_name = db_name
        self.init_database()
    
    def get_db_connection(self):
        """
        Establishes and returns a connection object to an SQLite database.
        """
        try:
            conn = sqlite3.connect(self.db_name)
            return conn
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            return None
    
    def init_database(self):
        """
        Initialize the database with sessions table if it doesn't exist.
        """
        conn = self.get_db_connection()
        if conn is None:
            print("Failed to initialize database")
            return
        
        try:
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
            conn.commit()
            conn.close()
        except sqlite3.Error as e:
            print(f"Error creating sessions table: {e}")
            if conn:
                conn.close()
        
    def insert_new_session(self, session):
        """
        Inserts a new session into the sessions table.
        
        Args:
            session (dict): Session data containing session_id, user_id, 
                          created_at, last_accessed_at, expires_at, data
        
        Returns:
            bool: True if insertion successful, False otherwise
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO sessions (session_id, user_id, created_at, last_accessed_at, expires_at, data)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session.get('session_id'),
                session.get('user_id'), 
                session.get('created_at'),
                session.get('last_accessed_at'),
                session.get('expires_at'),
                session.get('data')
            ))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error inserting session: {e}")
            conn.close()
            return False
    
    def get_session(self, session_id):
        """
        Retrieves a session by session_id.
        
        Args:
            session_id (str): The session ID to lookup
            
        Returns:
            dict: Session data or None if not found
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return None
            
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT session_id, user_id, created_at, last_accessed_at, expires_at, data
                FROM sessions 
                WHERE session_id = ?
            ''', (session_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'session_id': result[0],
                    'user_id': result[1],
                    'created_at': result[2],
                    'last_accessed_at': result[3],
                    'expires_at': result[4],
                    'data': result[5]
                }
            return None
        except sqlite3.Error as e:
            print(f"Error fetching session: {e}")
            conn.close()
            return None