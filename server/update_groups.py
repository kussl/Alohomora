#!/usr/bin/env python3

import sys
import os
sys.path.append(os.path.dirname(__file__))

from dbconnector import DBConnector
import sqlite3

def update_systems_to_group1():
    """Update existing systems to belong to group_1"""
    print("Updating systems to belong to group_1...")
    
    db_connector = DBConnector("sessions.db")
    conn = db_connector.get_db_connection()
    
    if conn is None:
        print("Failed to connect to database")
        return False
    
    try:
        cursor = conn.cursor()
        
        # First, ensure group_1 exists
        cursor.execute("SELECT group_id FROM groups WHERE group_id = 'group_1'")
        if not cursor.fetchone():
            print("Creating group_1...")
            cursor.execute('''
                INSERT INTO groups (group_id, group_name, description, created_at)
                VALUES ('group_1', 'Group 1', 'Primary group for app1, app2, and replica_app_g1', datetime('now'))
            ''')
        
        # Update all systems to belong to group_1
        cursor.execute('''
            UPDATE systems 
            SET group_id = 'group_1' 
            WHERE group_id IS NULL OR group_id != 'group_1'
        ''')
        
        rows_affected = cursor.rowcount
        print(f"Updated {rows_affected} systems to group_1")
        
        # Update all system_functions to belong to group_1  
        cursor.execute('''
            UPDATE system_functions 
            SET group_id = 'group_1'
            WHERE group_id IS NULL OR group_id != 'group_1'
        ''')
        
        functions_affected = cursor.rowcount
        print(f"Updated {functions_affected} system functions to group_1")
        
        # Update all workflow_edges to belong to group_1
        cursor.execute('''
            UPDATE workflow_edges 
            SET group_id = 'group_1'
            WHERE group_id IS NULL OR group_id != 'group_1'
        ''')
        
        edges_affected = cursor.rowcount
        print(f"Updated {edges_affected} workflow edges to group_1")
        
        # Update all workflows to belong to group_1
        cursor.execute('''
            UPDATE workflows
            SET group_id = 'group_1'
            WHERE group_id IS NULL OR group_id != 'group_1'
        ''')
        
        workflows_affected = cursor.rowcount
        print(f"Updated {workflows_affected} workflows to group_1")
        
        conn.commit()
        conn.close()
        
        print("✓ Successfully updated all systems to group_1")
        return True
        
    except sqlite3.Error as e:
        print(f"Error updating systems: {e}")
        conn.close()
        return False

def show_group_status():
    """Show current group membership status"""
    print("\nCurrent group membership status:")
    
    db_connector = DBConnector("sessions.db")
    conn = db_connector.get_db_connection()
    
    if conn is None:
        print("Failed to connect to database")
        return
    
    try:
        cursor = conn.cursor()
        
        # Show systems and their groups
        cursor.execute('''
            SELECT system_name, group_id, system_id 
            FROM systems 
            ORDER BY group_id, system_name
        ''')
        
        systems = cursor.fetchall()
        print("\nSystems:")
        for system in systems:
            print(f"  {system[0]} -> {system[1]} (ID: {system[2]})")
        
        # Show group summary
        cursor.execute('''
            SELECT group_id, COUNT(*) as system_count
            FROM systems 
            GROUP BY group_id
            ORDER BY group_id
        ''')
        
        groups = cursor.fetchall()
        print("\nGroup Summary:")
        for group in groups:
            group_name = group[0] if group[0] else "No Group"
            print(f"  {group_name}: {group[1]} systems")
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"Error querying systems: {e}")
        conn.close()

if __name__ == "__main__":
    print("Group Management Script")
    print("=" * 40)
    
    # Show current status
    show_group_status()
    
    # Update systems to group_1
    print("\n" + "=" * 40)
    update_systems_to_group1()
    
    # Show updated status
    print("\n" + "=" * 40)
    show_group_status()