# Replica1 - Alohomora Replica Server

Replica1 is a replica server that synchronizes with the main alohomora server. It maintains a local copy of the database for its assigned group and provides the same API endpoints as the main server (except token recording). Apps in the replica's group can query replica1 directly instead of the main server for better performance and reliability.

## Key Features

- **Full API Compatibility**: Same endpoints as main server (except /record_token)
- **Group-Based Replication**: Only synchronizes data for assigned group
- **Periodic Sync**: Automatically updates from main server
- **Read-Only Tokens**: Cannot create new tokens, only serve existing ones
- **Independent Database**: Local SQLite replica of main server data

## Architecture

```
Main Server (alohomora)  <--sync-->  Replica1
       |                                |
       v                                v
   [All Groups]                    [Group 1 Only]
       |                                |
   app1, app2  <--queries-->        replica1
```