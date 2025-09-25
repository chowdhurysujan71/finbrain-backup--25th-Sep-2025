"""
Phase 3 UAT: AI resilience and fallback system
Tests AI processing reliability without affecting routing or data systems
"""
import json
import time

import pytest

from utils.ai_resilience import AIMode, AIProvider, AIResponse, ResilientAIAdapter


class TestAIResilience:
    """Test AI resilience and fallback functionality"""
    
    def test_stub_mode_operation(self):
        """Test AI adapter works in stub mode for CI/testing"""
        adapter = ResilientAIAdapter(stub_mode=True)
        
        response = adapter.generate_insight("test_user", {"total_amount": 1000, "expense_count": 5})
        
        assert response.mode == AIMode.STUB
        assert response.provider == AIProvider.LOCAL
        assert response.confidence == 1.0
        assert "Stub AI Response" in response.content
        assert not response.fallback_used
    
    def test_stub_mode_categorization(self):
        """Test expense categorization in stub mode"""
        adapter = ResilientAIAdapter(stub_mode=True)
        
        response = adapter.categorize_expense("lunch 500 taka", 500.0)
        
        assert response.mode == AIMode.STUB
        assert response.confidence == 1.0
        
        # Parse categorization result
        result = json.loads(response.content)
        assert "category" in result
        assert "confidence" in result
    
    def test_local_fallback_insights(self):
        """Test local fallback insight generation"""
        adapter = ResilientAIAdapter(fallback_enabled=True)
        
        # Test different expense scenarios
        test_cases = [
            {"total_amount": 2500, "expense_count": 8, "expected_pattern": "High spending"},
            {"total_amount": 800, "expense_count": 20, "expected_pattern": "Frequent transactions"},
            {"total_amount": 500, "expense_count": 3, "expected_pattern": "Expenses tracked"}
        ]
        
        for case in test_cases:
            # Force fallback by opening circuit breaker
            adapter.circuit_breaker["is_open"] = True
            
            response = adapter.generate_insight("test_user", case)
            
            assert response.mode == AIMode.LOCAL_FALLBACK
            assert response.provider == AIProvider.LOCAL
            assert case["expected_pattern"] in response.content
            assert response.confidence > 0.5
    
    def test_local_categorization_rules(self):
        """Test local rule-based categorization"""
        adapter = ResilientAIAdapter()
        adapter.circuit_breaker["is_open"] = True  # Force fallback
        
        test_cases = [
            {"text": "lunch at restaurant", "expected": "Food & Dining"},
            {"text": "bus fare", "expected": "Transportation"},
            {"text": "shopping at market", "expected": "Shopping"},
            {"text": "movie tickets", "expected": "Entertainment"},
            {"text": "খাবারে চা", "expected": "Food & Dining"},
            {"text": "random expense", "expected": "Other"}
        ]
        
        for case in test_cases:
            response = adapter.categorize_expense(case["text"], 100.0)
            
            result = json.loads(response.content)
            assert result["category"] == case["expected"]
            assert response.mode == AIMode.LOCAL_FALLBACK
    
    def test_circuit_breaker_functionality(self):
        """Test circuit breaker opens after failures"""
        adapter = ResilientAIAdapter(max_retries=1)
        
        # Simulate repeated failures by making circuit breaker fail
        for i in range(6):  # Exceeds failure threshold (5)
            adapter._record_failure()
        
        assert adapter.circuit_breaker["is_open"]
        assert adapter.circuit_breaker["failures"] >= 5
        
        # Should use fallback when circuit breaker is open
        response = adapter.generate_insight("test_user", {"total_amount": 1000, "expense_count": 5})
        assert response.mode == AIMode.LOCAL_FALLBACK
    
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker recovers after timeout"""
        adapter = ResilientAIAdapter()
        
        # Open circuit breaker
        adapter.circuit_breaker["is_open"] = True
        adapter.circuit_breaker["last_failure"] = time.time() - 400  # 400 seconds ago (> 300s timeout)
        
        # Should recover and close circuit breaker
        assert not adapter._is_circuit_breaker_open()
        assert adapter.circuit_breaker["failures"] == 0

class TestAIResponseValidation:
    """Test AI response structure and validation"""
    
    def test_ai_response_structure(self):
        """Test AI response contains required fields"""
        adapter = ResilientAIAdapter(stub_mode=True)
        response = adapter.generate_insight("test_user", {"total_amount": 1000, "expense_count": 5})
        
        # Check required fields
        assert hasattr(response, 'content')
        assert hasattr(response, 'provider')
        assert hasattr(response, 'mode')
        assert hasattr(response, 'confidence')
        assert hasattr(response, 'processing_time_ms')
        assert hasattr(response, 'tokens_used')
        assert hasattr(response, 'retry_count')
        assert hasattr(response, 'fallback_used')
        assert hasattr(response, 'metadata')
        
        # Check types
        assert isinstance(response.content, str)
        assert isinstance(response.confidence, float)
        assert isinstance(response.processing_time_ms, float)
        assert isinstance(response.tokens_used, int)
        assert isinstance(response.retry_count, int)
        assert isinstance(response.fallback_used, bool)
        assert isinstance(response.metadata, dict)
    
    def test_response_content_quality(self):
        """Test response content meets quality standards"""
        adapter = ResilientAIAdapter(stub_mode=True)
        
        # Test insight response
        insight_response = adapter.generate_insight("test_user", {"total_amount": 1500, "expense_count": 10})
        assert len(insight_response.content) > 10  # Non-empty meaningful content
        assert insight_response.confidence >= 0.0 and insight_response.confidence <= 1.0
        
        # Test categorization response
        cat_response = adapter.categorize_expense("lunch 500 taka", 500.0)
        cat_data = json.loads(cat_response.content)
        assert "category" in cat_data
        assert "confidence" in cat_data
        assert isinstance(cat_data["confidence"], (int, float))

class TestPerformanceAndReliability:
    """Test performance and reliability characteristics"""
    
    def test_response_time_acceptable(self):
        """Test AI responses are generated within acceptable time"""
        adapter = ResilientAIAdapter(stub_mode=True)
        
        start_time = time.time()
        response = adapter.generate_insight("test_user", {"total_amount": 1000, "expense_count": 5})
        end_time = time.time()
        
        total_time_ms = (end_time - start_time) * 1000
        assert total_time_ms < 500  # Less than 500ms for stub mode
        assert response.processing_time_ms > 0
    
    def test_fallback_reliability(self):
        """Test fallback system provides consistent responses"""
        adapter = ResilientAIAdapter(fallback_enabled=True)
        adapter.circuit_breaker["is_open"] = True  # Force fallback
        
        # Test multiple calls for consistency
        expense_data = {"total_amount": 1200, "expense_count": 8}
        
        responses = []
        for _ in range(5):
            response = adapter.generate_insight("test_user", expense_data)
            responses.append(response)
        
        # All should use fallback
        for response in responses:
            assert response.mode == AIMode.LOCAL_FALLBACK
            assert response.provider == AIProvider.LOCAL
            assert len(response.content) > 0
            assert response.confidence > 0.5
    
    def test_error_handling_graceful(self):
        """Test graceful error handling"""
        adapter = ResilientAIAdapter(fallback_enabled=True)
        
        # Test with various invalid inputs
        invalid_inputs = [
            {"total_amount": None, "expense_count": 5},
            {"total_amount": -100, "expense_count": 0},
            {},  # Empty data
        ]
        
        for invalid_data in invalid_inputs:
            try:
                response = adapter.generate_insight("test_user", invalid_data)
                # Should handle gracefully and return some response
                assert isinstance(response, AIResponse)
                assert len(response.content) > 0
            except Exception as e:
                # If it raises an exception, it should be informative
                assert len(str(e)) > 0

class TestIntegrationScenarios:
    """Test integration scenarios with existing systems"""
    
    def test_bilingual_content_handling(self):
        """Test AI handles bilingual content correctly"""
        adapter = ResilientAIAdapter(stub_mode=True)
        
        # Bengali expense text
        response = adapter.categorize_expense("আজ চা ৫০ টাকা", 50.0)
        
        assert response.content is not None
        result = json.loads(response.content)
        assert "category" in result
    
    def test_health_status_reporting(self):
        """Test health status reporting"""
        adapter = ResilientAIAdapter()
        
        health = adapter.get_health_status()
        
        assert "primary_provider" in health
        assert "mode" in health
        assert "fallback_enabled" in health
        assert "circuit_breaker" in health
        assert "last_check" in health
        
        # Check circuit breaker status structure
        cb_status = health["circuit_breaker"]
        assert "is_open" in cb_status
        assert "failures" in cb_status
        assert "threshold" in cb_status
    
    def test_different_provider_modes(self):
        """Test different AI provider configurations"""
        providers = [AIProvider.GEMINI, AIProvider.OPENAI, AIProvider.LOCAL]
        
        for provider in providers:
            adapter = ResilientAIAdapter(primary_provider=provider, stub_mode=True)
            response = adapter.generate_insight("test_user", {"total_amount": 1000, "expense_count": 5})
            
            # In stub mode, should always use LOCAL provider
            assert response.provider == AIProvider.LOCAL
            assert response.mode == AIMode.STUB

def run_phase3_uat():
    """Run Phase 3 UAT and return results"""
    import subprocess
    import sys
    
    # Run the tests
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/test_phase3_ai_resilience.py", 
        "-v", "--tb=short"
    ], capture_output=True, text=True, cwd=".")
    
    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "success": result.returncode == 0
    }

if __name__ == "__main__":
    # Allow direct execution for testing
    pytest.main([__file__, "-v"])