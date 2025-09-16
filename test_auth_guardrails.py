#!/usr/bin/env python3
"""
Unit tests for authentication guardrails
Tests that hitting /api/backend/* without cookie returns 401
"""

import unittest
import requests
import os

class TestAuthGuardrails(unittest.TestCase):
    
    def setUp(self):
        """Set up test client"""
        self.base_url = "http://localhost:5000"
        
    def test_api_backend_chat_requires_auth(self):
        """Test that /api/backend/chat without cookie returns 401"""
        # Make request without session cookie
        response = requests.post(
            f"{self.base_url}/api/backend/propose_expense",
            json={"text": "I spent 100 taka on food"},
            headers={"Content-Type": "application/json"}
        )
        
        # Should return 401 for unauthenticated request
        self.assertEqual(response.status_code, 401)
        
        # Check error response format
        data = response.json()
        self.assertEqual(data.get('success'), False)
        self.assertEqual(data.get('error'), 'Authentication required')
        self.assertEqual(data.get('error_code'), 'AUTH_REQUIRED')
        self.assertIsNotNone(data.get('trace_id'))
        
    def test_api_backend_add_expense_requires_auth(self):
        """Test that /api/backend/add_expense without cookie returns 401"""
        response = requests.post(
            f"{self.base_url}/api/backend/add_expense",
            json={
                "description": "Test expense",
                "amount_minor": 10000,
                "currency": "BDT",
                "category": "food"
            },
            headers={"Content-Type": "application/json"}
        )
        
        self.assertEqual(response.status_code, 401)
        data = response.json()
        self.assertEqual(data.get('error_code'), 'AUTH_REQUIRED')
        
    def test_api_backend_get_requires_no_auth(self):
        """Test that GET requests to /api/backend/* don't require auth"""
        # GET requests should not be blocked by write protection
        response = requests.get(f"{self.base_url}/api/backend/get_totals")
        
        # Should not return 401 due to auth (might return other errors)
        self.assertNotEqual(response.status_code, 401)
        
    def test_non_api_routes_allow_guest_access(self):
        """Test that non-API routes allow guest access"""
        response = requests.get(f"{self.base_url}/chat")
        
        # Should not return 401 auth error
        self.assertNotEqual(response.status_code, 401)

if __name__ == '__main__':
    # Check if server is running
    try:
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code != 200:
            print("Server not responding to health check")
            exit(1)
    except requests.exceptions.RequestException:
        print("Server not running on localhost:5000")
        exit(1)
    
    unittest.main()