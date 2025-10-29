import requests
import json
import os
import uuid
import datetime

# Load configuration to get the correct BASE_URL
def load_config():
    config_path = os.path.join(os.path.dirname(__file__), '..', 'config.json')
    default_config = {
        "app": {
            "host": "0.0.0.0",
            "port": 8001
        }
    }
    
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_config

config = load_config()
app_config = config.get("app", {"host": "0.0.0.0", "port": 8001})
alohomora_config = config.get("alohomora", {"base_url": "http://localhost:8000"})

# Construct BASE_URL from config
host = app_config["host"]
port = app_config["port"]

# Convert 0.0.0.0 to localhost for testing
if host == "0.0.0.0":
    host = "localhost"

BASE_URL = f"http://{host}:{port}"
ALOHOMORA_URL = alohomora_config["base_url"]

def setup_alohomora_system():
    """Register app1 as a system in alohomora and create test workflow"""
    print("\nSetting up app1 system in alohomora...")
    headers = {"Content-Type": "application/json"}
    
    # Step 1: Register app1 as a system
    system_data = {
        "system_name": "app1_test_system",
        "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC7vbqajDgVcApp1TestKey...",
        "group_id": "test_group_1"
    }
    
    print(f"  Registering app1 system with alohomora ({ALOHOMORA_URL})...")
    try:
        response = requests.post(f"{ALOHOMORA_URL}/register_system", json=system_data, headers=headers)
        if response.status_code == 201:
            system_result = response.json()
            system_id = system_result["system_id"]
            print(f"  ✓ System registered with ID: {system_id}")
        elif response.status_code == 500 and "already exists" in response.text.lower():
            # System might already exist, try to get it by name
            print("  System may already exist, checking...")
            name_response = requests.get(f"{ALOHOMORA_URL}/system/name/app1_test_system")
            if name_response.status_code == 200:
                system_result = name_response.json()
                system_id = system_result["system_id"]
                print(f"  ✓ Using existing system ID: {system_id}")
            else:
                print(f"  ✗ Failed to register or find system: {response.status_code}")
                return None
        else:
            print(f"  ✗ Failed to register system: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Connection error to alohomora: {e}")
        return None
    
    # Step 2: Register a function for this system
    function_data = {
        "system_id": system_id,
        "function_name": "create_session",
        "url": "/new_session"
    }
    
    print("  Registering function...")
    try:
        response = requests.post(f"{ALOHOMORA_URL}/register_function", json=function_data, headers=headers)
        if response.status_code == 201:
            function_result = response.json()
            function_id = function_result["function_id"]
            print(f"  ✓ Function registered with ID: {function_id}")
        else:
            print(f"  ✗ Failed to register function: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Connection error: {e}")
        return None
    
    # Step 3: Create a simple workflow
    workflow_data = {
        "system_id": system_id,
        "workflow_graph": {
            "vertices": {
                function_id: {"f": "create_session", "s": "app1_test_system"}
            },
            "adj": {
                function_id: []
            }
        }
    }
    
    print("  Creating test workflow...")
    try:
        response = requests.post(f"{ALOHOMORA_URL}/register_workflow", json=workflow_data, headers=headers)
        if response.status_code == 201:
            workflow_result = response.json()
            workflow_id = workflow_result["workflow_id"]
            print(f"  ✓ Workflow created with ID: {workflow_id}")
            
            return {
                "system_id": system_id,
                "function_id": function_id, 
                "workflow_id": workflow_id
            }
        else:
            print(f"  ✗ Failed to create workflow: {response.status_code} - {response.text}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"  ✗ Connection error: {e}")
        return None

def test_session_creation_and_registration():
    print("Testing app1 session creation and token registration...")
    print(f"App1 server: {BASE_URL}")
    print(f"Alohomora server: {ALOHOMORA_URL}")
    
    # Setup alohomora system first
    alohomora_setup = setup_alohomora_system()
    if not alohomora_setup:
        print("✗ Failed to setup alohomora system, skipping token registration test")
        return
    
    headers = {"Content-Type": "application/json"}
    
    # Test 1: Valid session creation followed by token registration
    print("\n1. Testing session creation + token registration:")
    session_data = {"user_id": "app1_test_user", "data": "test data for app1"}
    
    try:
        # Create session
        response = requests.post(f"{BASE_URL}/new_session", json=session_data, headers=headers)
        print(f"Session creation status: {response.status_code}")
        
        if response.status_code == 201:
            result = response.json()
            session_id = result.get('session_id')
            print(f"✓ Session created! ID: {session_id}")
            
            # Now test token registration with real IDs and unique token
            unique_token = f"test-jwt-token-{uuid.uuid4()}"
            print(f"\n  Calling app1 /register_token endpoint (which forwards to alohomora {ALOHOMORA_URL})...")
            print(f"  Using unique token: {unique_token}")
            token_data = {
                "session_id": session_id,
                "token": unique_token,
                "workflow_id": alohomora_setup["workflow_id"],
                "function_id": alohomora_setup["function_id"],
                "system_id": alohomora_setup["system_id"],
                "token_metadata": {
                    "expires_at": "2025-12-31T23:59:59",
                    "scope": "read write",
                    "generated_at": datetime.datetime.now().isoformat()
                }
            }
            
            reg_response = requests.post(f"{BASE_URL}/register_token", json=token_data, headers=headers)
            print(f"  Token registration status: {reg_response.status_code}")
            print(f"  Response: {reg_response.json()}")
            
        else:
            print(f"✗ Session creation failed: {response.json()}")
            
    except requests.exceptions.ConnectionError as e:
        if "8001" in str(e):
            print("Error: Could not connect to app1 server. Make sure it's running on localhost:8001")
        else:
            print(f"Connection error: {e}")
        return
    
    # Test 2: Missing user_id (session creation failure)
    print("\n2. Testing missing user_id:")
    data = {"data": "test data"}
    response = requests.post(f"{BASE_URL}/new_session", json=data, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Test 3: Empty user_id (session creation failure)
    print("\n3. Testing empty user_id:")
    data = {"user_id": "", "data": "test data"}
    response = requests.post(f"{BASE_URL}/new_session", json=data, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    # Test 4: Token registration with invalid session_id
    print("\n4. Testing token registration with invalid session_id:")
    token_data = {
        "session_id": "non-existent-session-id",
        "token": f"invalid-session-token-{uuid.uuid4()}",
        "workflow_id": "test-workflow",
        "function_id": "test-function",
        "system_id": "test-system"
    }
    response = requests.post(f"{BASE_URL}/register_token", json=token_data, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")

def test_token_registration_only():
    """Test token registration with sample data (requires session_id from previous test)"""
    print("\n" + "="*50)
    print("Manual token registration test")
    print("Note: You'll need to replace session_id with a real one from session creation")
    
    headers = {"Content-Type": "application/json"}
    
    token_data = {
        "session_id": "REPLACE-WITH-REAL-SESSION-ID",
        "token": f"manual-test-token-{uuid.uuid4()}",
        "workflow_id": "test-workflow-id",
        "function_id": "test-function-id", 
        "system_id": "test-system-id"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/register_token", json=token_data, headers=headers)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to app1 server")

if __name__ == "__main__":
    test_session_creation_and_registration()
    print("\n" + "="*60)
    print(f"Note: Token registration will fail if alohomora server ({ALOHOMORA_URL}) isn't running")
    print("or if the workflow_id/function_id/system_id don't exist in alohomora.")