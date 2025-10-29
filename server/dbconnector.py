import sqlite3
import hashlib
import datetime
import uuid

class DBConnector:
    def __init__(self,db_name):
        self.db_name = db_name
        pass
    
    def get_db_connection(self):
        """
        Establishes and returns a connection object to an SQLite database.

        Args:
            db_path (str): The path to the SQLite database file.

        Returns:
            sqlite3.Connection: A connection object to the database.
                                Returns None if connection fails.
        """
        try:
            conn = sqlite3.connect(self.db_name)
            return conn
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")
            return None
        
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

    def fetch_data_from_table(self, table_name, columns="*", condition=None):
        """
        Executes a SELECT query on a specified table and returns the results.

        Args:
            conn (sqlite3.Connection): The database connection object.
            table_name (str): The name of the table to query.
            columns (str, optional): The columns to select (e.g., "col1, col2").
                                    Defaults to "*" (all columns).
            condition (str, optional): A WHERE clause condition (e.g., "id = 1").
                                    Defaults to None.

        Returns:
            list: A list of tuples, where each tuple represents a row from the query result.
                Returns an empty list if no data is found or an error occurs.
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return []

        try:
            cursor = conn.cursor()
            query = f"SELECT {columns} FROM {table_name}"
            if condition:
                query += f" WHERE {condition}"

            cursor.execute(query)
            rows = cursor.fetchall()
            return rows
        except sqlite3.Error as e:
            print(f"Error executing query: {e}")
            return []

    def fetch_all_sessions(self):
        """
        Fetches and prints all sessions from the database.
        """
        conn = self.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE expires_at > datetime('now')")
        sessions = cursor.fetchall()
        conn.close()
        return sessions

    def insert_group(self, group):
        """
        Inserts a new group into the groups table.
        
        Args:
            group (dict): Group data containing group_id, group_name, description, created_at
        
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
                INSERT INTO groups (group_id, group_name, description, created_at)
                VALUES (?, ?, ?, ?)
            ''', (
                group.get('group_id'),
                group.get('group_name'),
                group.get('description'),
                group.get('created_at')
            ))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error inserting group: {e}")
            conn.close()
            return False

    def insert_system(self, system):
        """
        Inserts a new system into the systems table.
        
        Args:
            system (dict): System data containing system_id, system_name, group_id, 
                          public_key, created_at, last_seen_at
        
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
                INSERT INTO systems (system_id, system_name, group_id, public_key, callback_url, created_at, last_seen_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                system.get('system_id'),
                system.get('system_name'),
                system.get('group_id'),
                system.get('public_key'),
                system.get('callback_url'),
                system.get('created_at'),
                system.get('last_seen_at')
            ))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error inserting system: {e}")
            conn.close()
            return False

    def fetch_system_info(self, system_id):
        """
        Fetches public system information (no private key leak).
        
        Args:
            system_id (str): The system ID to lookup
            
        Returns:
            dict: System info with system_id, system_name, group_id or None if not found
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return None
            
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT system_id, system_name, group_id 
                FROM systems 
                WHERE system_id = ?
            ''', (system_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'system_id': result[0],
                    'system_name': result[1], 
                    'group_id': result[2]
                }
            return None
        except sqlite3.Error as e:
            print(f"Error fetching system info: {e}")
            conn.close()
            return None

    def insert_system_function(self, function):
        """
        Inserts a new system function into the system_functions table.
        
        Args:
            function (dict): Function data containing function_id, system_id, group_id, 
                           function_name, url, created_at
        
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
                INSERT INTO system_functions (function_id, system_id, group_id, function_name, url, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                function.get('function_id'),
                function.get('system_id'),
                function.get('group_id'),
                function.get('function_name'),
                function.get('url'),
                function.get('created_at')
            ))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error inserting system function: {e}")
            print(f"Function data: {function}")
            conn.close()
            return False

    def insert_workflow_edges(self, edges):
        """
        Inserts workflow edges into the workflow_edges table.
        
        Args:
            edges (list): List of edge dictionaries containing edge_id, workflow_id,
                         from_function_id, to_function_id, group_id, created_at
        
        Returns:
            bool: True if insertion successful, False otherwise
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return False
            
        try:
            cursor = conn.cursor()
            for edge in edges:
                cursor.execute('''
                    INSERT INTO workflow_edges (edge_id, workflow_id, from_function_id, to_function_id, group_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (
                    edge.get('edge_id'),
                    edge.get('workflow_id'),
                    edge.get('from_function_id'),
                    edge.get('to_function_id'),
                    edge.get('group_id'),
                    edge.get('created_at')
                ))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error inserting workflow edges: {e}")
            conn.close()
            return False

    def fetch_system_functions_by_group(self, group_id):
        """
        Fetches all system functions for a given group.
        
        Args:
            group_id (str): The group ID to lookup
            
        Returns:
            list: List of function dictionaries or empty list if none found
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return []
            
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT function_id, system_id, group_id, function_name, url
                FROM system_functions 
                WHERE group_id = ?
            ''', (group_id,))
            results = cursor.fetchall()
            conn.close()
            
            functions = []
            for result in results:
                functions.append({
                    'function_id': result[0],
                    'system_id': result[1],
                    'group_id': result[2],
                    'function_name': result[3],
                    'url': result[4]
                })
            return functions
        except sqlite3.Error as e:
            print(f"Error fetching system functions: {e}")
            conn.close()
            return []

    def fetch_system_by_name(self, system_name):
        """
        Fetches system by name.
        
        Args:
            system_name (str): The system name to lookup
            
        Returns:
            dict: System info or None if not found
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return None
            
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT system_id, system_name, group_id 
                FROM systems 
                WHERE system_name = ?
            ''', (system_name,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'system_id': result[0],
                    'system_name': result[1], 
                    'group_id': result[2]
                }
            return None
        except sqlite3.Error as e:
            print(f"Error fetching system by name: {e}")
            conn.close()
            return None

    def fetch_function_by_name_and_system(self, function_name, system_id):
        """
        Fetches function by name and system ID.
        
        Args:
            function_name (str): The function name to lookup
            system_id (str): The system ID to lookup
            
        Returns:
            dict: Function info or None if not found
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return None
            
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT function_id, function_name, system_id, group_id, url
                FROM system_functions 
                WHERE function_name = ? AND system_id = ?
            ''', (function_name, system_id))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'function_id': result[0],
                    'function_name': result[1],
                    'system_id': result[2],
                    'group_id': result[3],
                    'url': result[4]
                }
            return None
        except sqlite3.Error as e:
            print(f"Error fetching function: {e}")
            conn.close()
            return None

    def verify_workflow_function(self, workflow_id, function_id, group_id):
        """
        Verifies that a function belongs to a workflow and the system's group has access.
        
        Args:
            workflow_id (str): The workflow ID to check
            function_id (str): The function ID to verify
            group_id (str): The group ID of the submitting system
            
        Returns:
            bool: True if function is valid for the workflow and group
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return False
            
        try:
            cursor = conn.cursor()
            # First check if the function exists in the system_functions table with the correct group
            cursor.execute('''
                SELECT function_id FROM system_functions 
                WHERE function_id = ? AND group_id = ?
            ''', (function_id, group_id))
            function_exists = cursor.fetchone()
            
            if not function_exists:
                conn.close()
                return False
            
            # Check if the workflow exists with the correct group
            cursor.execute('''
                SELECT COUNT(*) FROM workflow_edges WHERE workflow_id = ? AND group_id = ?
            ''', (workflow_id, group_id))
            workflow_edge_count = cursor.fetchone()[0]
            
            if workflow_edge_count > 0:
                # Workflow has edges - check if function is part of it
                cursor.execute('''
                    SELECT workflow_id FROM workflow_edges 
                    WHERE workflow_id = ? AND group_id = ? AND (from_function_id = ? OR to_function_id = ?)
                    LIMIT 1
                ''', (workflow_id, group_id, function_id, function_id))
                result = cursor.fetchone()
                conn.close()
                return result is not None
            else:
                # Workflow has no edges (single-node workflow) - just verify the group matches
                # Since we already verified the function exists and belongs to the group,
                # we'll accept any function from the same group for single-node workflows
                conn.close()
                return True
                
        except sqlite3.Error as e:
            print(f"Error verifying workflow function: {e}")
            conn.close()
            return False

    def token_exists(self, token_hash):
        """
        Checks if a token hash already exists in shared_tokens table.
        
        Args:
            token_hash (str): SHA256 hash of the token
            
        Returns:
            bool: True if token exists, False otherwise
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT token_id FROM shared_tokens WHERE token_hash = ? LIMIT 1
            ''', (token_hash,))
            result = cursor.fetchone()
            conn.close()
            
            return result is not None
        except sqlite3.Error as e:
            print(f"Error checking token existence: {e}")
            conn.close()
            return False

    def insert_shared_token(self, token_data):
        """
        Inserts a new shared token into the shared_tokens table.
        
        Args:
            token_data (dict): Token data containing token_id, system_id, workflow_id,
                             function_id, user_id, token_hash, expires_at, created_at, metadata
        
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
                INSERT INTO shared_tokens (token_id, system_id, workflow_id, function_id, 
                                         user_id, token_hash, expires_at, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                token_data.get('token_id'),
                token_data.get('system_id'),
                token_data.get('workflow_id'),
                token_data.get('function_id'),
                token_data.get('user_id'),
                token_data.get('token_hash'),
                token_data.get('expires_at'),
                token_data.get('created_at'),
                token_data.get('metadata')
            ))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error inserting shared token: {e}")
            conn.close()
            return False

    def hash_token(self, token):
        """
        Creates SHA256 hash of a token for secure storage.
        
        Args:
            token (str): The token to hash
            
        Returns:
            str: SHA256 hash of the token
        """
        return hashlib.sha256(token.encode('utf-8')).hexdigest()

    def create_workflow_instance(self, workflow_id, user_id, session_id=None, metadata=None):
        """
        Creates a new workflow instance.
        
        Args:
            workflow_id (str): The workflow ID to instantiate
            user_id (str): The user executing the workflow
            session_id (str, optional): Associated session ID
            metadata (str, optional): Additional metadata as JSON string
            
        Returns:
            str: Instance ID if successful, None otherwise
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return None
            
        try:
            instance_id = str(uuid.uuid4())
            now = datetime.datetime.now().isoformat()
            
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO workflow_instances 
                (instance_id, workflow_id, user_id, session_id, status, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, 'in_progress', ?, ?, ?)
            ''', (instance_id, workflow_id, user_id, session_id, now, now, metadata))
            conn.commit()
            conn.close()
            return instance_id
        except sqlite3.Error as e:
            print(f"Error creating workflow instance: {e}")
            conn.close()
            return None

    def get_workflow_instance(self, instance_id):
        """
        Retrieves a workflow instance by ID.
        
        Args:
            instance_id (str): The instance ID to retrieve
            
        Returns:
            dict: Instance data if found, None otherwise
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return None
            
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT instance_id, workflow_id, user_id, session_id, status, 
                       created_at, updated_at, completed_at, metadata
                FROM workflow_instances 
                WHERE instance_id = ?
            ''', (instance_id,))
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'instance_id': result[0],
                    'workflow_id': result[1],
                    'user_id': result[2],
                    'session_id': result[3],
                    'status': result[4],
                    'created_at': result[5],
                    'updated_at': result[6],
                    'completed_at': result[7],
                    'metadata': result[8]
                }
            return None
        except sqlite3.Error as e:
            print(f"Error fetching workflow instance: {e}")
            conn.close()
            return None

    def mark_step_completion(self, instance_id, function_id, system_id, result_data=None, error_message=None):
        """
        Marks a workflow step as completed.
        
        Args:
            instance_id (str): The workflow instance ID
            function_id (str): The function that was completed
            system_id (str): The system that completed the function
            result_data (str, optional): Result data as JSON string
            error_message (str, optional): Error message if step failed
            
        Returns:
            bool: True if successful, False otherwise
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return False
            
        try:
            now = datetime.datetime.now().isoformat()
            status = 'failed' if error_message else 'completed'
            
            cursor = conn.cursor()
            
            # First check if step already exists
            cursor.execute('''
                SELECT step_id FROM workflow_instance_steps 
                WHERE instance_id = ? AND function_id = ? AND system_id = ?
            ''', (instance_id, function_id, system_id))
            
            existing = cursor.fetchone()
            
            if existing:
                # Update existing step
                cursor.execute('''
                    UPDATE workflow_instance_steps 
                    SET status = ?, completed_at = ?, result_data = ?, error_message = ?
                    WHERE step_id = ?
                ''', (status, now, result_data, error_message, existing[0]))
            else:
                # Create new step
                step_id = str(uuid.uuid4())
                cursor.execute('''
                    INSERT INTO workflow_instance_steps 
                    (step_id, instance_id, function_id, system_id, status, started_at, completed_at, result_data, error_message)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (step_id, instance_id, function_id, system_id, status, now, now, result_data, error_message))
            
            # Update workflow instance timestamp
            cursor.execute('''
                UPDATE workflow_instances 
                SET updated_at = ? 
                WHERE instance_id = ?
            ''', (now, instance_id))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error marking step completion: {e}")
            conn.close()
            return False

    def insert_workflow(self, workflow_data):
        """
        Inserts a workflow into the workflows table.
        
        Args:
            workflow_data (dict): Contains workflow_id, system_id, group_id, created_at, workflow_data
            
        Returns:
            bool: True if successful, False otherwise
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO workflows (workflow_id, system_id, group_id, created_at, workflow_data)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                workflow_data.get('workflow_id'),
                workflow_data.get('system_id'),
                workflow_data.get('group_id'),
                workflow_data.get('created_at'),
                workflow_data.get('workflow_data')
            ))
            conn.commit()
            conn.close()
            return True
        except sqlite3.Error as e:
            print(f"Error inserting workflow: {e}")
            conn.close()
            return False

    def get_workflow_functions(self, workflow_id):
        """
        Gets all functions in a workflow by parsing the stored workflow data.
        
        Args:
            workflow_id (str): The workflow ID
            
        Returns:
            list: List of function IDs in the workflow
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return []
            
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT workflow_data FROM workflows WHERE workflow_id = ?
            ''', (workflow_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                import json
                workflow_data = json.loads(result[0])
                # Extract function IDs from vertices
                if "vertices" in workflow_data:
                    return list(workflow_data["vertices"].keys())
            return []
        except (sqlite3.Error, json.JSONDecodeError) as e:
            print(f"Error fetching workflow functions: {e}")
            conn.close()
            return []

    def validate_system_owns_function(self, system_id, function_id):
        """
        Validates that a system owns a specific function.
        
        Args:
            system_id (str): The system ID
            function_id (str): The function ID
            
        Returns:
            bool: True if system owns function, False otherwise
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return False
            
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT function_id FROM system_functions 
                WHERE function_id = ? AND system_id = ?
            ''', (function_id, system_id))
            
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except sqlite3.Error as e:
            print(f"Error validating function ownership: {e}")
            conn.close()
            return False

    def get_systems_for_notification(self, workflow_id, exclude_system_id=None):
        """
        Gets systems that should be notified about workflow progress.
        Returns systems in the same group that have callback URLs.
        
        Args:
            workflow_id (str): The workflow ID
            exclude_system_id (str, optional): System ID to exclude from notifications
            
        Returns:
            list: List of system info dictionaries with callback URLs
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return []
            
        try:
            cursor = conn.cursor()
            # Get the group_id for this workflow
            cursor.execute('''
                SELECT group_id FROM workflows WHERE workflow_id = ?
            ''', (workflow_id,))
            
            result = cursor.fetchone()
            if not result:
                conn.close()
                return []
                
            group_id = result[0]
            
            # Get all systems in the same group with callback URLs
            if exclude_system_id:
                cursor.execute('''
                    SELECT system_id, system_name, callback_url 
                    FROM systems 
                    WHERE group_id = ? AND callback_url IS NOT NULL AND callback_url != '' AND system_id != ?
                ''', (group_id, exclude_system_id))
            else:
                cursor.execute('''
                    SELECT system_id, system_name, callback_url 
                    FROM systems 
                    WHERE group_id = ? AND callback_url IS NOT NULL AND callback_url != ''
                ''', (group_id,))
            
            results = cursor.fetchall()
            conn.close()
            
            return [{
                'system_id': result[0],
                'system_name': result[1],
                'callback_url': result[2]
            } for result in results]
            
        except sqlite3.Error as e:
            print(f"Error getting systems for notification: {e}")
            conn.close()
            return []

    def get_workflow_instance_status(self, workflow_id):
        """
        Gets the status of workflow instances for a workflow.
        
        Args:
            workflow_id (str): The workflow ID
            
        Returns:
            dict: Summary of workflow instance statuses
        """
        conn = self.get_db_connection()
        
        if conn is None:
            print("Invalid database connection.")
            return {}
            
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_instances,
                    SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed_instances,
                    SUM(CASE WHEN status = 'in_progress' THEN 1 ELSE 0 END) as in_progress_instances,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_instances
                FROM workflow_instances 
                WHERE workflow_id = ?
            ''', (workflow_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'total_instances': result[0],
                    'completed_instances': result[1],
                    'in_progress_instances': result[2],
                    'failed_instances': result[3]
                }
            return {}
            
        except sqlite3.Error as e:
            print(f"Error getting workflow instance status: {e}")
            conn.close()
            return {}