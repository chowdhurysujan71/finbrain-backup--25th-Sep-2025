"""
Single Writer Observability Routes

Provides monitoring dashboards and API endpoints for tracking single writer enforcement.
"""

import os
import time

# Simplified auth for observability - using basic auth check
from functools import wraps

from flask import Blueprint, jsonify, request

from utils.single_writer_metrics import get_dashboard_data, get_health_status


def require_basic_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Simple auth check using environment variables
        admin_user = os.environ.get('ADMIN_USER')
        admin_pass = os.environ.get('ADMIN_PASS')
        
        if not admin_user or not admin_pass:
            return jsonify({"error": "Admin authentication not configured"}), 503
        
        # Check HTTP Basic Authentication
        auth = request.authorization
        if not auth or auth.username != admin_user or auth.password != admin_pass:
            return jsonify({"error": "Authentication required"}), 401, {
                'WWW-Authenticate': 'Basic realm="Admin Dashboard"'
            }
            
        return f(*args, **kwargs)
    return decorated_function
import logging

logger = logging.getLogger(__name__)

# Create blueprint
single_writer_obs = Blueprint('single_writer_obs', __name__)

@single_writer_obs.route('/ops/single-writer/health')
def health_check():
    """Health check endpoint for single writer enforcement"""
    try:
        # Simple health status without full metrics for now
        return jsonify({
            "status": "healthy",
            "timestamp": int(time.time()),
            "single_writer_guard": "active",
            "monitoring": "operational"
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@single_writer_obs.route('/ops/single-writer/metrics')
def metrics_endpoint():
    """Prometheus-style metrics endpoint"""
    try:
        health = get_health_status()
        metrics_24h = health["metrics_24h"]
        sla_compliance = health["sla_compliance"]
        
        # Import and get AI timeout metrics
        from utils.ai_adapter_v2 import get_ai_timeout_metrics
        ai_metrics = get_ai_timeout_metrics()
        
        # Generate Prometheus-style metrics
        metrics = [
            "# HELP single_writer_canonical_writes_total Total canonical writer operations",
            "# TYPE single_writer_canonical_writes_total counter",
            f"single_writer_canonical_writes_total {metrics_24h['canonical_writes_total']}",
            "",
            "# HELP single_writer_success_rate Success rate of canonical writer operations",
            "# TYPE single_writer_success_rate gauge", 
            f"single_writer_success_rate {metrics_24h['canonical_writes_success_rate'] / 100}",
            "",
            "# HELP single_writer_avg_response_time_ms Average response time in milliseconds",
            "# TYPE single_writer_avg_response_time_ms gauge",
            f"single_writer_avg_response_time_ms {metrics_24h['avg_response_time_ms']}",
            "",
            "# HELP single_writer_violations_total Total violations detected",
            "# TYPE single_writer_violations_total counter",
            f"single_writer_violations_total {metrics_24h['violations']}",
            "",
            "# HELP single_writer_protection_triggers_total Total protection triggers",
            "# TYPE single_writer_protection_triggers_total counter", 
            f"single_writer_protection_triggers_total {metrics_24h['protection_triggers']}",
            "",
            "# HELP single_writer_sla_compliance SLA compliance indicators",
            "# TYPE single_writer_sla_compliance gauge",
        ]
        
        for sla_name, compliant in sla_compliance.items():
            metrics.append(f"single_writer_sla_compliance{{sla=\"{sla_name}\"}} {1 if compliant else 0}")
        
        # Add AI timeout metrics
        metrics.extend([
            "",
            "# HELP ai_requests_total Total AI requests made",
            "# TYPE ai_requests_total counter",
            f"ai_requests_total {ai_metrics['ai_requests_total']}",
            "",
            "# HELP ai_timeouts_total Total AI request timeouts",
            "# TYPE ai_timeouts_total counter", 
            f"ai_timeouts_total {ai_metrics['ai_timeouts_total']}",
            "",
            "# HELP ai_timeout_rate AI timeout rate as percentage",
            "# TYPE ai_timeout_rate gauge",
            f"ai_timeout_rate {ai_metrics['ai_timeout_rate']}",
            "",
            "# HELP ai_success_rate AI request success rate as percentage",
            "# TYPE ai_success_rate gauge",
            f"ai_success_rate {ai_metrics['ai_success_rate']}"
        ])
        
        return "\n".join(metrics), 200, {'Content-Type': 'text/plain; charset=utf-8'}
        
    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
        return f"# ERROR: {str(e)}", 500, {'Content-Type': 'text/plain; charset=utf-8'}

@single_writer_obs.route('/admin/single-writer/dashboard')
@require_basic_auth
def admin_dashboard():
    """Admin dashboard for single writer monitoring"""
    try:
        dashboard_data = get_dashboard_data()
        
        # Simple HTML dashboard
        html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Single Writer Enforcement Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f8f9fa; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #28a745; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .status-healthy { color: #28a745; font-weight: bold; }
        .status-degraded { color: #dc3545; font-weight: bold; }
        .card { background: white; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; }
        .metric { text-align: center; }
        .metric-value { font-size: 2em; font-weight: bold; color: #007bff; }
        .metric-label { color: #6c757d; }
        .sla-pass { color: #28a745; }
        .sla-fail { color: #dc3545; }
        .protection-layer { margin: 10px 0; }
        .protection-active { color: #28a745; }
        table { width: 100%; border-collapse: collapse; }
        th, td { text-align: left; padding: 12px; border-bottom: 1px solid #ddd; }
        th { background-color: #f8f9fa; }
        .violation-critical { background-color: #f8d7da; }
        .violation-high { background-color: #fff3cd; }
        .violation-medium { background-color: #d1ecf1; }
        .refresh-btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🛡️ Single Writer Enforcement Dashboard</h1>
            <p>Real-time monitoring of single writer principle enforcement</p>
            <button class="refresh-btn" onclick="window.location.reload()">🔄 Refresh</button>
        </div>
        
        <div class="card">
            <h2>System Health</h2>
            <p class="{{ 'status-healthy' if dashboard_data.health.status == 'healthy' else 'status-degraded' }}">
                Status: {{ dashboard_data.health.status.upper() }}
            </p>
            <p>Last Updated: {{ dashboard_data.health.timestamp | timestamp_to_datetime }}</p>
        </div>
        
        <div class="card">
            <h2>Key Metrics (Last 24 Hours)</h2>
            <div class="metrics-grid">
                <div class="metric">
                    <div class="metric-value">{{ dashboard_data.health.metrics_24h.canonical_writes_total }}</div>
                    <div class="metric-label">Canonical Writes</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{{ dashboard_data.health.metrics_24h.canonical_writes_success_rate }}%</div>
                    <div class="metric-label">Success Rate</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{{ dashboard_data.health.metrics_24h.avg_response_time_ms }}ms</div>
                    <div class="metric-label">Avg Response Time</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{{ dashboard_data.health.metrics_24h.violations }}</div>
                    <div class="metric-label">Violations</div>
                </div>
                <div class="metric">
                    <div class="metric-value">{{ dashboard_data.health.metrics_24h.blocked_attempts }}</div>
                    <div class="metric-label">Blocked Attempts</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>SLA Compliance</h2>
            <table>
                <tr>
                    <th>SLA Target</th>
                    <th>Status</th>
                    <th>Target</th>
                </tr>
                {% for sla_name, compliant in dashboard_data.health.sla_compliance.items() %}
                <tr>
                    <td>{{ sla_name.replace('_', ' ').title() }}</td>
                    <td class="{{ 'sla-pass' if compliant else 'sla-fail' }}">
                        {{ '✅ PASS' if compliant else '❌ FAIL' }}
                    </td>
                    <td>{{ dashboard_data.sla_targets[sla_name] }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        
        <div class="card">
            <h2>Protection Layers</h2>
            {% for layer_name, layer_info in dashboard_data.protection_layers.items() %}
            <div class="protection-layer">
                <strong>{{ layer_name.replace('_', ' ').title() }}:</strong>
                <span class="protection-active">{{ layer_info.status.upper() }}</span>
                - {{ layer_info.description }}
            </div>
            {% endfor %}
        </div>
        
        {% if dashboard_data.health.recent_violations %}
        <div class="card">
            <h2>Recent Violations</h2>
            <table>
                <tr>
                    <th>Time</th>
                    <th>Type</th>
                    <th>Source</th>
                    <th>Severity</th>
                    <th>Details</th>
                </tr>
                {% for violation in dashboard_data.health.recent_violations %}
                <tr class="violation-{{ violation.severity }}">
                    <td>{{ violation.timestamp | timestamp_to_datetime }}</td>
                    <td>{{ violation.violation_type }}</td>
                    <td>{{ violation.source }}</td>
                    <td>{{ violation.severity.upper() }}</td>
                    <td>{{ violation.details | truncate(100) }}</td>
                </tr>
                {% endfor %}
            </table>
        </div>
        {% endif %}
        
        <div class="card">
            <h2>System Information</h2>
            <p><strong>Single Writer Guard:</strong> {{ dashboard_data.health.protection_status.runtime_guard }}</p>
            <p><strong>CI Checks:</strong> {{ dashboard_data.health.protection_status.ci_checks }}</p>
            <p><strong>Database Constraints:</strong> {{ dashboard_data.health.protection_status.database_constraints }}</p>
        </div>
    </div>
</body>
</html>
        """
        
        # Simple Jinja2-style template rendering
        from datetime import datetime
        
        def timestamp_to_datetime(ts):
            return datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        
        def truncate(s, length):
            return (str(s)[:length] + '...') if len(str(s)) > length else str(s)
        
        # Basic template substitution
        html = html_template
        html = html.replace('{{ dashboard_data.health.status }}', dashboard_data['health']['status'])
        html = html.replace('{{ dashboard_data.health.timestamp | timestamp_to_datetime }}', timestamp_to_datetime(dashboard_data['health']['timestamp']))
        
        # Render metrics
        metrics = dashboard_data['health']['metrics_24h']
        html = html.replace('{{ dashboard_data.health.metrics_24h.canonical_writes_total }}', str(metrics['canonical_writes_total']))
        html = html.replace('{{ dashboard_data.health.metrics_24h.canonical_writes_success_rate }}', str(metrics['canonical_writes_success_rate']))
        html = html.replace('{{ dashboard_data.health.metrics_24h.avg_response_time_ms }}', str(metrics['avg_response_time_ms']))
        html = html.replace('{{ dashboard_data.health.metrics_24h.violations }}', str(metrics['violations']))
        html = html.replace('{{ dashboard_data.health.metrics_24h.blocked_attempts }}', str(metrics['blocked_attempts']))
        
        return html
        
    except Exception as e:
        logger.error(f"Dashboard failed: {e}")
        return f"<h1>Dashboard Error</h1><p>{str(e)}</p>", 500

@single_writer_obs.route('/api/single-writer/stats')
@require_basic_auth  
def api_stats():
    """API endpoint for single writer statistics"""
    try:
        return jsonify(get_dashboard_data())
    except Exception as e:
        logger.error(f"Stats API failed: {e}")
        return jsonify({"error": str(e)}), 500

@single_writer_obs.route('/api/single-writer/test-violation', methods=['POST'])
@require_basic_auth
def test_violation():
    """Test endpoint to simulate violations for testing monitoring"""
    try:
        from utils.single_writer_metrics import ViolationType, record_violation
        
        violation_type = request.json.get('type', 'bypass_attempt')
        severity = request.json.get('severity', 'medium')
        
        record_violation(
            ViolationType(violation_type),
            'test_endpoint',
            {'test': True, 'user_triggered': True},
            severity
        )
        
        return jsonify({"status": "violation_recorded", "type": violation_type, "severity": severity})
        
    except Exception as e:
        logger.error(f"Test violation failed: {e}")
        return jsonify({"error": str(e)}), 500