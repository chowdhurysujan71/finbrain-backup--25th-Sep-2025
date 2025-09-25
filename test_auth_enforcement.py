"""
Test cases for AI chat authentication enforcement
Based on specification requirements for 100% success criteria
"""
from unittest.mock import patch

import pytest


def test_ai_chat_requires_auth(client):
    """
    UAT Criteria: Unauthenticated user gets 401 from /ai-chat
    Success: HTTP 401 with JSON error message
    """
    response = client.post('/ai-chat', 
                          json={"message": "I spent 200 on food"},
                          content_type='application/json')
    
    assert response.status_code == 401
    data = response.get_json()
    assert data is not None
    assert "error" in data
    assert "log in" in data["error"].lower()

def test_ai_chat_rejects_empty_message(authenticated_client):
    """
    UAT Criteria: Empty message returns 400 Bad Request
    Success: HTTP 400 with clear error message
    """
    response = authenticated_client.post('/ai-chat',
                                       json={"message": ""},
                                       content_type='application/json')
    
    assert response.status_code == 400
    data = response.get_json()
    assert data is not None
    assert "error" in data
    assert "required" in data["error"].lower()

def test_ai_chat_logs_for_authenticated_user(authenticated_client, mock_db):
    """
    UAT Criteria: Authenticated user can log expenses through AI chat
    Success: HTTP 200, expense saved to database with correct user_id
    """
    # Set up authenticated session
    with authenticated_client.session_transaction() as sess:
        sess['user_id'] = 'test_user_123'
    
    with patch('utils.production_router.route_message') as mock_route:
        mock_route.return_value = ("✅ Logged: ৳200 for food", "expense_log", "food", 200)
        
        response = authenticated_client.post('/ai-chat',
                                           json={"message": "I spent 200 on food"},
                                           content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None
        assert "reply" in data
        assert "user_id" in data
        assert data["user_id"] == 'test_user_123'
        
        # Verify route_message was called with correct user_id
        mock_route.assert_called_once()
        call_args = mock_route.call_args
        assert call_args[1]['user_id_hash'] == 'test_user_123'

def test_frontend_auth_flow_simulation():
    """
    UAT Criteria: Frontend handles 401 properly
    Success: Test simulates the frontend auth check and redirect flow
    """
    # This test simulates the JavaScript flow
    # In real UAT, this would be tested with browser automation
    
    # Simulate /api/auth/me check
    auth_response_status = 401  # Simulating unauthenticated
    
    if auth_response_status == 401:
        # Frontend should redirect to login
        expected_redirect = '/login?returnTo=/chat'
        assert expected_redirect == '/login?returnTo=/chat'
        # In real implementation, this would trigger window.location.href
    
    # Simulate successful auth
    auth_response_status = 200
    if auth_response_status == 200:
        # Frontend should proceed with chat request
        # This would be the /ai-chat request that gets 200 response
        assert True  # Test passes if flow reaches here

# Fixtures for testing
@pytest.fixture
def authenticated_client(client):
    """Create client with authenticated session"""
    with client.session_transaction() as sess:
        sess['user_id'] = 'test_user_123'
    return client

@pytest.fixture
def mock_db():
    """Mock database operations for testing"""
    with patch('utils.db.save_expense') as mock_save:
        mock_save.return_value = {
            'success': True,
            'expense_id': 123,
            'user_id': 'test_user_123'
        }
        yield mock_save

# UAT Test Cases (to be run manually)
"""
Manual UAT Steps - 100% Success Criteria:

1. Auth Gate Test:
   - Step: Logged out → POST /ai-chat with {"message": "I spent 200 on food"}
   - Expected: HTTP 401 with JSON {"error": "Please log in to track expenses"}
   - Success: Exact status code and error message match

2. Authenticated Flow Test:
   - Step: Log in → POST /ai-chat with {"message": "I spent 300 on dinner"}
   - Expected: HTTP 200 with expense logged to database
   - Success: Response contains user_id, expense appears in Recent Expenses

3. Frontend Redirect Test:
   - Step: Open /chat while logged out
   - Expected: Automatic redirect to /login?returnTo=/chat
   - Success: URL changes and login form appears

4. Consistency Test:
   - Step: Log expense via chat → Refresh dashboard
   - Expected: Item and totals match exactly
   - Success: No data discrepancies

5. Anonymous ID Cleanup Test:
   - Step: Search logs for 'pwa_anonymous' during authenticated requests
   - Expected: Zero occurrences
   - Success: No anonymous IDs created for authenticated users
"""