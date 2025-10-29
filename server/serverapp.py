from flask import Flask, jsonify, request
from dbconnector import DBConnector
from wfg import WFGraph, Vertex
import uuid
import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import requests
import yaml
import ssl
import hashlib

app = Flask(__name__)

# Load configuration
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

config = load_config()
db_connector = DBConnector(config['database']['path'])

# Logging configuration
ENABLE_REQUEST_LOGGING = True  #config['logging']['enabled']

# Setup request/response logging
def setup_logging():
    if not ENABLE_REQUEST_LOGGING:
        class _Dummy:
            def info(self, *a, **k):
                pass
        return _Dummy()
    log_file = os.path.join(os.path.dirname(__file__), 'server_requests.log')
    handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=0)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    logger = logging.getLogger('requests')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

request_logger = setup_logging()

@app.before_request
def log_request():
    request_data = {
        'method': request.method,
        'url': request.url,
        'headers': dict(request.headers),
        'body': request.get_data(as_text=True) if request.data else None
    }
    request_logger.info(f"REQUEST: {json.dumps(request_data)}")

@app.after_request
def log_response(response):
    response_data = {
        'status': response.status_code,
        'headers': dict(response.headers),
        'body': response.get_data(as_text=True) if response.data else None
    }
    request_logger.info(f"RESPONSE: {json.dumps(response_data)}")
    return response

@app.route("/hello")
def hello_json():
   return jsonify(message="Hello, World!")

@app.route("/new_session", methods=["POST"])
def create_session():
   data = request.get_json()
   
   if not data:
      return jsonify(error="No JSON data provided"), 400
   
   required_fields = ["user_id"]
   for field in required_fields:
      if field not in data:
         return jsonify(error=f"Missing required field: {field}"), 400
   
   if not isinstance(data.get("user_id"), str) or not data["user_id"].strip():
      return jsonify(error="user_id must be a non-empty string"), 400
   
   session_id = str(uuid.uuid4())
   created_at = datetime.datetime.now().isoformat()
   
   session = {
      "session_id": session_id,
      "user_id": data["user_id"],
      "created_at": created_at,
      "last_accessed_at": created_at,
      "expires_at": (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat(),
      "data": data.get("data", "")
   }
   
   if db_connector.insert_new_session(session):
      return jsonify(session_id=session_id), 201
   else:
      return jsonify(error="Failed to create session"), 500

@app.route("/register_system", methods=["POST"])
def register_system():
   data = request.get_json()

   if not data:
      return jsonify(error="No JSON data provided"), 400

   # Check admin key
   admin_key = data.get("admin_key")
   if not admin_key or admin_key != config.get("admin", {}).get("key"):
      return jsonify(error="Invalid or missing admin key"), 403

   required_fields = ["system_name", "public_key"]
   for field in required_fields:
      if field not in data:
         return jsonify(error=f"Missing required field: {field}"), 400
   
   if not isinstance(data.get("system_name"), str) or not data["system_name"].strip():
      return jsonify(error="system_name must be a non-empty string"), 400
      
   if not isinstance(data.get("public_key"), str) or not data["public_key"].strip():
      return jsonify(error="public_key must be a non-empty string"), 400
   
   system_id = str(uuid.uuid4())
   created_at = datetime.datetime.now().isoformat()
   
   system = {
      "system_id": system_id,
      "system_name": data["system_name"],
      "group_id": data.get("group_id"),
      "public_key": data["public_key"],
      "callback_url": data.get("callback_url"),
      "created_at": created_at,
      "last_seen_at": created_at
   }
   
   if db_connector.insert_system(system):
      return jsonify(system_id=system_id), 201
   else:
      return jsonify(error="Failed to register system"), 500

@app.route("/system/<system_id>", methods=["GET"])
def get_system_info(system_id):
   if not system_id or not system_id.strip():
      return jsonify(error="Invalid system_id"), 400
   
   system_info = db_connector.fetch_system_info(system_id)
   
   if system_info:
      return jsonify(system_info), 200
   else:
      return jsonify(error="System not found"), 404

@app.route("/register_workflow", methods=["POST"])
def register_workflow():
   data = request.get_json()
   
   if not data:
      return jsonify(error="No JSON data provided"), 400
   
   required_fields = ["system_id", "workflow_graph"]
   for field in required_fields:
      if field not in data:
         return jsonify(error=f"Missing required field: {field}"), 400
   
   system_id = data["system_id"]
   workflow_data = data["workflow_graph"]
   
   # Get system info to verify group membership
   system_info = db_connector.fetch_system_info(system_id)
   if not system_info:
      return jsonify(error="System not found"), 404
   
   group_id = system_info["group_id"]
   if not group_id:
      return jsonify(error="System must belong to a group to register workflows"), 400
   
   # Get all functions in the group
   group_functions = db_connector.fetch_system_functions_by_group(group_id)
   group_function_ids = {func["function_id"] for func in group_functions}
   
   # Reconstruct WFGraph from JSON
   try:
      wfg = WFGraph()
      
      # Add vertices
      if "vertices" in workflow_data:
         for vertex_id, vertex_data in workflow_data["vertices"].items():
            vertex = Vertex(vertex_id, vertex_data.get("f"), vertex_data.get("s"))
            wfg.add_vertex(vertex)
      
      # Validate all vertices are in the submitting system's group
      for vertex_id in wfg.vertices:
         if vertex_id not in group_function_ids:
            return jsonify(error=f"Function {vertex_id} not found in system's group"), 403
      
      # Add edges
      if "adj" in workflow_data:
         for from_vertex, to_vertices in workflow_data["adj"].items():
            for to_vertex in to_vertices:
               wfg.add_edge(from_vertex, to_vertex)
      
      # Store workflow in database
      workflow_id = str(uuid.uuid4())
      created_at = datetime.datetime.now().isoformat()
      
      # Store workflow metadata
      workflow_record = {
         "workflow_id": workflow_id,
         "system_id": system_id,
         "group_id": group_id,
         "created_at": created_at,
         "workflow_data": json.dumps(workflow_data)
      }
      
      if not db_connector.insert_workflow(workflow_record):
         return jsonify(error="Failed to register workflow"), 500
      
      # Store workflow edges if any exist
      edges = []
      for from_vertex, to_vertices in wfg.adj.items():
         for to_vertex in to_vertices:
            edge = {
               "edge_id": str(uuid.uuid4()),
               "workflow_id": workflow_id,
               "from_function_id": from_vertex,
               "to_function_id": to_vertex,
               "group_id": group_id,
               "created_at": created_at
            }
            edges.append(edge)
      
      if edges:
         if not db_connector.insert_workflow_edges(edges):
            return jsonify(error="Failed to register workflow edges"), 500
      
      return jsonify(workflow_id=workflow_id), 201
         
   except Exception as e:
      return jsonify(error=f"Invalid workflow format: {str(e)}"), 400

@app.route("/register_function", methods=["POST"])
def register_function():
   data = request.get_json()
   
   if not data:
      return jsonify(error="No JSON data provided"), 400
   
   required_fields = ["system_id", "function_name", "url"]
   for field in required_fields:
      if field not in data:
         return jsonify(error=f"Missing required field: {field}"), 400
   
   system_id = data["system_id"]
   
   # Verify system exists and get group_id
   system_info = db_connector.fetch_system_info(system_id)
   if not system_info:
      return jsonify(error="System not found"), 404
   
   # Debug: check if group_id exists
   if not system_info.get("group_id"):
      return jsonify(error="System must belong to a group"), 400
   
   function_id = str(uuid.uuid4())
   created_at = datetime.datetime.now().isoformat()
   
   function = {
      "function_id": function_id,
      "system_id": system_id,
      "group_id": system_info["group_id"],
      "function_name": data["function_name"],
      "url": data["url"],
      "created_at": created_at
   }
   
   if db_connector.insert_system_function(function):
      return jsonify(function_id=function_id), 201
   else:
      return jsonify(error="Failed to register function"), 500

@app.route("/system/name/<system_name>", methods=["GET"])
def get_system_by_name(system_name):
   if not system_name or not system_name.strip():
      return jsonify(error="Invalid system_name"), 400
   
   system_info = db_connector.fetch_system_by_name(system_name)
   
   if system_info:
      return jsonify(system_info), 200
   else:
      return jsonify(error="System not found"), 404

@app.route("/record_token", methods=["POST"])
def record_token():
   data = request.get_json()
   
   if not data:
      return jsonify(error="No JSON data provided"), 400
   
   required_fields = ["system_id", "token", "workflow_id", "function_id", "user_id"]
   for field in required_fields:
      if field not in data:
         return jsonify(error=f"Missing required field: {field}"), 400
   
   system_id = data["system_id"]
   token = data["token"]
   workflow_id = data["workflow_id"]
   function_id = data["function_id"]
   user_id = data["user_id"]
   token_metadata = data.get("token_metadata", {})
   
   # Validate input strings
   if not all(isinstance(field, str) and field.strip() for field in [system_id, token, workflow_id, function_id, user_id]):
      return jsonify(error="All required fields must be non-empty strings"), 400
   
   # 1. Verify system exists and get group info
   system_info = db_connector.fetch_system_info(system_id)
   if not system_info:
      return jsonify(error="System not found"), 404
   
   group_id = system_info.get("group_id")
   if not group_id:
      return jsonify(error="System must belong to a group"), 403
   
   # 2. Verify workflow and function relationship
   if not db_connector.verify_workflow_function(workflow_id, function_id, group_id):
      return jsonify(error="Function not found in specified workflow or not accessible by system's group"), 403
   
   # 3. Check token expiration if provided in metadata
   expires_at = token_metadata.get("expires_at")
   if expires_at:
      try:
         expires_datetime = datetime.datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
         if expires_datetime <= datetime.datetime.now(expires_datetime.tzinfo):
            return jsonify(error="Token has already expired"), 400
      except ValueError:
         return jsonify(error="Invalid expires_at format"), 400
   else:
      # Default expiration: 1 hour from now
      expires_at = (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat()
   
   # 4. Hash token and check for duplicates
   token_hash = db_connector.hash_token(token)
   if db_connector.token_exists(token_hash):
      return jsonify(error="Token already exists"), 409

   # 5. Prepare token data for storage
   token_id = token  # Store raw token as token_id
   created_at = datetime.datetime.now().isoformat()

   token_data = {
      "token_id": token_id,
      "system_id": system_id,
      "workflow_id": workflow_id,
      "function_id": function_id,
      "user_id": user_id,
      "token_hash": token_hash,
      "expires_at": expires_at,
      "created_at": created_at,
      "metadata": json.dumps(token_metadata) if token_metadata else None
   }
   
   # 6. Store token in database
   if db_connector.insert_shared_token(token_data):
      # 7. Send notifications to other systems in the workflow (async, best effort)
      try:
         notify_systems_about_token(token_id, system_id, workflow_id, user_id, token_metadata)
      except Exception as e:
         print(f"Warning: Failed to send notifications for token {token_id}: {e}")
         # Don't fail the token recording if notifications fail
      
      return jsonify(token_id=token_id, status="recorded"), 201
   else:
      return jsonify(error="Failed to record token"), 500

def notify_systems_about_token(token_id, system_id, workflow_id, user_id, token_metadata):
   """Send notifications to systems about new token registration"""
   import threading
   
   def send_notifications():
      try:
         # Get systems that should be notified (exclude the system that registered the token)
         notification_systems = db_connector.get_systems_for_notification(workflow_id, exclude_system_id=system_id)
         
         if not notification_systems:
            print(f"No systems to notify for workflow {workflow_id}")
            return
         
         # Get workflow status
         workflow_status = db_connector.get_workflow_instance_status(workflow_id)
         
         # Prepare notification payload
         notification_data = {
            "token_id": token_id,
            "session_info": {
               "user_id": user_id,
               "workflow_id": workflow_id,
               "session_id": None,  # Could be enhanced to include session ID if available
               "create_local_session": True  # Flag to suggest creating local session
            },
            "workflow_status": workflow_status,
            "notification_metadata": {
               "sent_at": datetime.datetime.now().isoformat(),
               "source_system_id": system_id,
               "token_metadata": token_metadata
            }
         }
         
         headers = {"Content-Type": "application/json"}
         
         for system in notification_systems:
            try:
               callback_url = system["callback_url"]
               if not callback_url.endswith("/receive_session_notification"):
                  callback_url = callback_url.rstrip("/") + "/receive_session_notification"
               
               print(f"Sending notification to {system['system_name']} at {callback_url}")
               
               response = requests.post(callback_url, json=notification_data, headers=headers, timeout=5)
               if response.status_code == 200:
                  print(f"Successfully notified {system['system_name']}")
               else:
                  print(f"Failed to notify {system['system_name']}: {response.status_code}")
                  
            except requests.exceptions.RequestException as e:
               print(f"Failed to send notification to {system['system_name']}: {e}")
            except Exception as e:
               print(f"Unexpected error notifying {system['system_name']}: {e}")
      
      except Exception as e:
         print(f"Error in notification thread: {e}")
   
   # Send notifications in a separate thread to not block the response
   thread = threading.Thread(target=send_notifications)
   thread.daemon = True
   thread.start()

@app.route("/shared_session_inquiry", methods=["POST"])
def shared_session_inquiry():
   """Allow registered systems to inquire about shared sessions"""
   data = request.get_json()
   
   if not data:
      return jsonify(error="No JSON data provided"), 400
   
   required_fields = ["system_id", "user_id", "token"]
   for field in required_fields:
      if field not in data:
         return jsonify(error=f"Missing required field: {field}"), 400

   system_id = data["system_id"]
   user_id = data["user_id"]
   token = data["token"]
   token_id = token

   try:
      conn = db_connector.get_db_connection()
      cursor = conn.cursor()

      cursor.execute("""
         SELECT *
         FROM shared_tokens
         WHERE user_id = ?
            AND token_id = ?
            AND system_id = ?
            AND created_at IS NOT NULL
            AND (strftime('%s','now') - strftime('%s', replace(substr(created_at,1,19),'T',' '))) <= 300
         LIMIT 1
      """, (user_id, token_id, system_id))

      results = cursor.fetchall()
      conn.close()

      if not results:
         return jsonify(session_exists=False), 200

      sessions = []
      for row in results:
         sessions.append({
            "workflow_id": row[2],
            "user_id": row[4],
            "created_at": row[7],
            "expires_at": row[6],
            "metadata": json.loads(row[9]) if row[9] else None
         })
      
      return jsonify(session_exists=True, sessions=sessions), 200
      
   except Exception as e:
      return jsonify(error="Failed to query sessions"), 500

@app.route("/replica_sync", methods=["POST"])
def replica_sync():
   """Provide synchronization updates to replica servers"""
   data = request.get_json()
   
   if not data:
      return jsonify(error="No JSON data provided"), 400
   
   required_fields = ["replica_id", "group_id"]
   for field in required_fields:
      if field not in data:
         return jsonify(error=f"Missing required field: {field}"), 400
   
   replica_id = data["replica_id"]
   group_id = data["group_id"]
   last_sync = data.get("last_sync")
   
   # Validate replica is registered (for now, accept any replica_id)
   # In production, you might want to validate the replica is authorized
   print(f"Sync request from replica '{replica_id}' for group '{group_id}'")
   
   try:
      conn = db_connector.get_db_connection()
      cursor = conn.cursor()
      
      # Get all supporting data for the group (for initial sync or when requested)
      is_initial_sync = last_sync is None
      
      # 1. Get systems in the group
      cursor.execute('''
         SELECT system_id, system_name, group_id, public_key, callback_url, created_at, last_seen_at
         FROM systems
         WHERE group_id = ?
      ''', (group_id,))
      systems_results = cursor.fetchall()
      
      systems = []
      for result in systems_results:
         systems.append({
            "system_id": result[0],
            "system_name": result[1],
            "group_id": result[2],
            "public_key": result[3],
            "callback_url": result[4],
            "created_at": result[5],
            "last_seen_at": result[6]
         })
      
      # 2. Get system functions for the group
      cursor.execute('''
         SELECT function_id, system_id, group_id, function_name, url, created_at
         FROM system_functions
         WHERE group_id = ?
      ''', (group_id,))
      functions_results = cursor.fetchall()
      
      functions = []
      for result in functions_results:
         functions.append({
            "function_id": result[0],
            "system_id": result[1],
            "group_id": result[2],
            "function_name": result[3],
            "url": result[4],
            "created_at": result[5]
         })
      
      # 3. Get workflows for the group
      cursor.execute('''
         SELECT workflow_id, system_id, group_id, created_at, workflow_data
         FROM workflows
         WHERE group_id = ?
      ''', (group_id,))
      workflows_results = cursor.fetchall()
      
      workflows = []
      for result in workflows_results:
         workflows.append({
            "workflow_id": result[0],
            "system_id": result[1],
            "group_id": result[2],
            "created_at": result[3],
            "workflow_data": result[4]
         })
      
      # 4. Get workflow edges for the group
      cursor.execute('''
         SELECT edge_id, workflow_id, from_function_id, to_function_id, group_id, created_at
         FROM workflow_edges
         WHERE group_id = ?
      ''', (group_id,))
      edges_results = cursor.fetchall()
      
      workflow_edges = []
      for result in edges_results:
         workflow_edges.append({
            "edge_id": result[0],
            "workflow_id": result[1],
            "from_function_id": result[2],
            "to_function_id": result[3],
            "group_id": result[4],
            "created_at": result[5]
         })
      
      # 5. Get shared tokens for the requested group that are newer than last_sync
      # CRITICAL: Only sync valid (non-expired) tokens for this group
      current_time = datetime.datetime.now().isoformat()

      # if last_sync:
      #    cursor.execute('''
      #       SELECT st.token_id, st.system_id, st.workflow_id, st.function_id,
      #              st.user_id, st.token_hash, st.expires_at, st.created_at,
      #              st.last_verified_at, st.metadata
      #       FROM shared_tokens st
      #       JOIN workflows w ON st.workflow_id = w.workflow_id
      #       WHERE w.group_id = ?
      #         AND st.created_at > ?
      #         AND st.expires_at > ?
      #       ORDER BY st.created_at ASC
      #    ''', (group_id, last_sync, current_time))
      # else:
      #    cursor.execute('''
      #       SELECT st.token_id, st.system_id, st.workflow_id, st.function_id,
      #              st.user_id, st.token_hash, st.expires_at, st.created_at,
      #              st.last_verified_at, st.metadata
      #       FROM shared_tokens st
      #       JOIN workflows w ON st.workflow_id = w.workflow_id
      #       WHERE w.group_id = ?
      #         AND st.expires_at > ?
      #       ORDER BY st.created_at ASC
      #    ''', (group_id, current_time))

      SYNC_LIMIT = 100
      cursor.execute(f'''
         SELECT st.token_id, st.system_id, st.workflow_id, st.function_id,
               st.user_id, st.token_hash, st.expires_at, st.created_at,
               st.last_verified_at, st.metadata
         FROM shared_tokens st
         JOIN workflows w ON st.workflow_id = w.workflow_id
         WHERE w.group_id = ?
         ORDER BY st.created_at DESC
         LIMIT {SYNC_LIMIT}
      ''', (group_id,))

      
      tokens_results = cursor.fetchall()
      conn.close()
      
      shared_tokens = []
      for result in tokens_results:
         shared_tokens.append({
            "token_id": result[0],
            "system_id": result[1],
            "workflow_id": result[2],
            "function_id": result[3],
            "user_id": result[4],
            "token_hash": result[5],
            "expires_at": result[6],
            "created_at": result[7],
            "last_verified_at": result[8],
            "metadata": result[9]
         })
      
      sync_response = {
         "replica_id": replica_id,
         "group_id": group_id,
         "sync_timestamp": datetime.datetime.now().isoformat(),
         "systems": systems,
         "system_functions": functions,
         "workflows": workflows,
         "workflow_edges": workflow_edges,
         "shared_tokens": shared_tokens
      }
      
      print(f"Sending sync data to replica '{replica_id}': {len(systems)} systems, {len(functions)} functions, {len(workflows)} workflows, {len(workflow_edges)} edges, {len(shared_tokens)} tokens")
      return jsonify(sync_response), 200
      
   except Exception as e:
      print(f"Error during replica sync: {e}")
      return jsonify(error="Sync failed"), 500

@app.route("/create_workflow_instance", methods=["POST"])
def create_workflow_instance():
   """Create a new workflow instance"""
   data = request.get_json()

   if not data:
      return jsonify(error="No JSON data provided"), 400

   required_fields = ["workflow_id", "user_id"]
   for field in required_fields:
      if field not in data:
         return jsonify(error=f"Missing required field: {field}"), 400

   workflow_id = data["workflow_id"]
   user_id = data["user_id"]
   session_id = data.get("session_id")
   metadata = data.get("metadata")

   # Validate workflow exists by checking if it has any functions
   workflow_functions = db_connector.get_workflow_functions(workflow_id)
   if not workflow_functions:
      return jsonify(error="Workflow not found"), 404

   # Create workflow instance
   instance_id = db_connector.create_workflow_instance(workflow_id, user_id, session_id, json.dumps(metadata) if metadata else None)
   if instance_id:
      return jsonify(instance_id=instance_id, workflow_id=workflow_id, status="created"), 201
   else:
      return jsonify(error="Failed to create workflow instance"), 500

@app.route("/mark_step_completion", methods=["POST"])
def mark_step_completion():
   """Mark completion of a workflow step by a system"""
   data = request.get_json()
   
   if not data:
      return jsonify(error="No JSON data provided"), 400
   
   required_fields = ["instance_id", "function_id", "system_id"]
   for field in required_fields:
      if field not in data:
         return jsonify(error=f"Missing required field: {field}"), 400
   
   instance_id = data["instance_id"]
   function_id = data["function_id"]
   system_id = data["system_id"]
   result_data = data.get("result_data")
   error_message = data.get("error_message")
   
   # 1. Validate workflow instance exists
   instance = db_connector.get_workflow_instance(instance_id)
   if not instance:
      return jsonify(error="Workflow instance not found"), 404
   
   # 2. Validate system owns the function
   if not db_connector.validate_system_owns_function(system_id, function_id):
      return jsonify(error="System does not own this function"), 403
   
   # 3. Validate function is part of the workflow
   workflow_functions = db_connector.get_workflow_functions(instance["workflow_id"])
   if function_id not in workflow_functions:
      return jsonify(error="Function not part of workflow"), 400
   
   # 4. Mark step completion
   if db_connector.mark_step_completion(instance_id, function_id, system_id, result_data, error_message):
      return jsonify(
         message="Step completion recorded",
         instance_id=instance_id,
         function_id=function_id,
         status="completed" if not error_message else "failed"
      ), 201
   else:
      return jsonify(error="Failed to record step completion"), 500

if __name__ == "__main__":
   app.run(
      debug=config['server']['debug'],
      host=config['server']['host'],
      port=config['server']['port'],
      threaded=True,
      use_reloader=False
   ) 
