# App1 - Minimal Session Management System

This is a minimal Flask application that provides session creation functionality with a local SQLite database and integration with alohomora server.

## Files

- `app.py` - Main Flask application
- `dbconnector.py` - Database connector for local SQLite database
- `config.json` - Configuration file (auto-created with defaults)
- `init_db.py` - Database initialization script
- `test_app.py` - Test script for endpoints
- `app1db.db` - Local SQLite database file

## Setup and Usage

1. **Initialize the database:**
   ```bash
   cd app1
   python init_db.py
   ```

2. **Start the application:**
   ```bash
   python app.py
   ```
   The app will auto-create `config.json` with defaults on first run.
   Default: `http://localhost:8001`

3. **Test the endpoints:**
   ```bash
   # In another terminal
   python test_app.py
   ```

4. **Optional: Customize configuration:**
   ```bash
   # Edit the auto-generated config.json file
   nano config.json
   ```

## Configuration

The app auto-creates `config.json` with these defaults on first run:

```json
{
  "alohomora": {
    "base_url": "http://localhost:8000",
    "timeout": 5
  },
  "app": {
    "host": "0.0.0.0",
    "port": 8001,
    "debug": true
  }
}
```

Edit this file to customize settings for your environment.

### Configuration Options:

- **alohomora.base_url**: URL of the alohomora server (for token registration)
- **alohomora.timeout**: Timeout in seconds for alohomora requests
- **app.host**: Host to bind the Flask app to
- **app.port**: Port to run the Flask app on
- **app.debug**: Enable/disable Flask debug mode

## API Endpoints

### POST /new_session

Creates a new user session.

**Request:**
```json
{
  "user_id": "string (required)",
  "data": "string (optional)"
}
```

**Response (Success - 201):**
```json
{
  "session_id": "uuid-string"
}
```

**Response (Error - 400):**
```json
{
  "error": "error message"
}
```

### POST /register_token

Registers a token with the alohomora server for an existing session.

**Request:**
```json
{
  "session_id": "string (required)",
  "token": "string (required)",
  "workflow_id": "string (required)",
  "function_id": "string (required)",
  "system_id": "string (required)",
  "user_id": "string (optional, uses session user_id if not provided)",
  "token_metadata": {
    "expires_at": "ISO timestamp (optional)",
    "additional_data": "any (optional)"
  }
}
```

**Response (Success - 201):**
```json
{
  "message": "Token registered successfully with alohomora",
  "alohomora_token_id": "uuid-string",
  "session_id": "uuid-string"
}
```

**Response (Error - 404):**
```json
{
  "error": "Session not found"
}
```

**Response (Error - 502):**
```json
{
  "error": "Failed to register token with alohomora",
  "alohomora_error": "error from alohomora",
  "alohomora_status": 400
}
```

**Response (Error - 503):**
```json
{
  "error": "Failed to connect to alohomora server",
  "details": "connection error details"
}
```

### POST /receive_session_notification

Receives shared session notifications from alohomora server. This endpoint allows app1 to act as a receiver in cross-app workflows.

**Request:**
```json
{
  "token_id": "string (required)",
  "session_info": {
    "user_id": "string (required)",
    "workflow_id": "string (required)", 
    "session_id": "string (optional)",
    "create_local_session": "boolean (optional)"
  },
  "workflow_status": {
    "total_instances": "number",
    "completed_instances": "number",
    "in_progress_instances": "number", 
    "failed_instances": "number"
  },
  "notification_metadata": "object (optional)"
}
```

**Response (Success - 200):**
```json
{
  "message": "Session notification received successfully",
  "token_id": "uuid-string",
  "processed_at": "ISO timestamp",
  "local_session_created": "boolean",
  "local_session_id": "uuid-string (if session created)"
}
```

## Database

The application uses a local SQLite database (`app1db.db`) with a single `sessions` table:

```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,
    created_at TEXT,
    last_accessed_at TEXT,
    expires_at TEXT,
    data TEXT
);
```

Sessions expire 1 hour after creation.