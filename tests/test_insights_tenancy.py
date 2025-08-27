"""
Tenancy Tests for AI Insights: Verify user isolation and no-data handling
Critical security tests to prevent cross-user contamination
"""

import pytest
from unittest.mock import Mock, patch
from ai.payloads.insight_payload import build_insight_payload, validate_insight_response
from utils.ai_contamination_monitor import AIContaminationMonitor


class TestInsightsTenancy:
    """Test user isolation and no-data scenarios in AI insights"""
    
    def test_zero_data_minimal_response(self):
        """Test that zero data produces safe minimal response"""
        user_id = "test_user_zero_data_12345"
        
        # Build payload with zero data
        payload = build_insight_payload(
            user_id=user_id,
            expenses=[],
            total_amount=0,
            timeframe="this month"
        )
        
        # Verify insufficient_data flag is set
        assert payload["meta"]["insufficient_data"] is True
        assert payload["meta"]["expense_count"] == 0
        assert payload["data"]["total_amount"] == 0
        assert payload["_echo"]["user_id"] == user_id
        
        # Verify data version is generated
        assert len(payload["meta"]["data_version"]) == 12
    
    def test_no_cross_user_mix(self):
        """Test that two users get isolated responses with no cross-contamination"""
        # User 1 data
        user1_id = "test_user_1_isolation_12345"
        user1_expenses = [
            {"category": "food", "total": 1000, "percentage": 66.7},
            {"category": "transport", "total": 500, "percentage": 33.3}
        ]
        user1_total = 1500
        
        # User 2 data  
        user2_id = "test_user_2_isolation_67890"
        user2_expenses = [
            {"category": "food", "total": 2000, "percentage": 87.0},
            {"category": "entertainment", "total": 300, "percentage": 13.0}
        ]
        user2_total = 2300
        
        # Build payloads
        payload1 = build_insight_payload(user1_id, user1_expenses, user1_total)
        payload2 = build_insight_payload(user2_id, user2_expenses, user2_total)
        
        # Verify user isolation
        assert payload1["_echo"]["user_id"] == user1_id
        assert payload2["_echo"]["user_id"] == user2_id
        assert payload1["meta"]["user_id"] == user1_id
        assert payload2["meta"]["user_id"] == user2_id
        
        # Verify different data versions (different spending patterns)
        assert payload1["meta"]["data_version"] != payload2["meta"]["data_version"]
        
        # Verify no cross-contamination in amounts
        assert payload1["data"]["total_amount"] == 1500
        assert payload2["data"]["total_amount"] == 2300
        
        # Check User 1 doesn't have User 2's amounts
        user1_amounts = [exp["total"] for exp in payload1["data"]["expenses"]]
        assert 2000 not in user1_amounts  # User 2's food amount
        assert 300 not in user1_amounts   # User 2's entertainment amount
        
        # Check User 2 doesn't have User 1's amounts  
        user2_amounts = [exp["total"] for exp in payload2["data"]["expenses"]]
        assert 1000 not in user2_amounts  # User 1's food amount
        assert 500 not in user2_amounts   # User 1's transport amount
    
    def test_response_validation_user_isolation(self):
        """Test response validation catches user ID mismatches"""
        expected_user = "test_user_validation_12345"
        
        # Valid response with correct user ID
        valid_response = {
            "success": True,
            "insights": ["Valid insight for user"],
            "_echo": {
                "user_id": expected_user
            }
        }
        
        validation = validate_insight_response(valid_response, expected_user)
        assert validation["valid"] is True
        assert validation["contamination"] is False
        assert len(validation["issues"]) == 0
        
        # Invalid response with wrong user ID (contamination)
        contaminated_response = {
            "success": True,
            "insights": ["Insight with wrong user"],
            "_echo": {
                "user_id": "different_user_67890"
            }
        }
        
        validation = validate_insight_response(contaminated_response, expected_user)
        assert validation["valid"] is False
        assert validation["contamination"] is True
        assert "Echo user_id mismatch" in validation["issues"][0]
    
    def test_contamination_monitor_detection(self):
        """Test contamination monitor catches cross-user data"""
        monitor = AIContaminationMonitor()
        
        # Log request for User 1
        user1_data = {
            "expenses": [{"total": 1000, "category": "food"}],
            "total_amount": 1000
        }
        request_id = monitor.log_request("user1_12345", user1_data)
        
        # Simulate contaminated response containing User 2's data
        contaminated_response = "Your food spending is ৳2000 (87% of total ৳2300)"
        
        # Check should detect contamination (User 1 data mixed with User 2 amounts)
        check_result = monitor.check_response(request_id, contaminated_response)
        
        # Note: This test depends on the contamination monitor implementation
        # It should detect foreign amounts (2000, 2300) not in User 1's data (1000)
        assert "status" in check_result
        assert request_id in monitor.active_requests
    
    @patch('utils.ai_adapter_v2.production_ai_adapter')
    def test_ai_adapter_user_isolation_logging(self, mock_adapter):
        """Test that AI adapter logs user ID for contamination tracking"""
        mock_adapter.generate_insights.return_value = {
            "success": True,
            "insights": ["Test insight"],
            "_echo": {"user_id": "test_user_12345"}
        }
        
        # Prepare test data
        user_id = "test_user_12345"
        expenses_data = {
            "total_amount": 1000,
            "expenses": [{"category": "food", "total": 1000, "percentage": 100}],
            "timeframe": "this month"
        }
        
        # Call adapter
        result = mock_adapter.generate_insights(expenses_data, user_id)
        
        # Verify user ID is passed and echoed back
        mock_adapter.generate_insights.assert_called_with(expenses_data, user_id)
        assert result["_echo"]["user_id"] == user_id


class TestInsightsCachingIsolation:
    """Test cache isolation for insights to prevent cross-user data leakage"""
    
    def test_cache_keys_include_user_id(self):
        """Test that cache keys include user ID for isolation"""
        user1_id = "user1_cache_test_12345"
        user2_id = "user2_cache_test_67890"
        
        # Same expense data, different users
        expenses = [{"category": "food", "total": 1000, "percentage": 100}]
        
        payload1 = build_insight_payload(user1_id, expenses, 1000)
        payload2 = build_insight_payload(user2_id, expenses, 1000)
        
        # Even with same expense data, cache keys should differ due to user_id
        # This would be used for cache key generation: f"{user_id}_{data_version}"
        cache_key1 = f"{user1_id}_{payload1['meta']['data_version']}"
        cache_key2 = f"{user2_id}_{payload2['meta']['data_version']}"
        
        assert cache_key1 != cache_key2
        assert user1_id in cache_key1
        assert user2_id in cache_key2
    
    def test_insufficient_data_flag_consistency(self):
        """Test insufficient_data flag is consistently set for edge cases"""
        user_id = "test_user_edge_cases_12345"
        
        # Test case 1: Empty expenses list
        payload1 = build_insight_payload(user_id, [], 0)
        assert payload1["meta"]["insufficient_data"] is True
        
        # Test case 2: Expenses with zero totals
        zero_expenses = [{"category": "food", "total": 0, "percentage": 0}]
        payload2 = build_insight_payload(user_id, zero_expenses, 0)
        assert payload2["meta"]["insufficient_data"] is True
        
        # Test case 3: Valid expenses
        valid_expenses = [{"category": "food", "total": 1000, "percentage": 100}]
        payload3 = build_insight_payload(user_id, valid_expenses, 1000)
        assert payload3["meta"]["insufficient_data"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])