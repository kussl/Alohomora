#!/usr/bin/env python3
"""
Standalone replica synchronization script.
Fetches updates from main server and syncs to local replica database.
"""

import json
import os
import sys
import datetime
import requests
from dbconnector import DBConnector

def load_config():
    """Load replica configuration"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in config file: {e}")
        sys.exit(1)

def load_last_sync_time(replica_id):
    """Load last sync timestamp from file"""
    sync_file = os.path.join(os.path.dirname(__file__), f'.last_sync_{replica_id}')
    try:
        with open(sync_file, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def save_last_sync_time(replica_id, timestamp):
    """Save last sync timestamp to file"""
    sync_file = os.path.join(os.path.dirname(__file__), f'.last_sync_{replica_id}')
    with open(sync_file, 'w') as f:
        f.write(timestamp)

def sync_with_main_server(config, db_connector, last_sync_time=None):
    """Fetch and sync data from main server"""

    replica_config = config['replica']
    main_server_url = replica_config['main_server_url']
    replica_id = replica_config['replica_id']
    group_id = replica_config['group_id']

    print(f"[SYNC] Starting sync for replica '{replica_id}' (group: {group_id})")
    print(f"[SYNC] Main server: {main_server_url}")
    if last_sync_time:
        print(f"[SYNC] Last sync: {last_sync_time}")
    else:
        print(f"[SYNC] Initial sync (no previous sync time)")

    # Prepare sync request
    sync_data = {
        "replica_id": replica_id,
        "group_id": group_id,
        "last_sync": last_sync_time
    }

    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(
            f"{main_server_url}/replica_sync",
            json=sync_data,
            headers=headers,
            timeout=30,
            verify=True
        )

        if response.status_code != 200:
            print(f"[ERROR] Sync request failed: {response.status_code}")
            print(f"[ERROR] Response: {response.text}")
            return False

        updates = response.json()

        # Get counts
        systems_count = len(updates.get('systems', []))
        functions_count = len(updates.get('system_functions', []))
        workflows_count = len(updates.get('workflows', []))
        edges_count = len(updates.get('workflow_edges', []))
        tokens_count = len(updates.get('shared_tokens', []))

        print(f"[SYNC] Received updates:")
        print(f"  - Systems: {systems_count}")
        print(f"  - Functions: {functions_count}")
        print(f"  - Workflows: {workflows_count}")
        print(f"  - Edges: {edges_count}")
        print(f"  - Tokens: {tokens_count}")

        # Sync data in dependency order
        latest_timestamp = last_sync_time

        # 1. Sync systems first (no dependencies)
        print(f"[SYNC] Syncing systems...")
        for system_data in updates.get('systems', []):
            if db_connector.sync_system(system_data):
                print(f"  ✓ {system_data['system_name']} ({system_data['system_id']})")
            else:
                print(f"  ✗ Failed to sync {system_data['system_name']}")

        # 2. Sync system functions (depends on systems)
        print(f"[SYNC] Syncing system functions...")
        for function_data in updates.get('system_functions', []):
            if db_connector.sync_system_function(function_data):
                print(f"  ✓ {function_data['function_name']}")
            else:
                print(f"  ✗ Failed to sync {function_data['function_name']}")

        # 3. Sync workflows (depends on systems and functions)
        print(f"[SYNC] Syncing workflows...")
        for workflow_data in updates.get('workflows', []):
            if db_connector.sync_workflow(workflow_data):
                print(f"  ✓ {workflow_data['workflow_id']}")
            else:
                print(f"  ✗ Failed to sync {workflow_data['workflow_id']}")

        # 4. Sync workflow edges (depends on workflows and functions)
        print(f"[SYNC] Syncing workflow edges...")
        for edge_data in updates.get('workflow_edges', []):
            if db_connector.sync_workflow_edge(edge_data):
                print(f"  ✓ {edge_data['edge_id']}")
            else:
                print(f"  ✗ Failed to sync {edge_data['edge_id']}")

        # 5. Sync tokens last (depends on all above)
        print(f"[SYNC] Syncing shared tokens...")
        for token_data in updates.get('shared_tokens', []):
            if db_connector.insert_shared_token(token_data):
                print(f"  ✓ Token {token_data['token_id']}")
                # Track latest timestamp
                token_time = token_data.get('created_at')
                if token_time and (not latest_timestamp or token_time > latest_timestamp):
                    latest_timestamp = token_time
            else:
                print(f"  ✗ Failed to sync token {token_data['token_id']}")

        # Update sync timestamp
        current_time = datetime.datetime.now().isoformat()
        if tokens_count > 0 and latest_timestamp:
            save_last_sync_time(replica_id, latest_timestamp)
            print(f"[SYNC] Updated last_sync to: {latest_timestamp}")
        else:
            save_last_sync_time(replica_id, current_time)
            print(f"[SYNC] Updated last_sync to: {current_time}")

        print(f"[SYNC] ✅ Sync completed successfully")
        return True

    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Network error: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    # Load configuration
    config = load_config()
    replica_id = config['replica']['replica_id']
    db_name = config['database']['name']

    print(f"=== Replica Sync Script ===")
    print(f"Replica ID: {replica_id}")
    print(f"Database: {db_name}")
    print()

    # Connect to database
    db_connector = DBConnector(db_name)

    # Load last sync time
    last_sync_time = load_last_sync_time(replica_id)

    # Perform sync
    success = sync_with_main_server(config, db_connector, last_sync_time)

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
