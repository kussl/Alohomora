# Server Tests

This directory contains tests for the alohomora server endpoints and functionality.

## Test Scripts

- **`test_server.py`** - Comprehensive server endpoint tests
  - Session management endpoints (`/new_session`)
  - System registration endpoints (`/register_system`, `/system/<id>`)
  - Function registration endpoints (`/register_function`)
  - Workflow management endpoints (`/register_workflow`)
  - Token recording endpoints (`/record_token`)
  - Workflow instance tracking endpoints (`/create_workflow_instance`, `/mark_step_completion`)
  - Error handling and validation tests
  - Run: `python test_server.py`

## Prerequisites

Start the alohomora server before running tests:
```bash
cd .. && python serverapp.py
```

## Test Coverage

The server tests cover:

- ✅ Session creation and management
- ✅ System registration and validation
- ✅ Function registration and ownership
- ✅ Workflow creation and validation
- ✅ Token recording and security
- ✅ Workflow instance creation and tracking
- ✅ Step completion marking
- ✅ Error handling and edge cases
- ✅ Database operations

## Expected Output

Tests show detailed results for each endpoint:
```
Session endpoint tests completed: X/Y successful tests
System endpoint tests completed: X/Y successful tests
Workflow endpoint tests completed: X/Y successful tests
Token recording endpoint tests completed: X/Y successful tests
Workflow instance endpoint tests completed: X/Y successful tests
```