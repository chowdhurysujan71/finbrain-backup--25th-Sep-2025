"""
Integration tests for non-breaking API changes
Tests HTTP endpoints to ensure backward compatibility and new features
"""

import pytest
import requests

# Base URL for the application
BASE_URL = "http://localhost:5000"

class TestUser:
    """Test user for integration tests"""
    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password
        self.session = requests.Session()
        
    def register_and_login(self) -> bool:
        """Register and login test user"""
        try:
            # Get captcha first
            captcha_response = self.session.get(f"{BASE_URL}/api/auth/captcha")
            if captcha_response.status_code != 200:
                return False
                
            captcha_data = captcha_response.json()
            
            # Parse and solve the math question (e.g., "What is 6 * 7?")
            question = captcha_data["question"]
            import re
            match = re.search(r'What is (\d+) ([+\-*/]) (\d+)\?', question)
            if match:
                num1, operator, num2 = match.groups()
                num1, num2 = int(num1), int(num2)
                if operator == '+':
                    answer = num1 + num2
                elif operator == '-':
                    answer = num1 - num2
                elif operator == '*':
                    answer = num1 * num2
                elif operator == '/':
                    answer = num1 // num2  # Integer division
                else:
                    answer = 0
            else:
                answer = 0  # Fallback
            
            # Register user
            register_data = {
                "email": self.email,
                "password": self.password,
                "captcha_answer": str(answer)
            }
            
            register_response = self.session.post(f"{BASE_URL}/api/auth/register", json=register_data)
            if register_response.status_code not in [200, 409]:  # 409 = already exists
                return False
            
            # Login user - get new CAPTCHA first
            login_captcha_response = self.session.get(f"{BASE_URL}/api/auth/captcha")
            if login_captcha_response.status_code != 200:
                return False
                
            login_captcha_data = login_captcha_response.json()
            
            # Parse and solve the login math question
            login_question = login_captcha_data["question"]
            match = re.search(r'What is (\d+) ([+\-*/]) (\d+)\?', login_question)
            if match:
                num1, operator, num2 = match.groups()
                num1, num2 = int(num1), int(num2)
                if operator == '+':
                    login_answer = num1 + num2
                elif operator == '-':
                    login_answer = num1 - num2
                elif operator == '*':
                    login_answer = num1 * num2
                elif operator == '/':
                    login_answer = num1 // num2  # Integer division
                else:
                    login_answer = 0
            else:
                login_answer = 0  # Fallback
            
            login_data = {
                "email": self.email,
                "password": self.password,
                "captcha_answer": str(login_answer)
            }
            
            login_response = self.session.post(f"{BASE_URL}/api/auth/login", json=login_data)
            return login_response.status_code == 200
            
        except Exception as e:
            print(f"Login failed: {e}")
            return False

class TestAIChatBackwardCompatibility:
    """Test backward compatibility of /ai-chat endpoint"""
    
    @pytest.fixture(scope="class")
    def test_user(self):
        """Create and login test user"""
        user = TestUser("integration_test@example.com", "testpass123")
        assert user.register_and_login(), "Failed to create/login test user"
        return user
    
    def test_ai_chat_existing_fields_preserved(self, test_user):
        """Test that existing API fields are preserved"""
        test_message = "Hello, how are you?"
        
        response = test_user.session.post(f"{BASE_URL}/ai-chat", json={
            "text": test_message
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify all existing fields are present
        assert "reply" in data, "Missing 'reply' field"
        assert "data" in data, "Missing 'data' field" 
        assert "user_id" in data, "Missing 'user_id' field"
        assert "metadata" in data, "Missing 'metadata' field"
        
        # Verify data structure unchanged
        assert "intent" in data["data"], "Missing 'intent' in data"
        assert "category" in data["data"], "Missing 'category' in data"
        assert "amount" in data["data"], "Missing 'amount' in data"
        
        # Verify metadata structure unchanged
        assert "source" in data["metadata"], "Missing 'source' in metadata"
        assert "latency_ms" in data["metadata"], "Missing 'latency_ms' in metadata"
        
        print("✅ Backward compatibility verified")
    
    def test_ai_chat_additive_fields_present(self, test_user):
        """Test that new additive fields are present"""
        test_message = "I spent 100 taka on lunch"
        
        response = test_user.session.post(f"{BASE_URL}/ai-chat", json={
            "text": test_message
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Verify new additive fields are present
        assert "ok" in data, "Missing new 'ok' field"
        assert "mode" in data, "Missing new 'mode' field"
        assert "expense_id" in data, "Missing new 'expense_id' field"
        
        # Verify new field types
        assert isinstance(data["ok"], bool), "'ok' should be boolean"
        assert isinstance(data["mode"], str), "'mode' should be string"
        # expense_id can be None or int
        assert data["expense_id"] is None or isinstance(data["expense_id"], int), "'expense_id' should be None or int"
        
        print("✅ Additive API fields verified")

class TestExpenseRepairIntegration:
    """Test expense repair functionality end-to-end"""
    
    @pytest.fixture(scope="class")
    def test_user(self):
        """Create and login test user"""
        user = TestUser("repair_test@example.com", "testpass123")
        assert user.register_and_login(), "Failed to create/login test user"
        return user
    
    def test_expense_repair_misclassified_intent(self, test_user):
        """Test repair of AI misclassified expense intent"""
        # Use a message that might be misclassified but contains clear expense patterns
        test_message = "I spent 150 taka on groceries today"
        
        response = test_user.session.post(f"{BASE_URL}/ai-chat", json={
            "text": test_message
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Should detect this as an expense (either originally or via repair)
        assert data["data"]["intent"] in ["add_expense", "expense_logged", "ai_expense_logged"], \
            f"Expected expense intent, got {data['data']['intent']}"
        
        # Should have amount detected (backward compatibility)
        assert data["data"]["amount"] is not None, "Should detect amount"
        
        # NEW: Should have amount_minor field with integer minor units
        assert data["data"]["amount_minor"] is not None, "Should have amount_minor field"
        assert data["data"]["amount_minor"] == 15000, f"Expected 15000 minor units, got {data['data']['amount_minor']}"
        
        # Should have food category (grocery -> food)
        assert data["data"]["category"] == "food", f"Expected 'food' category, got {data['data']['category']}"
        
        print("✅ Expense repair working for misclassified intent")
    
    def test_category_normalization(self, test_user):
        """Test category normalization during repair"""
        test_cases = [
            ("I bought groceries for 50 taka", "food"),
            ("Paid 30 tk for uber ride", "transport"), 
            ("Electricity bill was 200 taka", "bills"),
            ("Bought new clothes for 300 tk", "shopping")
        ]
        
        for message, expected_category in test_cases:
            response = test_user.session.post(f"{BASE_URL}/ai-chat", json={
                "text": message
            })
            
            assert response.status_code == 200, f"Expected 200, got {response.status_code}"
            data = response.json()
            
            if data["data"]["intent"] in ["add_expense", "expense_logged", "ai_expense_logged"]:
                assert data["data"]["category"] == expected_category, \
                    f"For '{message}': expected '{expected_category}', got '{data['data']['category']}'"
        
        print("✅ Category normalization working")

class TestFeatureFlagIntegration:
    """Test feature flag behavior"""
    
    @pytest.fixture(scope="class")
    def test_user(self):
        """Create and login test user"""
        user = TestUser("flag_test@example.com", "testpass123")
        assert user.register_and_login(), "Failed to create/login test user"
        return user
    
    def test_repair_enabled_by_default(self, test_user):
        """Test that repair is enabled by default"""
        test_message = "I spent 75 taka on coffee"
        
        response = test_user.session.post(f"{BASE_URL}/ai-chat", json={
            "text": test_message
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        # Should have ok=true (indicating successful processing)
        assert data["ok"] is True, "Expected ok=true"
        
        # Should have appropriate mode
        assert data["mode"] in ["expense", "chat"], f"Unexpected mode: {data['mode']}"
        
        print("✅ Feature flag system working")

class TestDatabaseConstraints:
    """Test that database constraints work correctly"""
    
    @pytest.fixture(scope="class")
    def test_user(self):
        """Create and login test user"""
        user = TestUser("db_test@example.com", "testpass123")
        assert user.register_and_login(), "Failed to create/login test user"
        return user
    
    def test_valid_categories_only(self, test_user):
        """Test that only valid categories are stored"""
        test_message = "I spent 100 taka on lunch"
        
        response = test_user.session.post(f"{BASE_URL}/ai-chat", json={
            "text": test_message
        })
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        
        data = response.json()
        
        if data["data"]["intent"] in ["add_expense", "expense_logged", "ai_expense_logged"]:
            valid_categories = {"food", "transport", "bills", "shopping", "uncategorized"}
            assert data["data"]["category"] in valid_categories, \
                f"Invalid category: {data['data']['category']}"
        
        print("✅ Database constraints working")

class TestErrorHandling:
    """Test error handling and edge cases"""
    
    @pytest.fixture(scope="class")
    def test_user(self):
        """Create and login test user"""
        user = TestUser("error_test@example.com", "testpass123")
        assert user.register_and_login(), "Failed to create/login test user"
        return user
    
    def test_empty_message_handling(self, test_user):
        """Test handling of empty messages"""
        response = test_user.session.post(f"{BASE_URL}/ai-chat", json={
            "text": ""
        })
        
        assert response.status_code == 400, f"Expected 400 for empty message, got {response.status_code}"
    
    def test_malformed_request_handling(self, test_user):
        """Test handling of malformed requests"""
        response = test_user.session.post(f"{BASE_URL}/ai-chat", json={
            "wrong_field": "test"
        })
        
        assert response.status_code == 400, f"Expected 400 for malformed request, got {response.status_code}"
    
    def test_unauthenticated_request(self):
        """Test handling of unauthenticated requests"""
        # Create new session without login
        session = requests.Session()
        
        response = session.post(f"{BASE_URL}/ai-chat", json={
            "text": "test message"
        })
        
        assert response.status_code == 401, f"Expected 401 for unauthenticated request, got {response.status_code}"
        
        print("✅ Error handling working correctly")

if __name__ == "__main__":
    # Run integration tests
    pytest.main([__file__, "-v", "-s"])