import requests

BASE_URL = "http://localhost:8000"

def print_response(response):
    print(f"Status: {response.status_code}")
    try:
        print(f"Response: {response.json()}")
    except requests.exceptions.JSONDecodeError:
        print(f"Response (text): {response.text}")
    return response.status_code < 400

def test_session_endpoint():
    print("Testing endpoints...")
    successful_tests = 0
    total_tests = 0
    
    # Test hello endpoint first
    print("\n0. Testing hello endpoint:")
    response = requests.get(f"{BASE_URL}/hello")
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    headers = {"Content-Type": "application/json"}
    
    # Test 1: Valid session creation
    print("\n1. Testing valid session creation:")
    data = {"user_id": "test_user", "data": "test session data"}
    response = requests.post(f"{BASE_URL}/new_session", json=data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 2: Missing user_id
    print("\n2. Testing missing user_id:")
    data = {"data": "test data"}
    response = requests.post(f"{BASE_URL}/new_session", json=data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 3: Empty user_id
    print("\n3. Testing empty user_id:")
    data = {"user_id": "", "data": "test data"}
    response = requests.post(f"{BASE_URL}/new_session", json=data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 4: No JSON data
    print("\n4. Testing no JSON data:")
    response = requests.post(f"{BASE_URL}/new_session", headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    print(f"\nSession endpoint tests completed: {successful_tests}/{total_tests} successful tests")

def test_system_endpoints():
    print("\n\nTesting system endpoints...")
    successful_tests = 0
    total_tests = 0
    
    headers = {"Content-Type": "application/json"}
    
    # Test 5: Valid system registration
    print("\n5. Testing valid system registration:")
    data = {
        "system_name": "test_system", 
        "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQ...",
        "group_id": "group_1"
    }
    response = requests.post(f"{BASE_URL}/register_system", json=data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    if response.status_code == 201:
        system_id = response.json().get("system_id")
        
        # Test 6: Get system information
        print("\n6. Testing system info retrieval:")
        response = requests.get(f"{BASE_URL}/system/{system_id}")
        total_tests += 1
        if print_response(response):
            successful_tests += 1
    
    # Test 7: Missing system_name
    print("\n7. Testing missing system_name:")
    data = {"public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQ..."}
    response = requests.post(f"{BASE_URL}/register_system", json=data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 8: Missing public_key
    print("\n8. Testing missing public_key:")
    data = {"system_name": "test_system"}
    response = requests.post(f"{BASE_URL}/register_system", json=data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 9: Empty system_name
    print("\n9. Testing empty system_name:")
    data = {"system_name": "", "public_key": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQ..."}
    response = requests.post(f"{BASE_URL}/register_system", json=data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 10: Empty public_key
    print("\n10. Testing empty public_key:")
    data = {"system_name": "test_system", "public_key": ""}
    response = requests.post(f"{BASE_URL}/register_system", json=data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 11: Get non-existent system
    print("\n11. Testing non-existent system:")
    response = requests.get(f"{BASE_URL}/system/non-existent-id")
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 12: Get system with empty ID
    print("\n12. Testing empty system ID:")
    response = requests.get(f"{BASE_URL}/system/")
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    print(f"\nSystem endpoint tests completed: {successful_tests}/{total_tests} successful tests")

def setup_dummy_data():
    """Setup dummy systems, group, and functions for workflow testing"""
    print("\n\nSetting up dummy test data...")
    
    headers = {"Content-Type": "application/json"}
    dummy_data = {}
    
    # Create dummy group (we'll assume group creation endpoint exists or use direct DB)
    # For now, we'll use a fixed group_id that should exist
    group_id = "test_group_1"
    
    # Create dummy systems
    systems = [
        {"system_name": "auth_service", "public_key": "auth_pub_key_123", "group_id": group_id},
        {"system_name": "user_service", "public_key": "user_pub_key_456", "group_id": group_id},
        {"system_name": "order_service", "public_key": "order_pub_key_789", "group_id": group_id},
        {"system_name": "payment_service", "public_key": "payment_pub_key_abc", "group_id": group_id}
    ]
    
    dummy_data["systems"] = {}
    for i, system_data in enumerate(systems):
        system_name = system_data['system_name']
        print(f"\n  Checking system {i+1}: {system_name}")
        
        # Check if system already exists
        response = requests.get(f"{BASE_URL}/system/name/{system_name}")
        if response.status_code == 200:
            # System exists, use existing data
            existing_system = response.json()
            dummy_data["systems"][system_name] = {
                "system_id": existing_system["system_id"],
                "group_id": existing_system["group_id"]
            }
            print(f"    Found existing system with ID: {existing_system['system_id']}")
        else:
            # System doesn't exist, create it
            response = requests.post(f"{BASE_URL}/register_system", json=system_data, headers=headers)
            if response.status_code == 201:
                system_id = response.json().get("system_id")
                dummy_data["systems"][system_name] = {
                    "system_id": system_id,
                    "group_id": group_id
                }
                print(f"    Created with ID: {system_id}")
            else:
                print(f"    Failed to create: {response.status_code}")
    
    # Register functions for each system
    functions = {
        "auth_service": [
            {"function_name": "login", "url": "/auth/login"},
            {"function_name": "verify_token", "url": "/auth/verify"}
        ],
        "user_service": [
            {"function_name": "get_profile", "url": "/user/profile"},
            {"function_name": "validate_user", "url": "/user/validate"},
            {"function_name": "send_notification", "url": "/user/notify"}
        ],
        "order_service": [
            {"function_name": "create_order", "url": "/order/create"},
            {"function_name": "process_order", "url": "/order/process"},
            {"function_name": "cancel_order", "url": "/order/cancel"}
        ],
        "payment_service": [
            {"function_name": "charge_payment", "url": "/payment/charge"},
            {"function_name": "retry_payment", "url": "/payment/retry"}
        ]
    }
    
    dummy_data["functions"] = {}
    for service_name, service_functions in functions.items():
        if service_name in dummy_data["systems"]:
            system_id = dummy_data["systems"][service_name]["system_id"]
            dummy_data["functions"][service_name] = {}
            
            for func_data in service_functions:
                func_name = func_data['function_name']
                print(f"\n  Checking function: {service_name}.{func_name}")
                
                # For simplicity, always try to register (functions are cheap to recreate)
                # In a production system, you'd want a lookup endpoint here too
                func_request = {
                    "system_id": system_id,
                    "function_name": func_name,
                    "url": func_data["url"]
                }
                response = requests.post(f"{BASE_URL}/register_function", json=func_request, headers=headers)
                if response.status_code == 201:
                    function_id = response.json().get("function_id")
                    dummy_data["functions"][service_name][func_name] = function_id
                    print(f"    Registered with ID: {function_id}")
                else:
                    print(f"    Failed to register function: {response.status_code}")
                    if response.text:
                        print(f"    Error: {response.text}")
                    # Don't add to dummy_data if failed
    
    return dummy_data

def test_workflow_endpoints():
    print("\n\nTesting workflow endpoints...")
    successful_tests = 0
    total_tests = 0
    
    headers = {"Content-Type": "application/json"}
    
    # Setup dummy data
    dummy_data = setup_dummy_data()
    
    if not dummy_data["systems"]:
        print("Failed to create dummy systems, skipping workflow tests")
        return
    
    # Check if we have all required functions
    required_functions = {
        "auth_service": ["login", "verify_token"],
        "user_service": ["get_profile", "validate_user", "send_notification"],
        "order_service": ["create_order", "process_order", "cancel_order"],
        "payment_service": ["charge_payment", "retry_payment"]
    }
    
    missing_functions = []
    for service, functions in required_functions.items():
        if service not in dummy_data["functions"]:
            missing_functions.extend([f"{service}.{func}" for func in functions])
        else:
            for func in functions:
                if func not in dummy_data["functions"][service]:
                    missing_functions.append(f"{service}.{func}")
    
    if missing_functions:
        print(f"Missing required functions: {missing_functions}")
        print("Skipping workflow tests")
        print(f"\nWorkflow endpoint tests completed: {successful_tests}/{total_tests} successful tests")
        return
    
    # Test 13: Simple workflow
    print("\n13. Testing simple workflow registration:")
    
    # Simple workflow: auth -> user -> order
    simple_workflow = {
        "vertices": {
            dummy_data["functions"]["auth_service"]["login"]: {"f": "login", "s": "auth_service"},
            dummy_data["functions"]["user_service"]["get_profile"]: {"f": "get_profile", "s": "user_service"},
            dummy_data["functions"]["order_service"]["create_order"]: {"f": "create_order", "s": "order_service"}
        },
        "adj": {
            dummy_data["functions"]["auth_service"]["login"]: [dummy_data["functions"]["user_service"]["get_profile"]],
            dummy_data["functions"]["user_service"]["get_profile"]: [dummy_data["functions"]["order_service"]["create_order"]],
            dummy_data["functions"]["order_service"]["create_order"]: []
        }
    }
    
    workflow_data = {
        "system_id": dummy_data["systems"]["auth_service"]["system_id"],
        "workflow_graph": simple_workflow
    }
    
    response = requests.post(f"{BASE_URL}/register_workflow", json=workflow_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 14: Complex workflow with loops and exit paths
    print("\n14. Testing complex workflow with loops:")
    
    # Complex workflow with loops:
    # auth -> user -> order -> payment
    #          ^        |       |
    #          |        v       v
    #          +--- retry <-----+
    #               |
    #               v
    #            cancel_order
    auth_verify = dummy_data["functions"]["auth_service"]["verify_token"]
    user_validate = dummy_data["functions"]["user_service"]["validate_user"]
    order_process = dummy_data["functions"]["order_service"]["process_order"]
    payment_charge = dummy_data["functions"]["payment_service"]["charge_payment"]
    payment_retry = dummy_data["functions"]["payment_service"]["retry_payment"]
    order_cancel = dummy_data["functions"]["order_service"]["cancel_order"]
    user_notify = dummy_data["functions"]["user_service"]["send_notification"]
    
    complex_workflow = {
        "vertices": {
            auth_verify: {"f": "verify_token", "s": "auth_service"},
            user_validate: {"f": "validate_user", "s": "user_service"},
            order_process: {"f": "process_order", "s": "order_service"},
            payment_charge: {"f": "charge_payment", "s": "payment_service"},
            payment_retry: {"f": "retry_payment", "s": "payment_service"},
            order_cancel: {"f": "cancel_order", "s": "order_service"},
            user_notify: {"f": "send_notification", "s": "user_service"}
        },
        "adj": {
            auth_verify: [user_validate],
            user_validate: [order_process],
            order_process: [payment_charge],
            payment_charge: [user_notify, payment_retry],  # Success or retry
            payment_retry: [payment_charge, order_cancel],  # Loop back or cancel
            order_cancel: [user_notify],  # Exit path from loop
            user_notify: []  # End node
        }
    }
    
    workflow_data = {
        "system_id": dummy_data["systems"]["auth_service"]["system_id"],
        "workflow_graph": complex_workflow
    }
    
    response = requests.post(f"{BASE_URL}/register_workflow", json=workflow_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 15: Invalid workflow - function not in group
    print("\n15. Testing invalid workflow (function not in group):")
    
    invalid_workflow = {
        "vertices": {
            "auth_login": {"f": "login", "s": "auth_service"},
            "external_api": {"f": "external_call", "s": "external_service"}
        },
        "adj": {
            "auth_login": ["external_api"],
            "external_api": []
        }
    }
    
    workflow_data = {
        "system_id": dummy_data["systems"]["auth_service"]["system_id"],
        "workflow_graph": invalid_workflow
    }
    
    response = requests.post(f"{BASE_URL}/register_workflow", json=workflow_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 16: Missing system_id
    print("\n16. Testing missing system_id:")
    
    workflow_data = {
        "workflow_graph": simple_workflow
    }
    
    response = requests.post(f"{BASE_URL}/register_workflow", json=workflow_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 17: Non-existent system
    print("\n17. Testing non-existent system:")
    
    workflow_data = {
        "system_id": "non-existent-system-id",
        "workflow_graph": simple_workflow
    }
    
    response = requests.post(f"{BASE_URL}/register_workflow", json=workflow_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 18: Invalid JSON format
    print("\n18. Testing invalid workflow format:")
    
    workflow_data = {
        "system_id": dummy_data["systems"]["auth_service"]["system_id"],
        "workflow_graph": "invalid_format"
    }
    
    response = requests.post(f"{BASE_URL}/register_workflow", json=workflow_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    print(f"\nWorkflow endpoint tests completed: {successful_tests}/{total_tests} successful tests")

def test_token_recording_endpoints():
    print("\n\nTesting token recording endpoints...")
    successful_tests = 0
    total_tests = 0
    
    headers = {"Content-Type": "application/json"}
    
    # Setup dummy data (reuse from workflow tests)
    dummy_data = setup_dummy_data()
    
    if not dummy_data["systems"]:
        print("Failed to create dummy systems, skipping token recording tests")
        print(f"\nToken recording endpoint tests completed: {successful_tests}/{total_tests} successful tests")
        return
    
    # Get valid system and function data for tests
    auth_system_id = dummy_data["systems"]["auth_service"]["system_id"]
    auth_function_id = dummy_data["functions"]["auth_service"]["login"]
    
    # We need a workflow_id - let's create a simple single-node workflow for testing
    simple_workflow = {
        "vertices": {
            auth_function_id: {"f": "login", "s": "auth_service"}
        },
        "adj": {
            auth_function_id: []
        }
    }
    
    workflow_data = {
        "system_id": auth_system_id,
        "workflow_graph": simple_workflow
    }
    
    print("\n  Setting up test workflow...")
    workflow_response = requests.post(f"{BASE_URL}/register_workflow", json=workflow_data, headers=headers)
    
    if workflow_response.status_code == 201:
        test_workflow_id = workflow_response.json().get("workflow_id")
        print(f"  Test workflow created with ID: {test_workflow_id}")
    else:
        print("  Failed to create test workflow, skipping token recording tests")
        print(f"\nToken recording endpoint tests completed: {successful_tests}/{total_tests} successful tests")
        return
    
    # Test 19: Valid token recording
    print("\n19. Testing valid token recording:")
    token_data = {
        "system_id": auth_system_id,
        "token": "valid-jwt-token-12345",
        "workflow_id": test_workflow_id,
        "function_id": auth_function_id,
        "user_id": "test_user_123"
    }
    response = requests.post(f"{BASE_URL}/record_token", json=token_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 20: Valid token with custom expiration
    print("\n20. Testing valid token with custom expiration:")
    token_data = {
        "system_id": auth_system_id,
        "token": "valid-jwt-token-with-expiry-67890",
        "workflow_id": test_workflow_id,
        "function_id": auth_function_id,
        "user_id": "test_user_456",
        "token_metadata": {
            "expires_at": "2025-12-31T23:59:59",
            "issued_at": "2025-08-30T15:00:00"
        }
    }
    response = requests.post(f"{BASE_URL}/record_token", json=token_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 21: Valid token with additional metadata
    print("\n21. Testing valid token with additional metadata:")
    token_data = {
        "system_id": auth_system_id,
        "token": "valid-jwt-token-with-metadata-abcdef",
        "workflow_id": test_workflow_id,
        "function_id": auth_function_id,
        "user_id": "test_user_789",
        "token_metadata": {
            "expires_at": "2025-12-31T23:59:59",
            "scope": "read write",
            "permissions": ["login", "profile"]
        }
    }
    response = requests.post(f"{BASE_URL}/record_token", json=token_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 22: Missing system_id
    print("\n22. Testing missing system_id:")
    token_data = {
        "token": "missing-system-id-token",
        "workflow_id": test_workflow_id,
        "function_id": auth_function_id,
        "user_id": "test_user"
    }
    response = requests.post(f"{BASE_URL}/record_token", json=token_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 23: Missing token
    print("\n23. Testing missing token:")
    token_data = {
        "system_id": auth_system_id,
        "workflow_id": test_workflow_id,
        "function_id": auth_function_id,
        "user_id": "test_user"
    }
    response = requests.post(f"{BASE_URL}/record_token", json=token_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 24: Missing workflow_id
    print("\n24. Testing missing workflow_id:")
    token_data = {
        "system_id": auth_system_id,
        "token": "missing-workflow-id-token",
        "function_id": auth_function_id,
        "user_id": "test_user"
    }
    response = requests.post(f"{BASE_URL}/record_token", json=token_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 25: Missing function_id
    print("\n25. Testing missing function_id:")
    token_data = {
        "system_id": auth_system_id,
        "token": "missing-function-id-token",
        "workflow_id": test_workflow_id,
        "user_id": "test_user"
    }
    response = requests.post(f"{BASE_URL}/record_token", json=token_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 26: Missing user_id
    print("\n26. Testing missing user_id:")
    token_data = {
        "system_id": auth_system_id,
        "token": "missing-user-id-token",
        "workflow_id": test_workflow_id,
        "function_id": auth_function_id
    }
    response = requests.post(f"{BASE_URL}/record_token", json=token_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 27: Empty string values
    print("\n27. Testing empty string values:")
    token_data = {
        "system_id": "",
        "token": "empty-fields-token",
        "workflow_id": test_workflow_id,
        "function_id": auth_function_id,
        "user_id": "test_user"
    }
    response = requests.post(f"{BASE_URL}/record_token", json=token_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 28: Non-existent system_id
    print("\n28. Testing non-existent system_id:")
    token_data = {
        "system_id": "non-existent-system-id",
        "token": "non-existent-system-token",
        "workflow_id": test_workflow_id,
        "function_id": auth_function_id,
        "user_id": "test_user"
    }
    response = requests.post(f"{BASE_URL}/record_token", json=token_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 29: Invalid workflow_id/function_id combination
    print("\n29. Testing invalid workflow/function combination:")
    token_data = {
        "system_id": auth_system_id,
        "token": "invalid-workflow-function-token",
        "workflow_id": "non-existent-workflow-id",
        "function_id": auth_function_id,
        "user_id": "test_user"
    }
    response = requests.post(f"{BASE_URL}/record_token", json=token_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 30: Expired token in metadata
    print("\n30. Testing expired token:")
    token_data = {
        "system_id": auth_system_id,
        "token": "expired-token-12345",
        "workflow_id": test_workflow_id,
        "function_id": auth_function_id,
        "user_id": "test_user",
        "token_metadata": {
            "expires_at": "2020-01-01T00:00:00"
        }
    }
    response = requests.post(f"{BASE_URL}/record_token", json=token_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 31: Duplicate token
    print("\n31. Testing duplicate token:")
    token_data = {
        "system_id": auth_system_id,
        "token": "valid-jwt-token-12345",  # Same as test 19
        "workflow_id": test_workflow_id,
        "function_id": auth_function_id,
        "user_id": "test_user_duplicate"
    }
    response = requests.post(f"{BASE_URL}/record_token", json=token_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 32: No JSON data
    print("\n32. Testing no JSON data:")
    response = requests.post(f"{BASE_URL}/record_token", headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    print(f"\nToken recording endpoint tests completed: {successful_tests}/{total_tests} successful tests")

def test_workflow_instance_endpoints():
    print("\n\nTesting workflow instance endpoints...")
    successful_tests = 0
    total_tests = 0
    
    headers = {"Content-Type": "application/json"}
    
    # Setup dummy data
    dummy_data = setup_dummy_data()
    
    if not dummy_data["systems"]:
        print("Failed to create dummy systems, skipping workflow instance tests")
        print(f"\nWorkflow instance endpoint tests completed: {successful_tests}/{total_tests} successful tests")
        return
    
    # Get valid system and function data for tests
    auth_system_id = dummy_data["systems"]["auth_service"]["system_id"]
    auth_function_id = dummy_data["functions"]["auth_service"]["login"]
    
    # Create a test workflow
    simple_workflow = {
        "vertices": {
            auth_function_id: {"f": "login", "s": "auth_service"}
        },
        "adj": {
            auth_function_id: []
        }
    }
    
    workflow_data = {
        "system_id": auth_system_id,
        "workflow_graph": simple_workflow
    }
    
    print("\n  Setting up test workflow...")
    workflow_response = requests.post(f"{BASE_URL}/register_workflow", json=workflow_data, headers=headers)
    if workflow_response.status_code != 201:
        print("Failed to create test workflow, skipping workflow instance tests")
        print(f"\nWorkflow instance endpoint tests completed: {successful_tests}/{total_tests} successful tests")
        return
    
    test_workflow_id = workflow_response.json()["workflow_id"]
    
    # Test 33: Create workflow instance - valid data
    print("\n33. Testing create workflow instance with valid data:")
    instance_data = {
        "workflow_id": test_workflow_id,
        "user_id": "test_user",
        "session_id": "test-session-123",
        "metadata": {"description": "Test workflow instance"}
    }
    response = requests.post(f"{BASE_URL}/create_workflow_instance", json=instance_data, headers=headers)
    total_tests += 1
    test_instance_id = None
    if print_response(response):
        successful_tests += 1
        if response.status_code == 201:
            test_instance_id = response.json().get("instance_id")
    
    # Test 34: Create workflow instance - missing workflow_id
    print("\n34. Testing create workflow instance missing workflow_id:")
    instance_data = {
        "user_id": "test_user"
    }
    response = requests.post(f"{BASE_URL}/create_workflow_instance", json=instance_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 35: Create workflow instance - non-existent workflow
    print("\n35. Testing create workflow instance with non-existent workflow:")
    instance_data = {
        "workflow_id": "non-existent-workflow-id",
        "user_id": "test_user"
    }
    response = requests.post(f"{BASE_URL}/create_workflow_instance", json=instance_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    if test_instance_id:
        # Test 36: Mark step completion - valid data
        print("\n36. Testing mark step completion with valid data:")
        step_data = {
            "instance_id": test_instance_id,
            "function_id": auth_function_id,
            "system_id": auth_system_id,
            "result_data": '{"status": "success", "user_authenticated": true}'
        }
        response = requests.post(f"{BASE_URL}/mark_step_completion", json=step_data, headers=headers)
        total_tests += 1
        if print_response(response):
            successful_tests += 1
        
        # Test 37: Mark step completion - with error
        print("\n37. Testing mark step completion with error:")
        step_data = {
            "instance_id": test_instance_id,
            "function_id": auth_function_id,
            "system_id": auth_system_id,
            "error_message": "Authentication failed: invalid credentials"
        }
        response = requests.post(f"{BASE_URL}/mark_step_completion", json=step_data, headers=headers)
        total_tests += 1
        if print_response(response):
            successful_tests += 1
    else:
        print("Skipping step completion tests - no valid instance created")
        total_tests += 2
    
    # Test 38: Mark step completion - non-existent instance
    print("\n38. Testing mark step completion with non-existent instance:")
    step_data = {
        "instance_id": "non-existent-instance-id",
        "function_id": auth_function_id,
        "system_id": auth_system_id
    }
    response = requests.post(f"{BASE_URL}/mark_step_completion", json=step_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    # Test 39: Mark step completion - system doesn't own function
    print("\n39. Testing mark step completion with wrong system:")
    if len(dummy_data["systems"]) > 1:
        other_system_id = next(sys_id for sys_id in dummy_data["systems"].values() 
                               if sys_id["system_id"] != auth_system_id)["system_id"]
        step_data = {
            "instance_id": test_instance_id if test_instance_id else "dummy-instance",
            "function_id": auth_function_id,
            "system_id": other_system_id
        }
        response = requests.post(f"{BASE_URL}/mark_step_completion", json=step_data, headers=headers)
        total_tests += 1
        if print_response(response):
            successful_tests += 1
    else:
        print("  Skipped - need multiple systems for this test")
        total_tests += 1
    
    # Test 40: Mark step completion - missing required fields
    print("\n40. Testing mark step completion missing instance_id:")
    step_data = {
        "function_id": auth_function_id,
        "system_id": auth_system_id
    }
    response = requests.post(f"{BASE_URL}/mark_step_completion", json=step_data, headers=headers)
    total_tests += 1
    if print_response(response):
        successful_tests += 1
    
    print(f"\nWorkflow instance endpoint tests completed: {successful_tests}/{total_tests} successful tests")

if __name__ == "__main__":
    try:
        test_session_endpoint()
        test_system_endpoints()
        test_workflow_endpoints()
        test_token_recording_endpoints()
        test_workflow_instance_endpoints()
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to server. Make sure server is running on localhost:8000")