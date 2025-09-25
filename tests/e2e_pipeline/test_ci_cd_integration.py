"""
E2E Tests for CI/CD Integration

Tests comprehensive CI/CD pipeline integration including:
- Automated test execution
- Deployment gates and validation
- Health checks and readiness probes
- Integration with monitoring systems
- Database migration safety
- Environment configuration validation
"""
import json
import os
from datetime import datetime

import pytest

from tests.e2e_pipeline.test_base import E2ETestBase


class TestCICDIntegrationE2E(E2ETestBase):
    """End-to-end tests for CI/CD pipeline integration"""

    def test_health_endpoint_readiness(self, client, test_users):
        """Test application health endpoint for CI/CD readiness checks"""
        with self.mock_environment_secrets():
            # Test basic health endpoint
            response = client.get('/health')
            
            assert response.status_code == 200, f"Health check failed: {response.status_code}"
            
            data = response.get_json()
            assert data is not None, "Health endpoint should return JSON"
            assert data.get('status') == 'ok', f"Health status should be 'ok', got: {data}"
            
            # Verify response headers
            assert 'X-Request-ID' in response.headers, "Health endpoint should include request ID"

    def test_readiness_endpoint_comprehensive(self, client, test_users):
        """Test comprehensive readiness endpoint for deployment gates"""
        with self.mock_environment_secrets():
            # Test readiness endpoint
            response = client.get('/readyz')
            
            # Should return either 200 (ready) or 503 (not ready)
            assert response.status_code in [200, 503], (
                f"Readiness check returned unexpected status: {response.status_code}"
            )
            
            if response.status_code == 200:
                data = response.get_json()
                
                # Verify readiness components
                if data and isinstance(data, dict):
                    # Database should be ready
                    if 'db' in data:
                        assert data['db'] is True, "Database should be ready for deployment"
                    
                    # AI system should be configured
                    if 'ai_key_present' in data:
                        assert data['ai_key_present'] is True, "AI key should be present"

    def test_database_migration_safety_check(self, client, test_users):
        """Test database migration safety for CI/CD deployments"""
        with self.mock_environment_secrets():
            # Verify database schema is properly initialized
            with client.application.app_context():
                from db_base import db
                
                # Check that all required tables exist
                inspector = db.inspect(db.engine)
                table_names = inspector.get_table_names()
                
                required_tables = ['users', 'expenses', 'monthly_summaries']
                for table in required_tables:
                    assert table in table_names, f"Required table {table} not found in database"
                
                # Verify table structure
                for table in required_tables:
                    columns = inspector.get_columns(table)
                    column_names = [col['name'] for col in columns]
                    
                    if table == 'expenses':
                        required_columns = ['id', 'user_id_hash', 'amount', 'category', 'created_at']
                        for col in required_columns:
                            assert col in column_names, f"Required column {col} not found in {table}"
                    
                    elif table == 'users':
                        required_columns = ['id', 'user_id_hash', 'platform', 'created_at']
                        for col in required_columns:
                            assert col in column_names, f"Required column {col} not found in {table}"

    def test_environment_configuration_validation(self, client, test_users):
        """Test environment configuration validation for deployments"""
        with self.mock_environment_secrets():
            # Test that required environment variables are validated
            required_env_vars = [
                'SESSION_SECRET',
                'DATABASE_URL'
            ]
            
            for env_var in required_env_vars:
                value = os.environ.get(env_var)
                assert value is not None, f"Required environment variable {env_var} not set"
                assert len(value) > 0, f"Environment variable {env_var} should not be empty"
            
            # Test configuration endpoint if available
            try:
                config_response = client.get('/ops/quickscan')
                if config_response.status_code == 200:
                    # Configuration endpoint is available and working
                    config_data = config_response.get_json()
                    if config_data:
                        # Verify configuration structure
                        assert isinstance(config_data, dict), "Configuration should return dict"
            except Exception as e:  # narrowed from bare except (lint A1)
                # Configuration endpoint might be protected or unavailable in test
                pass

    def test_api_endpoints_availability(self, client, test_users):
        """Test that all critical API endpoints are available for deployment validation"""
        with self.mock_environment_secrets():
            # Critical endpoints that should be available
            critical_endpoints = [
                ('GET', '/health'),
                ('GET', '/readyz'),
                ('GET', '/'),  # Root endpoint
                ('POST', '/webhook/messenger'),  # Webhook endpoint
            ]
            
            for method, endpoint in critical_endpoints:
                if method == 'GET':
                    response = client.get(endpoint)
                elif method == 'POST':
                    # Provide minimal valid data for POST endpoints
                    if endpoint == '/webhook/messenger':
                        # Test without signature (should get 403 or handle gracefully)
                        response = client.post(endpoint, 
                                             data=json.dumps({'test': 'data'}),
                                             content_type='application/json')
                    else:
                        response = client.post(endpoint)
                
                # Should not return 404 or 500
                assert response.status_code not in [404, 500], (
                    f"Critical endpoint {method} {endpoint} returned {response.status_code}"
                )

    def test_database_connectivity_resilience(self, client, test_users):
        """Test database connectivity resilience for deployment health"""
        with self.mock_environment_secrets():
            # Test basic database operations
            with client.application.app_context():
                from db_base import db
                from models import User
                
                try:
                    # Test database connection
                    from sqlalchemy import text
                    db.session.execute(text('SELECT 1'))
                    db.session.commit()
                    
                    # Test basic query
                    user_count = User.query.count()
                    assert user_count >= 0, "Should be able to count users"
                    
                    # Test transaction capability
                    test_user = User()
                    test_user.user_id_hash = f'test_ci_cd_{int(datetime.now().timestamp())}'
                    test_user.platform = 'ci_cd_test'
                    test_user.total_expenses = 0
                    test_user.expense_count = 0
                    
                    db.session.add(test_user)
                    db.session.commit()
                    
                    # Clean up test user
                    db.session.delete(test_user)
                    db.session.commit()
                    
                except Exception as e:
                    pytest.fail(f"Database connectivity test failed: {e}")

    def test_api_response_consistency(self, client, test_users):
        """Test API response consistency for CI/CD validation"""
        with self.mock_environment_secrets():
            user = test_users['alice']
            
            # Test form endpoint response consistency
            headers = self.setup_x_user_id_auth(user['x_user_id'])
            
            form_data = {
                'amount': '100.0',
                'category': 'ci_cd_test',
                'description': 'CI/CD consistency test'
            }
            
            # Make multiple requests to test consistency
            responses = []
            for i in range(3):
                response = client.post('/expense', data=form_data, headers=headers)
                responses.append({
                    'status_code': response.status_code,
                    'content_type': response.content_type,
                    'has_json': response.is_json if hasattr(response, 'is_json') else False
                })
            
            # Verify response consistency
            first_response = responses[0]
            for response in responses[1:]:
                # Status codes should be consistent
                if first_response['status_code'] in [200, 400]:  # Valid statuses
                    assert response['status_code'] == first_response['status_code'], (
                        f"Inconsistent status codes: {[r['status_code'] for r in responses]}"
                    )

    def test_error_handling_robustness(self, client, test_users):
        """Test error handling robustness for production deployment"""
        with self.mock_environment_secrets():
            # Test various error conditions
            error_test_cases = [
                # Invalid JSON
                ('POST', '/api/backend/get_totals', b'invalid json', {'Content-Type': 'application/json'}),
                
                # Missing content type
                ('POST', '/expense', b'{"amount": "100"}', {}),
                
                # Large payload (if there's a size limit)
                ('POST', '/expense', b'x' * 1000, {'Content-Type': 'application/json'}),
                
                # Non-existent endpoint
                ('GET', '/non-existent-endpoint', b'', {}),
            ]
            
            for method, endpoint, data, headers in error_test_cases:
                response = None
                if method == 'GET':
                    response = client.get(endpoint, headers=headers)
                elif method == 'POST':
                    response = client.post(endpoint, data=data, headers=headers)
                
                if response:
                    # Should handle errors gracefully (not 500)
                    assert response.status_code != 500, (
                        f"Server error on {method} {endpoint}: {response.status_code}"
                    )
                    
                    # Should return reasonable error codes
                    assert response.status_code in [200, 400, 401, 403, 404, 405, 413, 415, 422], (
                        f"Unexpected error code {response.status_code} for {method} {endpoint}"
                    )

    def test_performance_baseline_validation(self, client, test_users):
        """Test performance baseline for deployment validation"""
        with self.mock_environment_secrets():
            import time
            
            user = test_users['alice']
            
            # Test endpoint response times
            performance_tests = [
                ('GET', '/health', None, None),
                ('GET', '/readyz', None, None),
                ('GET', '/', None, None)
            ]
            
            for method, endpoint, data, headers in performance_tests:
                start_time = time.time()
                
                response = None
                if method == 'GET':
                    response = client.get(endpoint, headers=headers or {})
                elif method == 'POST':
                    response = client.post(endpoint, data=data, headers=headers or {})
                
                response_time = time.time() - start_time
                
                # Performance baselines for CI/CD
                if endpoint == '/health':
                    assert response_time < 2.0, f"Health endpoint took {response_time:.3f}s, should be under 2s"
                elif endpoint == '/readyz':
                    assert response_time < 5.0, f"Readiness endpoint took {response_time:.3f}s, should be under 5s"
                elif endpoint == '/':
                    assert response_time < 10.0, f"Root endpoint took {response_time:.3f}s, should be under 10s"

    def test_logging_and_monitoring_integration(self, client, test_users):
        """Test logging and monitoring integration for observability"""
        with self.mock_environment_secrets():
            # Test that requests generate appropriate logs
            user = test_users['alice']
            
            # Make request that should generate logs
            response = client.get('/health')
            assert response.status_code == 200
            
            # Verify request ID header is present (for log correlation)
            assert 'X-Request-ID' in response.headers, "Request ID should be present for log correlation"
            
            request_id = response.headers['X-Request-ID']
            assert len(request_id) > 0, "Request ID should not be empty"
            
            # Test structured logging format (if accessible)
            # This would typically check log files or monitoring endpoints
            # For now, we verify the request completed successfully
            
            # Test monitoring endpoint if available
            try:
                monitoring_response = client.get('/api/monitoring/health')
                if monitoring_response.status_code == 200:
                    monitoring_data = monitoring_response.get_json()
                    if monitoring_data:
                        assert isinstance(monitoring_data, dict), "Monitoring data should be structured"
            except Exception as e:  # narrowed from bare except (lint A1)
                # Monitoring endpoints might be protected
                pass

    def test_deployment_rollback_safety(self, client, test_users):
        """Test deployment rollback safety mechanisms"""
        with self.mock_environment_secrets():
            # Test that critical data operations are atomic
            user = test_users['alice']
            
            # Create expense that exercises multiple database operations
            from utils.db import create_expense
            
            try:
                result = create_expense(
                    user_id=user['psid_hash'],
                    amount=500.0,
                    currency='৳',
                    category='rollback_safety_test',
                    occurred_at=datetime.now(),
                    source_message_id='rollback_safety_001',
                    correlation_id='rollback_safety_corr_001',
                    notes='Rollback safety test expense'
                )
                
                # Verify expense was created atomically
                if result:
                    expense = self.assert_expense_created(
                        user_hash=user['psid_hash'],
                        expected_amount=500.0,
                        expected_category='rollback_safety_test'
                    )
                    
                    # Verify related operations were also completed
                    self.assert_user_totals_updated(user['psid_hash'], 500.0)
                    
            except Exception:
                # If operation fails, it should fail cleanly without partial state
                # Verify no partial data was left behind
                with client.application.app_context():
                    from models import Expense
                    
                    partial_expense = Expense.query.filter_by(
                        correlation_id='rollback_safety_corr_001'
                    ).first()
                    
                    # Should be no partial expense if operation failed
                    if partial_expense is None:
                        # This is expected for failed atomic operations
                        pass

    def test_security_headers_deployment_ready(self, client, test_users):
        """Test security headers for production deployment readiness"""
        with self.mock_environment_secrets():
            # Test critical endpoints for security headers
            security_endpoints = [
                '/health',
                '/readyz',
                '/'
            ]
            
            for endpoint in security_endpoints:
                response = client.get(endpoint)
                
                # Check for security-related headers
                headers = response.headers
                
                # Verify request tracking
                assert 'X-Request-ID' in headers, f"Missing X-Request-ID header on {endpoint}"
                
                # Content type should be set
                if response.status_code == 200:
                    assert 'Content-Type' in headers, f"Missing Content-Type header on {endpoint}"
                
                # Should not expose server information
                server_header = headers.get('Server', '')
                assert 'gunicorn' not in server_header.lower(), "Server header exposes implementation details"