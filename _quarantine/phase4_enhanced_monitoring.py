#!/usr/bin/env python3
"""
Phase 4: Enhanced Monitoring & Controls
Full monitoring dashboard with real-time metrics and admin controls
"""

import sys
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List
from flask import Blueprint, request, jsonify, render_template_string

# Add project root to path
sys.path.append('/home/runner/workspace')

from app import app, db
from sqlalchemy import text
from utils.pca_flags import pca_flags

# Blueprint for monitoring endpoints
monitoring_bp = Blueprint('monitoring', __name__, url_prefix='/api/monitoring')

class EnhancedMonitoring:
    """Enhanced monitoring and controls for CC system"""
    
    def get_cc_throughput_metrics(self) -> Dict[str, Any]:
        """Get CC throughput and performance metrics"""
        try:
            with app.app_context():
                # Last 24 hours metrics
                metrics = db.session.execute(text("""
                    SELECT 
                        COUNT(*) as total_ccs,
                        COUNT(DISTINCT user_id) as unique_users,
                        AVG(confidence) as avg_confidence,
                        AVG(processing_time_ms) as avg_processing_time,
                        MAX(processing_time_ms) as max_processing_time,
                        COUNT(CASE WHEN error_message IS NOT NULL THEN 1 END) as error_count,
                        COUNT(CASE WHEN applied = true THEN 1 END) as applied_count
                    FROM inference_snapshots 
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                """)).fetchone()
                
                # Decision distribution
                decisions = db.session.execute(text("""
                    SELECT decision, COUNT(*) as count, AVG(confidence) as avg_conf
                    FROM inference_snapshots 
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY decision
                    ORDER BY count DESC
                """)).fetchall()
                
                # Intent distribution
                intents = db.session.execute(text("""
                    SELECT intent, COUNT(*) as count, AVG(confidence) as avg_conf
                    FROM inference_snapshots 
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY intent
                    ORDER BY count DESC
                """)).fetchall()
                
                # Hourly trend (last 24 hours)
                hourly_trend = db.session.execute(text("""
                    SELECT 
                        DATE_TRUNC('hour', created_at) as hour,
                        COUNT(*) as cc_count,
                        AVG(processing_time_ms) as avg_time,
                        COUNT(CASE WHEN error_message IS NOT NULL THEN 1 END) as errors
                    FROM inference_snapshots 
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY DATE_TRUNC('hour', created_at)
                    ORDER BY hour
                """)).fetchall()
                
                return {
                    'period': '24_hours',
                    'summary': {
                        'total_ccs': metrics[0] or 0,
                        'unique_users': metrics[1] or 0,
                        'avg_confidence': round(float(metrics[2] or 0), 3),
                        'avg_processing_time_ms': round(float(metrics[3] or 0), 1),
                        'max_processing_time_ms': metrics[4] or 0,
                        'error_count': metrics[5] or 0,
                        'applied_count': metrics[6] or 0,
                        'error_rate_pct': round((metrics[5] or 0) / max(metrics[0] or 1, 1) * 100, 2),
                        'apply_rate_pct': round((metrics[6] or 0) / max(metrics[0] or 1, 1) * 100, 2)
                    },
                    'decision_distribution': [
                        {'decision': row[0], 'count': row[1], 'avg_confidence': round(float(row[2] or 0), 3)}
                        for row in decisions
                    ],
                    'intent_distribution': [
                        {'intent': row[0], 'count': row[1], 'avg_confidence': round(float(row[2] or 0), 3)}
                        for row in intents
                    ],
                    'hourly_trend': [
                        {
                            'hour': row[0].isoformat() if row[0] else None,
                            'cc_count': row[1] or 0,
                            'avg_time_ms': round(float(row[2] or 0), 1),
                            'error_count': row[3] or 0
                        }
                        for row in hourly_trend
                    ],
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {'error': str(e), 'generated_at': datetime.now().isoformat()}
    
    def get_performance_slo_status(self) -> Dict[str, Any]:
        """Check performance against SLOs"""
        try:
            with app.app_context():
                # Performance percentiles for last 24 hours
                perf_stats = db.session.execute(text("""
                    SELECT 
                        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY processing_time_ms) as p50,
                        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY processing_time_ms) as p95,
                        PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY processing_time_ms) as p99,
                        COUNT(*) as sample_size
                    FROM inference_snapshots 
                    WHERE created_at >= NOW() - INTERVAL '24 hours'
                    AND processing_time_ms IS NOT NULL
                """)).fetchone()
                
                # SLO targets
                slo_targets = {
                    'p50_target_ms': 250,
                    'p95_target_ms': 900, 
                    'p99_target_ms': 1500,
                    'error_rate_target_pct': 0.5
                }
                
                if perf_stats and perf_stats[3] > 0:  # sample_size > 0
                    p50, p95, p99, sample_size = perf_stats
                    
                    # Calculate SLO compliance
                    slo_status = {
                        'p50_ms': round(float(p50 or 0), 1),
                        'p95_ms': round(float(p95 or 0), 1), 
                        'p99_ms': round(float(p99 or 0), 1),
                        'sample_size': sample_size,
                        'slo_compliance': {
                            'p50_ok': (p50 or 0) <= slo_targets['p50_target_ms'],
                            'p95_ok': (p95 or 0) <= slo_targets['p95_target_ms'],
                            'p99_ok': (p99 or 0) <= slo_targets['p99_target_ms']
                        },
                        'targets': slo_targets,
                        'overall_slo_met': all([
                            (p50 or 0) <= slo_targets['p50_target_ms'],
                            (p95 or 0) <= slo_targets['p95_target_ms'],
                            (p99 or 0) <= slo_targets['p99_target_ms']
                        ])
                    }
                else:
                    slo_status = {
                        'error': 'No performance data available',
                        'sample_size': 0,
                        'targets': slo_targets
                    }
                
                return {
                    'period': '24_hours',
                    'slo_status': slo_status,
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            return {'error': str(e), 'generated_at': datetime.now().isoformat()}
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health indicators"""
        try:
            # Current PCA configuration
            current_config = {
                'pca_mode': pca_flags.mode.value,
                'tau_high': pca_flags.tau_high,
                'tau_low': pca_flags.tau_low,
                'slo_budget_ms': pca_flags.slo_budget_ms,
                'global_kill_switch': pca_flags.global_kill_switch,
                'clarifiers_enabled': pca_flags.should_enable_clarifiers(),
                'overlay_writes_enabled': pca_flags.should_write_overlays(),
                'snapshot_logging_enabled': pca_flags.should_log_snapshots()
            }
            
            # Database connectivity check
            with app.app_context():
                db_health = db.session.execute(text("SELECT 1")).scalar()
                
                # Recent activity check
                recent_activity = db.session.execute(text("""
                    SELECT COUNT(*) FROM inference_snapshots 
                    WHERE created_at >= NOW() - INTERVAL '1 hour'
                """)).scalar()
            
            health_indicators = {
                'database_connectivity': db_health == 1,
                'recent_cc_activity': recent_activity > 0,
                'pca_system_active': pca_flags.mode != pca_flags.mode.FALLBACK,
                'no_kill_switch': not pca_flags.global_kill_switch,
                'recent_activity_count': recent_activity
            }
            
            overall_health = all([
                health_indicators['database_connectivity'],
                health_indicators['pca_system_active'],
                health_indicators['no_kill_switch']
            ])
            
            return {
                'overall_health': 'HEALTHY' if overall_health else 'WARNING',
                'health_indicators': health_indicators,
                'current_config': current_config,
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'overall_health': 'ERROR',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }

# Initialize monitoring
monitoring = EnhancedMonitoring()

@monitoring_bp.route('/metrics', methods=['GET'])
def get_metrics():
    """Get CC system metrics"""
    return jsonify(monitoring.get_cc_throughput_metrics())

@monitoring_bp.route('/slo', methods=['GET'])
def get_slo_status():
    """Get SLO compliance status"""
    return jsonify(monitoring.get_performance_slo_status())

@monitoring_bp.route('/health', methods=['GET'])
def get_health():
    """Get system health status"""
    return jsonify(monitoring.get_system_health())

@monitoring_bp.route('/dashboard', methods=['GET'])
def monitoring_dashboard():
    """Enhanced monitoring dashboard"""
    dashboard_html = """
<!DOCTYPE html>
<html>
<head>
    <title>CC System Monitoring Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .metric-card { margin-bottom: 20px; }
        .health-indicator { padding: 8px 12px; border-radius: 4px; margin: 4px; display: inline-block; }
        .health-ok { background-color: #d4edda; color: #155724; }
        .health-warning { background-color: #fff3cd; color: #856404; }
        .health-error { background-color: #f8d7da; color: #721c24; }
    </style>
</head>
<body>
    <div class="container-fluid mt-4">
        <h1>CC System Monitoring Dashboard</h1>
        
        <div class="row">
            <div class="col-md-12">
                <div class="card metric-card">
                    <div class="card-header">
                        <h5>System Health</h5>
                    </div>
                    <div class="card-body" id="health-status">
                        Loading...
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-6">
                <div class="card metric-card">
                    <div class="card-header">
                        <h5>24-Hour Metrics</h5>
                    </div>
                    <div class="card-body" id="metrics-summary">
                        Loading...
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card metric-card">
                    <div class="card-header">
                        <h5>SLO Status</h5>
                    </div>
                    <div class="card-body" id="slo-status">
                        Loading...
                    </div>
                </div>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-12">
                <div class="card metric-card">
                    <div class="card-header">
                        <h5>Decision & Intent Distribution</h5>
                    </div>
                    <div class="card-body" id="distribution-charts">
                        Loading...
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function loadData() {
            // Load health status
            fetch('/api/monitoring/health')
                .then(r => r.json())
                .then(data => {
                    const healthDiv = document.getElementById('health-status');
                    const healthClass = data.overall_health === 'HEALTHY' ? 'health-ok' : 
                                       data.overall_health === 'WARNING' ? 'health-warning' : 'health-error';
                    
                    healthDiv.innerHTML = `
                        <div class="health-indicator ${healthClass}">
                            Overall Health: ${data.overall_health}
                        </div>
                        <div class="mt-3">
                            <strong>Current Config:</strong><br>
                            Mode: ${data.current_config?.pca_mode || 'Unknown'}<br>
                            Thresholds: ${data.current_config?.tau_low || 'N/A'} - ${data.current_config?.tau_high || 'N/A'}<br>
                            Clarifiers: ${data.current_config?.clarifiers_enabled ? 'Enabled' : 'Disabled'}
                        </div>
                    `;
                });
            
            // Load metrics
            fetch('/api/monitoring/metrics')
                .then(r => r.json())
                .then(data => {
                    const metricsDiv = document.getElementById('metrics-summary');
                    const summary = data.summary || {};
                    
                    metricsDiv.innerHTML = `
                        <div class="row">
                            <div class="col-6"><strong>Total CCs:</strong> ${summary.total_ccs || 0}</div>
                            <div class="col-6"><strong>Unique Users:</strong> ${summary.unique_users || 0}</div>
                            <div class="col-6"><strong>Avg Confidence:</strong> ${summary.avg_confidence || 0}</div>
                            <div class="col-6"><strong>Error Rate:</strong> ${summary.error_rate_pct || 0}%</div>
                            <div class="col-6"><strong>Apply Rate:</strong> ${summary.apply_rate_pct || 0}%</div>
                            <div class="col-6"><strong>Avg Time:</strong> ${summary.avg_processing_time_ms || 0}ms</div>
                        </div>
                    `;
                    
                    // Show distributions
                    const distDiv = document.getElementById('distribution-charts');
                    const decisions = data.decision_distribution || [];
                    const intents = data.intent_distribution || [];
                    
                    distDiv.innerHTML = `
                        <div class="row">
                            <div class="col-6">
                                <h6>Decisions</h6>
                                ${decisions.map(d => `<div>${d.decision}: ${d.count} (${d.avg_confidence})</div>`).join('')}
                            </div>
                            <div class="col-6">
                                <h6>Intents</h6>
                                ${intents.map(i => `<div>${i.intent}: ${i.count} (${i.avg_confidence})</div>`).join('')}
                            </div>
                        </div>
                    `;
                });
            
            // Load SLO status
            fetch('/api/monitoring/slo')
                .then(r => r.json())
                .then(data => {
                    const sloDiv = document.getElementById('slo-status');
                    const status = data.slo_status || {};
                    
                    if (status.error) {
                        sloDiv.innerHTML = `<div class="text-warning">${status.error}</div>`;
                        return;
                    }
                    
                    const compliance = status.slo_compliance || {};
                    const overallClass = status.overall_slo_met ? 'text-success' : 'text-warning';
                    
                    sloDiv.innerHTML = `
                        <div class="${overallClass}">
                            <strong>Overall SLO: ${status.overall_slo_met ? 'MET' : 'NOT MET'}</strong>
                        </div>
                        <div class="mt-2">
                            P50: ${status.p50_ms}ms ${compliance.p50_ok ? '✅' : '❌'}<br>
                            P95: ${status.p95_ms}ms ${compliance.p95_ok ? '✅' : '❌'}<br>
                            P99: ${status.p99_ms}ms ${compliance.p99_ok ? '✅' : '❌'}<br>
                            Sample Size: ${status.sample_size}
                        </div>
                    `;
                });
        }
        
        // Load data on page load and refresh every 30 seconds
        loadData();
        setInterval(loadData, 30000);
    </script>
</body>
</html>
    """
    return dashboard_html

def register_monitoring_routes(app):
    """Register enhanced monitoring routes"""
    app.register_blueprint(monitoring_bp)
    print(f"✅ Enhanced monitoring registered at /api/monitoring/*")

if __name__ == "__main__":
    # CLI tool for monitoring
    import argparse
    
    parser = argparse.ArgumentParser(description='CC Monitoring CLI')
    parser.add_argument('--metrics', action='store_true', help='Show metrics')
    parser.add_argument('--slo', action='store_true', help='Show SLO status')
    parser.add_argument('--health', action='store_true', help='Show health status')
    parser.add_argument('--watch', action='store_true', help='Watch mode (refresh every 30s)')
    
    args = parser.parse_args()
    
    if args.metrics or args.health or args.slo:
        if args.metrics:
            print(json.dumps(monitoring.get_cc_throughput_metrics(), indent=2))
        if args.slo:
            print(json.dumps(monitoring.get_performance_slo_status(), indent=2))
        if args.health:
            print(json.dumps(monitoring.get_system_health(), indent=2))
            
        if args.watch:
            import time
            while True:
                time.sleep(30)
                print("\n" + "="*50)
                print(f"Refresh at {datetime.now().isoformat()}")
                print("="*50)
                if args.metrics:
                    print(json.dumps(monitoring.get_cc_throughput_metrics(), indent=2))
                if args.slo:
                    print(json.dumps(monitoring.get_performance_slo_status(), indent=2))
                if args.health:
                    print(json.dumps(monitoring.get_system_health(), indent=2))
    else:
        parser.print_help()