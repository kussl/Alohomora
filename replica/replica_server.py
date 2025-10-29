from flask import Flask, jsonify, request
from dbconnector import DBConnector
from dbcreator import create_session_db
import datetime
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import hashlib

app = Flask(__name__)

# Load configuration
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    default_config = {
        "replica": {
            "group_id": "group_1",
            "main_server_url": "http://localhost:8000",
            "port": 9456,
            "sync_interval": 2,  # Faster sync for experiments (was 30)
            "replica_id": "replica1",
            "cache_hit_simulation": 0.70  # Simulate 70% cache hit rate
        },
        "database": {
            "name": "replica1_sessions.db"
        }
    }
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Config file not found. Creating {config_path} with defaults.")
        try:
            with open(config_path, 'w') as f:
                json.dump(default_config, f, indent=2)
            print("✓ Default config file created successfully.")
        except Exception as e:
            print(f"Could not create config file: {e}")
        return default_config
    except json.JSONDecodeError as e:
        print(f"Error parsing config file: {e}. Using defaults.")
        return default_config

config = load_config()

# Initialize database with all required tables
def init_database():
    """Initialize replica database with all required tables"""
    try:
        db_connector_temp = DBConnector(config["database"]["name"])
        connection = db_connector_temp.get_db_connection()
        create_session_db(connection, config["database"]["name"])
        pass  # Database initialized successfully
    except Exception as e:
        print(f"[INIT] Database initialization warning: {e}")  # Keep errors only

# Initialize database on startup
init_database()

# Create db_connector after initialization
db_connector = DBConnector(config["database"]["name"])

# Replica configuration from config file
REPLICA_CONFIG = config["replica"]

# Setup request/response logging
ENABLE_REQUEST_LOGGING = True 

def setup_logging():
    if not ENABLE_REQUEST_LOGGING:
        class _Dummy:
            def info(self, *a, **k):
                pass
        return _Dummy()
    log_file = os.path.join(os.path.dirname(__file__), 'replica1_requests.log')
    handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=0)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    logger = logging.getLogger('replica_requests')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

def setup_generic_logger():
    log_file = os.path.join(os.path.dirname(__file__), 'replica1_generic.log')
    handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=0)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    logger = logging.getLogger('replica_generic')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    # Add a convenience method: .log_anything(obj)
    def log_anything(obj):
        try:
            logger.info(str(obj))
        except Exception as e:
            logger.error(f"Logging failed: {e}")

    logger.log_anything = log_anything
    return logger


request_logger = setup_logging()
generic_logger = setup_generic_logger()

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
   return jsonify(message="Hello from Replica1!", replica_id=REPLICA_CONFIG["replica_id"])

@app.route("/test_endpoint", methods=["POST"])
def test_endpoint():
   """Simple test endpoint to verify POST methods work"""
   return jsonify(message="POST method works on replica", status="success")

@app.route("/register_system", methods=["POST"])
def register_system():
   """Register a system with this replica - requires admin key"""
   data = request.get_json()

   if not data:
      return jsonify(error="No JSON data provided"), 400

   # Check admin key
   admin_key = data.get("admin_key")
   expected_admin_key = config.get("admin", {}).get("key")
   if not admin_key or not expected_admin_key or admin_key != expected_admin_key:
      return jsonify(error="Invalid or missing admin key"), 403

   required_fields = ["system_name", "public_key"]
   for field in required_fields:
      if field not in data:
         return jsonify(error=f"Missing required field: {field}"), 400

   if not isinstance(data.get("system_name"), str) or not data["system_name"].strip():
      return jsonify(error="system_name must be a non-empty string"), 400

   if not isinstance(data.get("public_key"), str) or not data["public_key"].strip():
      return jsonify(error="public_key must be a non-empty string"), 400

   import uuid
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

@app.route("/system/name/<system_name>", methods=["GET"])
def get_system_by_name(system_name):
   if not system_name or not system_name.strip():
      return jsonify(error="Invalid system_name"), 400
   
   system_info = db_connector.fetch_system_by_name(system_name)
   if system_info:
      return jsonify(system_info), 200
   else:
      return jsonify(error="System not found"), 404


from itertools import count
c = count()
def log(line, path):
    if next(c) % 100 == 0: open(path, "w").close()  # clear every 100 writes
    with open(path, "a") as f:
        print(line, file=f)

def format_query(sql, params):
    """Return an executable SQL string with parameters interpolated for debugging only."""
    for p in params:
        if isinstance(p, str):
            p_safe = "'" + p.replace("'", "''") + "'"   # escape quotes
        elif p is None:
            p_safe = "NULL"
        else:
            p_safe = str(p)
        sql = sql.replace("?", p_safe, 1)
    return sql


@app.route("/shared_session_inquiry", methods=["POST"])
def shared_session_inquiry():
    """DEBUG: Fetch one row from shared_tokens for testing"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify(error="No JSON data provided"), 400

    #original query no system ID check -- just to change code. 
    query = """
        SELECT user_id, created_at, expires_at 
        FROM shared_tokens
        WHERE user_id = ?
          AND token_id = ?
          AND created_at IS NOT NULL
        LIMIT 1
    """


    #AND (strftime('%s','now') - strftime('%s', replace(substr(created_at,1,19),'T',' '))) <= 120
    params = (data["user_id"], data["token"]) #, data["system_id"])

   #  #simplified debug query
   #  query = "SELECT user_id, created_at, expires_at FROM shared_tokens LIMIT 1"
   #  params = ()

    try:
        conn = db_connector.get_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
    except Exception as ex:
        generic_logger.log_anything(f"[ERROR] DB query failed: {ex}")
        return jsonify(message="Database error"), 500

    generic_logger.log_anything("[DEBUG] Raw SQL to test:\n" + format_query(query, params))
    generic_logger.log_anything(f"[DEBUG] REPLICA RESULT: {results}")

    return jsonify(session_exists=bool(results), sessions=results), 200


# def shared_session_inquiry():
#     """Check if a valid shared session exists for given system/user/token"""
#     data = request.get_json(silent=True)
#     if not data:
#         return jsonify(error="No JSON data provided"), 400

#     missing = [f for f in ("system_id", "user_id", "token") if f not in data]
#     if missing:
#         return jsonify(error=f"Missing required field: {', '.join(missing)}"), 400

#     system_id, user_id, token_id = data["system_id"], data["user_id"], data["token"]

#     query = """
#         SELECT user_id, created_at, expires_at 
#         FROM shared_tokens
#         WHERE user_id = ?
#           AND token_id = ?
#           AND system_id = ?
#           AND created_at IS NOT NULL
#           AND (strftime('%s','now') - strftime('%s', replace(substr(created_at,1,19),'T',' '))) <= 120
#         LIMIT 1
#     """
#     params = (user_id, token_id, system_id)

#     try:
#         conn = db_connector.get_db_connection()
#         cursor = conn.cursor()
#         cursor.execute(query, params)
#         results = cursor.fetchall()
#         conn.close()
#     except Exception as ex:
#         generic_logger.log_anything(f"[ERROR] DB query failed: {ex}")
#         return jsonify(message="Database error"), 500

#     generic_logger.log_anything(f"REPLICA QUERY: {query.strip()} | params={params}")
#     generic_logger.log_anything(f"REPLICA RESULT: {results}")

#     if results:
#         return jsonify(
#             session_exists=True,
#             sessions=[{
#                 "workflow_id": "query",
#                 "user_id": user_id,
#                 "metadata": results,
#                 "query": query.strip()
#             }]
#         ), 200
#     return jsonify(session_exists=False), 200
 
   
# def shared_session_inquiry_bias():
#    """Allow registered systems to inquire about shared sessions"""
#    data = request.get_json()

#    if not data:
#       return jsonify(error="No JSON data provided"), 400

#    required_fields = ["system_id", "user_id", "token"]
#    for field in required_fields:
#       if field not in data:
#          return jsonify(error=f"Missing required field: {field}"), 400

#    system_id = data["system_id"]
#    user_id = data["user_id"]
#    token = data["token"]

#    # Simulate cache hit with configured probability
#    import random
#    cache_hit_probability = config.get("replica", {}).get("cache_hit_simulation", 0.70)

#    # Create biased list: 70% heads, 30% tails
#    num_heads = int(cache_hit_probability * 100)
#    num_tails = 100 - num_heads
#    biased_list = ['hit'] * num_heads + ['miss'] * num_tails

#    # Draw uniformly from the list
#    result = random.choice(biased_list)

#    if result == 'hit':
#       # Simulate cache hit - return success
#       sessions = [{
#          "workflow_id": "simulated",
#          "user_id": user_id,
#          "created_at": datetime.datetime.now().isoformat(),
#          "expires_at": (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat(),
#          "metadata": None
#       }]
#       return jsonify(session_exists=True, sessions=sessions), 200
#    else:
#       # Simulate cache miss
#       return jsonify(session_exists=False), 200 


# def shared_session_inquiry2():
#    """Allow registered systems to inquire about shared sessions"""
#    data = request.get_json()
   
#    if not data:
#       return jsonify(error="No JSON data provided"), 400
   
#    required_fields = ["system_id", "user_id", "token"]
#    for field in required_fields:
#       if field not in data:
#          return jsonify(error=f"Missing required field: {field}"), 400

#    system_id = data["system_id"]
#    user_id = data["user_id"]
#    token = data["token"]

#    # Hash the token to match database storage (tokens are stored as SHA256 hashes for security)
#    token_hash = hashlib.sha256(token.encode()).hexdigest()

#    # Validate system exists and is registered
#    system_info = db_connector.fetch_system_info(system_id)
#    if not system_info:
#       return jsonify(error="System not found"), 404

#    # Get tokens associated with this user and find workflows the system participates in
#    try:
#       conn = db_connector.get_db_connection()
#       cursor = conn.cursor()

#       # Find the SPECIFIC token for this user where the system participates in the workflow
#       current_time = datetime.datetime.now().isoformat()
#       cursor.execute('''
#          SELECT DISTINCT st.workflow_id, st.user_id, st.created_at, st.expires_at, st.metadata
#          FROM shared_tokens st
#          JOIN workflows w ON st.workflow_id = w.workflow_id
#          JOIN system_functions sf ON w.group_id = sf.group_id
#          WHERE st.user_id = ? AND sf.system_id = ? AND st.token_hash = ? AND st.expires_at > ?
#       ''', (user_id, system_id, token_hash, current_time))
      
#       results = cursor.fetchall()
#       conn.close()
      
#       if not results:
#          return jsonify(session_exists=False), 200
      
#       # Return session information for workflows the system participates in
#       sessions = []
#       for result in results:
#          sessions.append({
#             "workflow_id": result[0],
#             "user_id": result[1],
#             "created_at": result[2],
#             "expires_at": result[3],
#             "metadata": json.loads(result[4]) if result[4] else None
#          })
      
#       return jsonify(session_exists=True, sessions=sessions), 200
      
#    except Exception:
#       return jsonify(error="Failed to query sessions"), 500

if __name__ == "__main__":
   print(f"Starting Replica Server for group {REPLICA_CONFIG['group_id']}...")
   print(f"Main server: {REPLICA_CONFIG['main_server_url']}")
   print(f"Replica server: http://0.0.0.0:{REPLICA_CONFIG['port']}")
   print(f"Note: Run sync_replica.py separately to sync data from main server")

   app.run(debug=True, host='0.0.0.0', port=REPLICA_CONFIG['port'], threaded=True, use_reloader=False)
