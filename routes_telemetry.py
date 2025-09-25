"""
FinBrain Growth Telemetry Routes
/metrics endpoint and /admin/metrics dashboard
"""

import logging
from datetime import UTC

from flask import Blueprint, render_template_string

from utils.telemetry import GrowthMetrics

logger = logging.getLogger(__name__)

telemetry_bp = Blueprint('telemetry', __name__)

@telemetry_bp.route('/metrics')
def metrics_endpoint():
    """
    Human-readable metrics endpoint for monitoring
    Returns plain text metrics report
    """
    try:
        metrics_report = GrowthMetrics.generate_metrics_report()
        
        # Return as plain text with proper content type
        from flask import current_app
        response = current_app.response_class(
            response=metrics_report,
            status=200,
            mimetype='text/plain'
        )
        return response
        
    except Exception as e:
        logger.error(f"Failed to generate /metrics endpoint: {e}")
        return f"Error generating metrics: {str(e)}", 500

@telemetry_bp.route('/admin/metrics')
def admin_metrics_dashboard():
    """
    Admin dashboard showing growth metrics in web interface
    Bootstrap-styled dashboard with auto-refresh
    """
    try:
        # Get all metrics data
        dau_today = GrowthMetrics.get_dau_today()
        dau_7day = GrowthMetrics.get_dau_7day()
        cohorts = GrowthMetrics.get_retention_cohorts(7)
        totals = GrowthMetrics.get_running_totals()
        
        # Admin dashboard HTML template
        dashboard_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FinBrain - Growth Metrics Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        .metric-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-radius: 15px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }
        .metric-number {
            font-size: 2.5rem;
            font-weight: bold;
        }
        .metric-label {
            font-size: 0.9rem;
            opacity: 0.9;
        }
        .retention-table {
            background: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .counter-card {
            background: white;
            border-radius: 10px;
            padding: 1.5rem;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-left: 4px solid #28a745;
        }
        .auto-refresh {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 10px 15px;
            border-radius: 20px;
            font-size: 0.9rem;
        }
    </style>
</head>
<body style="background-color: #f8f9fa;">
    <div class="auto-refresh">
        <i class="fas fa-sync-alt"></i> Auto-refresh: 5min
    </div>
    
    <div class="container-fluid py-4">
        <div class="row">
            <div class="col-12">
                <h1 class="mb-4">
                    <i class="fas fa-chart-line text-primary"></i>
                    FinBrain Growth Metrics
                </h1>
                <p class="text-muted mb-4">
                    Generated: {{ generation_time }} UTC
                </p>
            </div>
        </div>
        
        <!-- DAU Metrics -->
        <div class="row">
            <div class="col-md-6">
                <div class="metric-card">
                    <div class="d-flex align-items-center">
                        <div class="flex-grow-1">
                            <div class="metric-number">{{ dau_today }}</div>
                            <div class="metric-label">Daily Active Users (Today)</div>
                        </div>
                        <div class="fs-1 opacity-25">
                            <i class="fas fa-users"></i>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="metric-card">
                    <div class="d-flex align-items-center">
                        <div class="flex-grow-1">
                            <div class="metric-number">{{ dau_7day }}</div>
                            <div class="metric-label">7-Day Active Users</div>
                        </div>
                        <div class="fs-1 opacity-25">
                            <i class="fas fa-calendar-week"></i>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Retention Table -->
        <div class="row">
            <div class="col-12">
                <div class="card retention-table">
                    <div class="card-header bg-primary text-white">
                        <h5 class="card-title mb-0">
                            <i class="fas fa-chart-bar"></i>
                            User Retention (Last 7 Cohorts)
                        </h5>
                    </div>
                    <div class="card-body p-0">
                        <div class="table-responsive">
                            <table class="table table-striped mb-0">
                                <thead class="table-light">
                                    <tr>
                                        <th>Cohort Date</th>
                                        <th>D0 Users</th>
                                        <th>D1 Retention</th>
                                        <th>D3 Retention</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for cohort in cohorts %}
                                    <tr>
                                        <td><strong>{{ cohort.cohort_date }}</strong></td>
                                        <td>{{ cohort.d0_users }}</td>
                                        <td>
                                            <span class="badge bg-{% if cohort.d1_retention >= 50 %}success{% elif cohort.d1_retention >= 30 %}warning{% else %}danger{% endif %}">
                                                {{ "{:.1f}".format(cohort.d1_retention) }}%
                                            </span>
                                        </td>
                                        <td>
                                            <span class="badge bg-{% if cohort.d3_retention >= 40 %}success{% elif cohort.d3_retention >= 20 %}warning{% else %}danger{% endif %}">
                                                {{ "{:.1f}".format(cohort.d3_retention) }}%
                                            </span>
                                        </td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Running Totals -->
        <div class="row mt-4">
            <div class="col-md-4">
                <div class="counter-card">
                    <h5 class="text-primary">
                        <i class="fas fa-receipt"></i>
                        Total Expenses
                    </h5>
                    <div class="fs-2 fw-bold text-dark">{{ "{:,}".format(totals.total_expenses) }}</div>
                    <small class="text-muted">All-time expense entries</small>
                </div>
            </div>
            <div class="col-md-4">
                <div class="counter-card">
                    <h5 class="text-primary">
                        <i class="fas fa-chart-pie"></i>
                        Total Reports
                    </h5>
                    <div class="fs-2 fw-bold text-dark">{{ "{:,}".format(totals.total_reports) }}</div>
                    <small class="text-muted">Financial reports generated</small>
                </div>
            </div>
            <div class="col-md-4">
                <div class="counter-card">
                    <h5 class="text-primary">
                        <i class="fas fa-trophy"></i>
                        Challenges Started
                    </h5>
                    <div class="fs-2 fw-bold text-dark">{{ "{:,}".format(totals.challenges_started) }}</div>
                    <small class="text-muted">Financial challenges initiated</small>
                </div>
            </div>
        </div>
        
        <!-- Export Section -->
        <div class="row mt-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">
                            <i class="fas fa-download"></i>
                            Export Data
                        </h5>
                        <p class="card-text">Download metrics data for external analysis</p>
                        <a href="/metrics" target="_blank" class="btn btn-outline-primary">
                            <i class="fas fa-file-alt"></i>
                            Export as Text
                        </a>
                        <button class="btn btn-outline-secondary" onclick="window.print()">
                            <i class="fas fa-print"></i>
                            Print Dashboard
                        </button>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Auto-refresh every 5 minutes
        setTimeout(function() {
            window.location.reload();
        }, 5 * 60 * 1000);
        
        // Add current time to auto-refresh indicator
        setInterval(function() {
            const now = new Date();
            const refreshElement = document.querySelector('.auto-refresh');
            const nextRefresh = new Date(now.getTime() + (5 * 60 * 1000));
            refreshElement.innerHTML = '<i class="fas fa-sync-alt"></i> Next refresh: ' + nextRefresh.toLocaleTimeString();
        }, 1000);
    </script>
</body>
</html>
        """
        
        from datetime import datetime, timezone
        
        return render_template_string(
            dashboard_html,
            dau_today=dau_today,
            dau_7day=dau_7day,
            cohorts=cohorts,
            totals=totals,
            generation_time=datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')
        )
        
    except Exception as e:
        logger.error(f"Failed to generate admin metrics dashboard: {e}")
        return f"Error generating dashboard: {str(e)}", 500

# Helper function to register telemetry routes
def register_telemetry_routes(app):
    """Register telemetry routes with the Flask app"""
    # Import needed for blueprint registration
    telemetry_bp.app = app
    app.register_blueprint(telemetry_bp)