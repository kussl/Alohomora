from flask import Flask, jsonify, request
from dbconnector import DBConnector
import uuid
import datetime
import requests
import json
import os
import logging
from logging.handlers import RotatingFileHandler

# Disable verbose request/response logging during experiments
ENABLE_REQUEST_LOGGING = False

app = Flask(__name__)

# Load configuration
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    default_config = {
        "alohomora": {
            "main_server_url": "https://main.datarivers.io",
            "replica_url": "https://replica1.datarivers.io",
            "timeout": 10
        },
        "app": {
            "host": "0.0.0.0",
            "port": 8001,
            "debug": True
        },
        "database": {
            "name": "app1db.db"
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

# Initialize database connector with config
db_connector = DBConnector(config["database"]["name"])

# Setup request/response logging
def setup_logging():
    if not ENABLE_REQUEST_LOGGING:
        class _Dummy:
            def info(self, *a, **k):
                pass
        return _Dummy()
    log_file = os.path.join(os.path.dirname(__file__), 'app1_requests.log')
    handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=0)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
    logger = logging.getLogger('app1_requests')
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

@app.route("/register_token", methods=["POST"])
def register_token():
   """Register a token with alohomora server"""
   data = request.get_json()
   
   if not data:
      return jsonify(error="No JSON data provided"), 400
   
   required_fields = ["session_id", "token", "workflow_id", "function_id", "system_id"]
   for field in required_fields:
      if field not in data:
         return jsonify(error=f"Missing required field: {field}"), 400
   
   session_id = data["session_id"]
   token = data["token"]
   workflow_id = data["workflow_id"]
   function_id = data["function_id"]
   system_id = data["system_id"]
   user_id = data.get("user_id")
   
   # Validate that session exists locally
   session = db_connector.get_session(session_id)
   if not session:
      return jsonify(error="Session not found"), 404
   
   # Use user_id from session if not provided
   if not user_id:
      user_id = session.get("user_id")
   
   # Prepare data for alohomora
   alohomora_data = {
      "system_id": system_id,
      "token": token,
      "workflow_id": workflow_id,
      "function_id": function_id,
      "user_id": user_id,
      "token_metadata": data.get("token_metadata", {})
   }
   
   try:
      # Call alohomora's record_token endpoint using config
      alohomora_main_url = config["alohomora"]["main_server_url"]
      alohomora_timeout = config["alohomora"]["timeout"]
      alohomora_url = f"{alohomora_main_url}/record_token"
      headers = {"Content-Type": "application/json"}
      
      response = requests.post(alohomora_url, json=alohomora_data, headers=headers, timeout=alohomora_timeout)
      
      if response.status_code == 201:
         alohomora_result = response.json()
         return jsonify(
            message="Token registered successfully with alohomora",
            alohomora_token_id=alohomora_result.get("token_id"),
            session_id=session_id
         ), 201
      else:
         return jsonify(
            error="Failed to register token with alohomora",
            alohomora_error=response.json().get("error", "Unknown error"),
            alohomora_status=response.status_code
         ), 502
         
   except requests.exceptions.RequestException as e:
      return jsonify(
         error="Failed to connect to alohomora server",
         details=str(e)
      ), 503

def validate_token(user_id, system_id, token):
   """Validate token by checking replica first, then main server"""

   replica_url = config["alohomora"]["replica_url"]
   main_url = config["alohomora"]["main_server_url"]
   timeout = config["alohomora"]["timeout"]

   inquiry_data = {
      "system_id": system_id,
      "user_id": user_id,
      "token": token
   }

   # Try replica first
   try:
      response = requests.post(
         f"{replica_url}/shared_session_inquiry",
         json=inquiry_data,
         timeout=timeout,
         verify=True
      )
      #change 
      if response.status_code == 200:
         data = response.json()
         if data.get("session_exists", False):
            return {"valid": True, "source": "replica", "sessions": data.get("sessions", [])}
   except Exception as e:
      print(f"Replica query failed: {e}")

   # Fallback to main server
   try:
      response = requests.post(
         f"{main_url}/shared_session_inquiry",
         json=inquiry_data,
         timeout=timeout,
         verify=True
      )

      if response.status_code == 200:
         data = response.json()
         if data.get("session_exists", False):
            return {"valid": True, "source": "main", "sessions": data.get("sessions", [])}
   except Exception as e:
      print(f"Main server query failed: {e}")

   return {"valid": False, "source": "none"}


@app.route("/function", methods=["POST"])
def execute_function():
   """Generic function endpoint that validates token and simulates execution"""
   data = request.get_json()

   if not data:
      return jsonify(error="No JSON data provided"), 400

   required_fields = ["function_id", "token", "user_id"]
   for field in required_fields:
      if field not in data:
         return jsonify(error=f"Missing required field: {field}"), 400

   function_id = data["function_id"]
   token = data["token"]
   user_id = data["user_id"]
   system_id = data.get("system_id", "default_system")

   # Validate token
   validation = validate_token(user_id, system_id, token)

   if not validation["valid"]:
      return jsonify(
         success=False,
         error="Token validation failed",
         message="No valid session found", 
      ), 401

   # Simulation: function execution does nothing, just return success
   return jsonify(
      success=True,
      function_id=function_id,
      message="Function executed successfully (simulated)",
      token_source=validation["source"],
      user_id=user_id, 
   ), 200


@app.route("/receive_session_notification", methods=["POST"])
def receive_session_notification():
   """Receive shared session notification from alohomora"""
   data = request.get_json()
   
   if not data:
      return jsonify(error="No JSON data provided"), 400
   
   required_fields = ["token_id", "session_info", "workflow_status"]
   for field in required_fields:
      if field not in data:
         return jsonify(error=f"Missing required field: {field}"), 400
   
   token_id = data["token_id"]
   session_info = data["session_info"]
   workflow_status = data["workflow_status"]
   notification_metadata = data.get("notification_metadata", {})
   
   # Log the received notification
   print(f"Received session notification for token_id: {token_id}")
   print(f"Session info: {session_info}")
   print(f"Workflow status: {workflow_status}")
   
   # Here you could:
   # 1. Store the session info in local database for cross-app validation
   # 2. Update local workflow tracking
   # 3. Trigger local business logic based on the session
   
   try:
      # For now, just acknowledge receipt and log the details
      response_data = {
         "message": "Session notification received successfully",
         "token_id": token_id,
         "processed_at": datetime.datetime.now().isoformat(),
         "local_session_created": False  # Could create local session here if needed
      }
      
      # Optional: Create a local session based on the shared session info
      if session_info.get("create_local_session", False):
         local_session_data = {
            "user_id": session_info.get("user_id", "unknown_shared_user"),
            "data": json.dumps({
               "shared_from_token": token_id,
               "original_session_id": session_info.get("session_id"),
               "workflow_status": workflow_status,
               "notification_metadata": notification_metadata
            })
         }
         
         session_id = str(uuid.uuid4())
         created_at = datetime.datetime.now().isoformat()
         
         local_session = {
            "session_id": session_id,
            "user_id": local_session_data["user_id"],
            "created_at": created_at,
            "last_accessed_at": created_at,
            "expires_at": (datetime.datetime.now() + datetime.timedelta(hours=1)).isoformat(),
            "data": local_session_data["data"]
         }
         
         if db_connector.insert_new_session(local_session):
            response_data["local_session_created"] = True
            response_data["local_session_id"] = session_id
            print(f"Created local session {session_id} based on shared session notification")
      
      return jsonify(response_data), 200
      
   except Exception as e:
      return jsonify(
         error="Failed to process session notification",
         details=str(e)
      ), 500

if __name__ == "__main__":
   app_config = config["app"]
   print(f"Starting app1 server...")
   print(f"Alohomora main server: {config['alohomora']['main_server_url']}")
   print(f"Alohomora replica: {config['alohomora']['replica_url']}")
   print(f"App server: http://{app_config['host']}:{app_config['port']}")
   
   app.run(
      debug=app_config["debug"],
      host=app_config["host"], 
      port=app_config["port"],
      threaded=True,
      use_reloader=False
   ) 
