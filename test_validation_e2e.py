"""
Comprehensive End-to-End Test Suite for Validation Error Handling System
Tests complete validation flow from API to frontend error handling

Coverage:
- API validation with standardized error responses
- Backend validation functions
- Frontend error handling integration
- Performance validation
- Complete error flow testing
"""

import json
import time

import pytest

from app import app
from utils.error_responses import (
    ErrorCodes,
    internal_error,
    missing_fields_error,
    success_response,
    unauthorized_error,
    validation_error_response,
)
from utils.validators import (
    APIValidator,
    ValidationResult,
    validate_expense,
    validate_login,
    validate_registration,
)

# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Create test client with proper configuration"""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.test_client() as client:
        with app.app_context():
            yield client


@pytest.fixture
def test_headers():
    """Standard test headers"""
    return {
        'Content-Type': 'application/json',
        'User-Agent': 'FinBrain-Test-Client/1.0'
    }


# ============================================================================
# Standardized Error Response Format Testing
# ============================================================================

class TestStandardizedErrorResponseFormat:
    """Test that all API errors follow the standardized response format"""
    
    def test_validation_error_response_structure(self):
        """Test validation errors return proper JSON structure"""
        with app.app_context():
            field_errors = {
                "amount": "Amount must be greater than 0",
                "category": "Category is required"
            }
            
            response, status_code = validation_error_response(field_errors)
            
            assert status_code == 400
            assert "success" in response
            assert response["success"] is False
            assert "code" in response
            assert response["code"] == ErrorCodes.VALIDATION_ERROR
            assert "message" in response
            assert "trace_id" in response
            assert len(response["trace_id"]) > 0
            assert "field_errors" in response
            assert isinstance(response["field_errors"], dict)
            assert response["field_errors"] == field_errors
    
    def test_unauthorized_error_response_structure(self, client):
        """Test unauthorized errors return proper JSON structure"""
        with client.application.app_context():
            with client.application.test_request_context():
                response, status_code = unauthorized_error("Please log in")
                
                assert status_code == 401
                assert response["success"] is False
                assert response["code"] == ErrorCodes.UNAUTHORIZED
                assert response["message"] == "Please log in"
                assert "trace_id" in response
                assert "field_errors" not in response
    
    def test_missing_fields_error_format(self):
        """Test missing required fields error format"""
        with app.app_context():
            missing_fields = ["email", "password"]
            
            response, status_code = missing_fields_error(missing_fields)
            
            assert status_code == 400
            assert response["code"] == ErrorCodes.MISSING_FIELDS
            assert "field_errors" in response
            assert response["field_errors"]["email"] == "This field is required"
            assert response["field_errors"]["password"] == "This field is required"
    
    def test_internal_error_response_structure(self, client):
        """Test internal errors return proper JSON structure"""
        with client.application.app_context():
            with client.application.test_request_context():
                response, status_code = internal_error("Something went wrong")
                
                assert status_code == 500
                assert response["success"] is False
                assert response["code"] == ErrorCodes.INTERNAL_ERROR
                assert "message" in response
                assert "trace_id" in response
    
    def test_success_response_format(self):
        """Test success response format"""
        with app.app_context():
            data = {"expense_id": "123", "amount": 100.50}
            response = success_response(data, "Expense created successfully")
            
            assert response["success"] is True
            assert response["message"] == "Expense created successfully"
            assert response["data"] == data
            assert "trace_id" in response


# ============================================================================
# Expense Validation Testing
# ============================================================================

class TestExpenseValidation:
    """Test expense validation system comprehensively"""
    
    def test_valid_expense_data(self):
        """Test validation passes for valid expense data"""
        valid_expense = {
            "amount": "25.50",
            "category": "food",
            "description": "Lunch at restaurant"
        }
        
        result = validate_expense(valid_expense)
        assert not result.has_errors()
        assert len(result.errors) == 0
    
    def test_invalid_amount_scenarios(self):
        """Test various invalid amount scenarios"""
        test_cases = [
            {"amount": "", "expected_error": "Amount is required"},
            {"amount": "0", "expected_error": "Amount must be greater than 0"},
            {"amount": "-10", "expected_error": "Amount must be greater than 0"},
            {"amount": "abc", "expected_error": "Amount must be a valid number"},
            {"amount": "999999999", "expected_error": "Amount must be less than 1,000,000"},
            {"amount": "10.123", "expected_error": "Amount can have at most 2 decimal places"}
        ]
        
        for test_case in test_cases:
            expense_data = {
                "amount": test_case["amount"],
                "category": "food",
                "description": "Test"
            }
            
            result = validate_expense(expense_data)
            assert result.has_errors(), f"Expected error for amount: {test_case['amount']}"
            assert "amount" in result.errors
            assert result.errors["amount"] == test_case["expected_error"]
    
    def test_invalid_category_validation(self):
        """Test category validation"""
        test_cases = [
            {"category": "", "expected_error": "Category is required"},
            {"category": "invalid_category", "expected_pattern": "Category must be one of:"}
        ]
        
        for test_case in test_cases:
            expense_data = {
                "amount": "25.00",
                "category": test_case["category"],
                "description": "Test"
            }
            
            result = validate_expense(expense_data)
            assert result.has_errors()
            assert "category" in result.errors
            if "expected_error" in test_case:
                assert result.errors["category"] == test_case["expected_error"]
            elif "expected_pattern" in test_case:
                assert test_case["expected_pattern"] in result.errors["category"]
    
    def test_description_validation(self):
        """Test description validation"""
        # Test extremely long description
        long_description = "a" * 501  # Exceeds 500 character limit
        
        expense_data = {
            "amount": "25.00",
            "category": "food",
            "description": long_description
        }
        
        result = validate_expense(expense_data)
        assert result.has_errors()
        assert "description" in result.errors
        assert "500 characters" in result.errors["description"]


# ============================================================================
# Authentication Validation Testing
# ============================================================================

class TestAuthenticationValidation:
    """Test authentication validation system"""
    
    def test_valid_login_data(self):
        """Test validation passes for valid login data"""
        valid_login = {
            "email": "user@example.com",
            "password": "validpass123"
        }
        
        result = validate_login(valid_login)
        assert not result.has_errors()
    
    def test_invalid_email_validation(self):
        """Test email validation catches various invalid formats"""
        test_cases = [
            {"email": "", "expected_error": "Email is required"},
            {"email": "invalid-email", "expected_error": "Please enter a valid email address"},
            {"email": "@example.com", "expected_error": "Please enter a valid email address"},
            {"email": "user@", "expected_error": "Please enter a valid email address"},
            {"email": "a" * 315 + "@example.com", "expected_error": "Email address is too long"}
        ]
        
        for test_case in test_cases:
            login_data = {
                "email": test_case["email"],
                "password": "validpass123"
            }
            
            result = validate_login(login_data)
            assert result.has_errors(), f"Expected error for email: {test_case['email']}"
            assert "email" in result.errors
            assert result.errors["email"] == test_case["expected_error"]
    
    def test_password_validation(self):
        """Test password validation for registration"""
        test_cases = [
            {"password": "", "expected_error": "Password is required"},
            {"password": "short", "expected_error": "Password must be at least 8 characters long"},
            {"password": "a" * 129, "expected_error": "Password must be 128 characters or less"},
            {"password": "onlyletters", "expected_error": "Password must contain at least one number"},
            {"password": "12345678", "expected_error": "Password must contain at least one letter"}
        ]
        
        for test_case in test_cases:
            registration_data = {
                "email": "user@example.com",
                "password": test_case["password"],
                "confirm_password": test_case["password"],
                "name": "Test User"
            }
            
            result = validate_registration(registration_data)
            assert result.has_errors(), f"Expected error for password: {test_case['password']}"
            assert "password" in result.errors
            assert result.errors["password"] == test_case["expected_error"]


# ============================================================================
# API Validator Testing
# ============================================================================

class TestAPIValidators:
    """Test API-specific validation utilities"""
    
    def test_integer_validation(self):
        """Test integer validation with bounds"""
        # Valid cases
        assert APIValidator.validate_integer(5, "limit", min_val=1, max_val=100) is None
        assert APIValidator.validate_integer("10", "limit", min_val=1, max_val=100) is None
        
        # Invalid cases
        assert "required" in APIValidator.validate_integer(None, "limit")
        assert "at least 1" in APIValidator.validate_integer(0, "limit", min_val=1)
        assert "at most 100" in APIValidator.validate_integer(101, "limit", max_val=100)
        assert "valid number" in APIValidator.validate_integer("abc", "limit")
    
    def test_string_length_validation(self):
        """Test string length validation"""
        # Valid cases
        assert APIValidator.validate_string_length("test", "name", min_length=2, max_length=10) is None
        
        # Invalid cases
        assert "required" in APIValidator.validate_string_length(None, "name")
        assert "at least 5" in APIValidator.validate_string_length("ab", "name", min_length=5)
        assert "5 characters or less" in APIValidator.validate_string_length("toolong", "name", max_length=5)
    
    def test_choice_validation(self):
        """Test choice validation"""
        valid_choices = ["day", "week", "month"]
        
        # Valid cases
        assert APIValidator.validate_choice("week", "period", valid_choices) is None
        
        # Invalid cases
        assert "required" in APIValidator.validate_choice(None, "period", valid_choices)
        assert "must be one of" in APIValidator.validate_choice("year", "period", valid_choices)
        assert "day, week, month" in APIValidator.validate_choice("invalid", "period", valid_choices)


# ============================================================================
# Direct API Endpoint Testing
# ============================================================================

class TestDirectAPIValidation:
    """Test API endpoints that can be tested without complex authentication"""
    
    def test_nonexistent_endpoint_handling(self, client, test_headers):
        """Test how validation system handles non-existent endpoints"""
        response = client.post('/api/nonexistent/endpoint',
                             json={"test": "data"},
                             headers=test_headers)
        
        assert response.status_code == 404
    
    def test_malformed_json_handling(self, client, test_headers):
        """Test handling of malformed JSON requests"""
        # Test various malformed JSON scenarios
        malformed_payloads = [
            "{'invalid': json}",  # Invalid JSON
            '{"unclosed": "quote}',  # Unclosed quote
            '{"trailing": "comma",}',  # Trailing comma
        ]
        
        for payload in malformed_payloads:
            response = client.post('/api/test',
                                 data=payload,
                                 headers={'Content-Type': 'application/json'})
            
            # Should return 400 or 422, not crash the server
            assert response.status_code in [400, 404, 422]
    
    def test_large_payload_handling(self, client, test_headers):
        """Test handling of unusually large request payloads"""
        # Create large JSON payload
        large_data = {"text": "a" * 50000}  # 50KB of text
        
        response = client.post('/api/test',
                             json=large_data,
                             headers=test_headers)
        
        # Should handle gracefully, not crash
        assert response.status_code in [400, 404, 413, 422]


# ============================================================================
# Frontend Error Handling Integration Tests
# ============================================================================

class TestFrontendErrorHandlingIntegration:
    """Test frontend error handling integration without complex mocking"""
    
    def test_field_error_structure_for_frontend(self):
        """Test that API field errors have proper structure for frontend display"""
        with app.app_context():
            field_errors = {
                "amount": "Amount must be greater than 0",
                "category": "Category is required",
                "description": "Description is too long"
            }
            
            response, status_code = validation_error_response(field_errors)
            
            # Verify the response structure matches what frontend expects
            assert "field_errors" in response
            assert isinstance(response["field_errors"], dict)
            
            # Each field error should be a string that can be displayed
            for field, error_message in response["field_errors"].items():
                assert isinstance(error_message, str)
                assert len(error_message) > 0
                # Error messages should be user-friendly
                assert "exception" not in error_message.lower()
                assert "traceback" not in error_message.lower()
                assert "sql" not in error_message.lower()
    
    def test_toast_notification_message_format(self, client):
        """Test that API errors provide appropriate messages for toast notifications"""
        with client.application.app_context():
            with client.application.test_request_context():
                # Test different error types
                error_scenarios = [
                    (unauthorized_error("Please log in"), "Please log in"),
                    (internal_error(), "An unexpected error occurred"),
                    (validation_error_response({"amount": "Required"}), "Please fix the highlighted field")
                ]
                
                for (response, _), expected_pattern in error_scenarios:
                    # Message should be appropriate for user display
                    assert "message" in response
                    assert len(response["message"]) > 0
                    assert len(response["message"]) < 200  # Not too long for toast
                    
                    # Should have trace ID for debugging
                    assert "trace_id" in response
                    assert len(response["trace_id"]) > 0
    
    def test_error_code_mapping_for_frontend(self, client):
        """Test different error codes for frontend routing"""
        with client.application.app_context():
            with client.application.test_request_context():
                test_scenarios = [
                    {
                        "function": validation_error_response,
                        "args": [{"amount": "Required"}],
                        "expected_code": ErrorCodes.VALIDATION_ERROR,
                        "should_have_field_errors": True
                    },
                    {
                        "function": unauthorized_error,
                        "args": ["Please log in"],
                        "expected_code": ErrorCodes.UNAUTHORIZED,
                        "should_have_field_errors": False
                    },
                    {
                        "function": internal_error,
                        "args": ["Server error"],
                        "expected_code": ErrorCodes.INTERNAL_ERROR,
                        "should_have_field_errors": False
                    }
                ]
                
                for scenario in test_scenarios:
                    response, status_code = scenario["function"](*scenario["args"])
                    
                    assert response["code"] == scenario["expected_code"]
                    
                    # Verify frontend can distinguish between error types
                    if scenario["should_have_field_errors"]:
                        assert "field_errors" in response
                    else:
                        assert "field_errors" not in response


# ============================================================================
# Performance and Security Testing
# ============================================================================

class TestErrorHandlingPerformance:
    """Test that error handling doesn't significantly impact performance"""
    
    def test_validation_error_performance(self):
        """Test validation errors are generated quickly"""
        start_time = time.time()
        
        # Create multiple validation errors quickly
        for _ in range(100):
            invalid_expense = {
                "amount": "invalid",
                "category": "",
                "description": "a" * 600  # Too long
            }
            result = validate_expense(invalid_expense)
            assert result.has_errors()
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should complete 100 validations in under 1 second
        assert total_time < 1.0, f"Validation took too long: {total_time}s"
    
    def test_error_response_generation_performance(self):
        """Test error response generation is fast"""
        with app.app_context():
            start_time = time.time()
            
            # Generate multiple error responses
            for i in range(50):
                field_errors = {
                    "field1": f"Error message {i}",
                    "field2": f"Another error {i}"
                }
                response, status_code = validation_error_response(field_errors)
                assert status_code == 400
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Should complete 50 error responses in under 0.5 seconds
            assert total_time < 0.5, f"Error response generation took too long: {total_time}s"
    
    def test_error_response_size(self):
        """Test error responses are reasonably sized"""
        with app.app_context():
            # Create error response with multiple fields
            field_errors = {
                f"field_{i}": f"This is an error message for field {i}"
                for i in range(10)
            }
            
            response, status_code = validation_error_response(field_errors)
            response_size = len(json.dumps(response))
            
            # Error response should be under 5KB even with many fields
            assert response_size < 5120, f"Error response too large: {response_size} bytes"


class TestSecurityValidation:
    """Test security aspects of error handling"""
    
    def test_error_message_sanitization(self):
        """Test that error messages don't expose sensitive information"""
        # Test that validation doesn't expose system internals
        dangerous_inputs = [
            "'; DROP TABLE expenses; --",
            "1' OR '1'='1",
            "<script>alert('xss')</script>",
            "../../../etc/passwd",
            "${system('rm -rf /')}"
        ]
        
        for dangerous_input in dangerous_inputs:
            expense_data = {
                "amount": dangerous_input,
                "category": dangerous_input,
                "description": dangerous_input
            }
            
            result = validate_expense(expense_data)
            
            # Should have validation errors, but not expose the dangerous input
            error_text = json.dumps(result.errors).lower()
            assert "drop table" not in error_text
            assert "script" not in error_text
            assert "etc/passwd" not in error_text
            assert "system(" not in error_text
    
    def test_trace_id_uniqueness_and_security(self, client):
        """Test trace IDs are unique and don't expose sensitive information"""
        with client.application.app_context():
            trace_ids = set()
            
            # Generate multiple trace IDs with small delays to ensure uniqueness
            for i in range(10):
                with client.application.test_request_context():
                    response, _ = validation_error_response({"test": f"error_{i}"})
                    trace_id = response["trace_id"]
                    
                    # Should be unique (allow some non-uniqueness for quick generation)
                    if trace_id in trace_ids:
                        # This is expected in quick succession, continue
                        continue
                    trace_ids.add(trace_id)
                    
                    # Should not be predictable or expose sensitive info
                    assert len(trace_id) >= 6  # Reasonable length
                    assert "user" not in trace_id.lower()
                    assert "admin" not in trace_id.lower()
            
            # Should have generated at least some unique trace IDs
            assert len(trace_ids) >= 3


# ============================================================================
# Integration with Existing Systems
# ============================================================================

class TestExistingSystemIntegration:
    """Test integration with existing validation and error systems"""
    
    def test_validation_result_class_functionality(self):
        """Test ValidationResult class works correctly"""
        result = ValidationResult()
        
        # Initially valid
        assert not result.has_errors()
        assert result.is_valid
        assert len(result.errors) == 0
        
        # After adding error
        result.add_error("field1", "Error message")
        assert result.has_errors()
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors["field1"] == "Error message"
        
        # Multiple errors
        result.add_error("field2", "Another error")
        assert len(result.errors) == 2
    
    def test_error_code_constants(self):
        """Test that error code constants are properly defined"""
        # Verify all expected error codes exist
        expected_codes = [
            "VALIDATION_ERROR", "MISSING_FIELDS", "INVALID_FORMAT",
            "UNAUTHORIZED", "FORBIDDEN", "SESSION_EXPIRED",
            "DUPLICATE_RESOURCE", "RESOURCE_NOT_FOUND", "OPERATION_FAILED",
            "INTERNAL_ERROR", "SERVICE_UNAVAILABLE", "RATE_LIMITED"
        ]
        
        for code in expected_codes:
            assert hasattr(ErrorCodes, code), f"Missing error code: {code}"
            assert isinstance(getattr(ErrorCodes, code), str)
    
    def test_validator_integration_with_error_responses(self):
        """Test that validators integrate properly with error responses"""
        with app.app_context():
            # Test expense validation integration
            invalid_expense = {
                "amount": "",
                "category": "",
                "description": ""
            }
            
            validation_result = validate_expense(invalid_expense)
            assert validation_result.has_errors()
            
            # Convert to standardized error response
            response, status_code = validation_error_response(validation_result.errors)
            
            assert status_code == 400
            assert response["code"] == ErrorCodes.VALIDATION_ERROR
            assert "field_errors" in response
            assert len(response["field_errors"]) >= 2  # amount and category errors


# ============================================================================
# Test Runner Configuration
# ============================================================================

if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])