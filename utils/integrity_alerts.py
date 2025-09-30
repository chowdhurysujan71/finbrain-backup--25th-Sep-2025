"""
Advanced alerting system for data integrity failures
Handles notifications to operations team when data discrepancies are detected
"""

import json
import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MimeText
from typing import Any, Dict

import requests

from .data_integrity_check import IntegrityReport

logger = logging.getLogger(__name__)

class IntegrityAlerting:
    """Manages alerts for data integrity failures"""
    
    def __init__(self):
        self.email_enabled = self._check_email_config()
        self.slack_enabled = self._check_slack_config()
        self.webhook_enabled = self._check_webhook_config()
        
        # Alert thresholds
        self.critical_threshold = 0  # Any failures are critical
        self.warning_threshold = 0   # Any warnings should be reported
        
        logger.info(f"Integrity alerting initialized: email={self.email_enabled}, "
                   f"slack={self.slack_enabled}, webhook={self.webhook_enabled}")
    
    def _check_email_config(self) -> bool:
        """Check if email alerting is configured"""
        required_vars = ['SMTP_HOST', 'SMTP_PORT', 'SMTP_USER', 'SMTP_PASS', 'ALERT_EMAIL_TO']
        return all(os.getenv(var) for var in required_vars)
    
    def _check_slack_config(self) -> bool:
        """Check if Slack alerting is configured"""
        return bool(os.getenv('SLACK_WEBHOOK_URL'))
    
    def _check_webhook_config(self) -> bool:
        """Check if generic webhook alerting is configured"""
        return bool(os.getenv('INTEGRITY_WEBHOOK_URL'))
    
    def send_alert(self, report: IntegrityReport):
        """Send alerts based on report status"""
        try:
            # Determine if we should alert
            should_alert = (
                report.failed > self.critical_threshold or 
                report.warnings > self.warning_threshold or
                report.overall_status in ['CRITICAL', 'WARNING']
            )
            
            if not should_alert:
                logger.debug("No alerting needed - all checks passed")
                return
            
            # Generate alert content
            alert_data = self._generate_alert_content(report)
            
            # Send via all enabled channels
            alerts_sent = []
            
            if self.email_enabled:
                try:
                    self._send_email_alert(alert_data)
                    alerts_sent.append('email')
                except Exception as e:
                    logger.error(f"Failed to send email alert: {e}")
            
            if self.slack_enabled:
                try:
                    self._send_slack_alert(alert_data)
                    alerts_sent.append('slack')
                except Exception as e:
                    logger.error(f"Failed to send Slack alert: {e}")
            
            if self.webhook_enabled:
                try:
                    self._send_webhook_alert(alert_data)
                    alerts_sent.append('webhook')
                except Exception as e:
                    logger.error(f"Failed to send webhook alert: {e}")
            
            if alerts_sent:
                logger.info(f"Integrity alerts sent via: {', '.join(alerts_sent)}")
            else:
                logger.warning("No integrity alerts could be sent - check configuration")
                
        except Exception as e:
            logger.error(f"Alert sending failed: {e}")
    
    def _generate_alert_content(self, report: IntegrityReport) -> dict[str, Any]:
        """Generate structured alert content"""
        # Determine severity and emoji
        if report.overall_status == 'CRITICAL':
            severity = 'CRITICAL'
            emoji = '🚨'
            color = '#ff0000'
        elif report.overall_status == 'WARNING':
            severity = 'WARNING'
            emoji = '⚠️'
            color = '#ffaa00'
        else:
            severity = 'INFO'
            emoji = 'ℹ️'
            color = '#0099ff'
        
        # Get failed and warning checks
        failed_checks = [c for c in report.checks if c.status == 'FAIL']
        warning_checks = [c for c in report.checks if c.status == 'WARNING']
        
        # Generate summary
        if failed_checks:
            summary = f"{emoji} {severity}: FinBrain data integrity issues detected"
        elif warning_checks:
            summary = f"{emoji} {severity}: FinBrain data integrity warnings"
        else:
            summary = f"{emoji} FinBrain data integrity check completed"
        
        # Calculate total affected users
        total_affected = sum(
            c.affected_count for c in failed_checks + warning_checks 
            if c.affected_count and c.affected_count > 0
        )
        
        return {
            'severity': severity,
            'emoji': emoji,
            'color': color,
            'summary': summary,
            'report': report,
            'failed_checks': failed_checks,
            'warning_checks': warning_checks,
            'total_affected_users': total_affected,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _send_email_alert(self, alert_data: dict[str, Any]):
        """Send email alert to operations team"""
        smtp_host = os.getenv('SMTP_HOST')
        smtp_port = int(os.getenv('SMTP_PORT', '587'))
        smtp_user = os.getenv('SMTP_USER')
        smtp_pass = os.getenv('SMTP_PASS')
        alert_email_to = os.getenv('ALERT_EMAIL_TO')
        alert_email_from = os.getenv('ALERT_EMAIL_FROM', smtp_user)
        
        report = alert_data['report']
        
        # Create email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"[FinBrain] {alert_data['severity']}: Data Integrity Alert"
        msg['From'] = alert_email_from
        msg['To'] = alert_email_to
        
        # Create text content
        text_content = self._generate_email_text(alert_data)
        
        # Create HTML content
        html_content = self._generate_email_html(alert_data)
        
        # Attach parts
        text_part = MimeText(text_content, 'plain')
        html_part = MimeText(html_content, 'html')
        
        msg.attach(text_part)
        msg.attach(html_part)
        
        # Send email
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        
        logger.info(f"Email alert sent to {alert_email_to}")
    
    def _send_slack_alert(self, alert_data: dict[str, Any]):
        """Send Slack alert to operations channel"""
        webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        
        report = alert_data['report']
        failed_checks = alert_data['failed_checks']
        warning_checks = alert_data['warning_checks']
        
        # Create Slack message
        message = {
            "text": alert_data['summary'],
            "attachments": [
                {
                    "color": alert_data['color'],
                    "fields": [
                        {
                            "title": "Overall Status",
                            "value": report.overall_status,
                            "short": True
                        },
                        {
                            "title": "Run ID",
                            "value": report.run_id,
                            "short": True
                        },
                        {
                            "title": "Total Checks",
                            "value": f"{report.total_checks} (✅ {report.passed} | ❌ {report.failed} | ⚠️ {report.warnings})",
                            "short": False
                        }
                    ],
                    "ts": int(datetime.utcnow().timestamp())
                }
            ]
        }
        
        # Add failed checks if any
        if failed_checks:
            failed_field = {
                "title": "❌ Failed Checks",
                "value": "\n".join([f"• {c.check_name}: {c.message}" for c in failed_checks[:5]]),
                "short": False
            }
            if len(failed_checks) > 5:
                failed_field["value"] += f"\n... and {len(failed_checks) - 5} more"
            message["attachments"][0]["fields"].append(failed_field)
        
        # Add warning checks if any
        if warning_checks:
            warning_field = {
                "title": "⚠️ Warning Checks",
                "value": "\n".join([f"• {c.check_name}: {c.message}" for c in warning_checks[:3]]),
                "short": False
            }
            if len(warning_checks) > 3:
                warning_field["value"] += f"\n... and {len(warning_checks) - 3} more"
            message["attachments"][0]["fields"].append(warning_field)
        
        # Add action buttons
        message["attachments"][0]["actions"] = [
            {
                "type": "button",
                "text": "View Details",
                "url": f"{os.getenv('APP_BASE_URL', 'https://finbrain.app')}/api/integrity/last-report",
                "style": "primary"
            },
            {
                "type": "button", 
                "text": "Health Check",
                "url": f"{os.getenv('APP_BASE_URL', 'https://finbrain.app')}/api/health/integrity"
            }
        ]
        
        # Send to Slack
        response = requests.post(webhook_url, json=message, timeout=10)
        response.raise_for_status()
        
        logger.info("Slack alert sent successfully")
    
    def _send_webhook_alert(self, alert_data: dict[str, Any]):
        """Send alert to generic webhook endpoint"""
        webhook_url = os.getenv('INTEGRITY_WEBHOOK_URL')
        webhook_secret = os.getenv('INTEGRITY_WEBHOOK_SECRET')
        
        # Prepare payload
        payload = {
            'event': 'data_integrity_alert',
            'severity': alert_data['severity'],
            'timestamp': alert_data['timestamp'],
            'report_summary': {
                'run_id': alert_data['report'].run_id,
                'overall_status': alert_data['report'].overall_status,
                'total_checks': alert_data['report'].total_checks,
                'passed': alert_data['report'].passed,
                'failed': alert_data['report'].failed,
                'warnings': alert_data['report'].warnings,
                'summary': alert_data['report'].summary
            },
            'failed_checks': [
                {
                    'name': c.check_name,
                    'message': c.message,
                    'affected_count': c.affected_count
                } for c in alert_data['failed_checks']
            ],
            'warning_checks': [
                {
                    'name': c.check_name,
                    'message': c.message,
                    'affected_count': c.affected_count
                } for c in alert_data['warning_checks']
            ]
        }
        
        # Prepare headers
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'FinBrain-Integrity-Alert/1.0'
        }
        
        if webhook_secret:
            # Add authentication header if secret is configured
            import hashlib
            import hmac
            payload_str = json.dumps(payload, sort_keys=True)
            signature = hmac.new(
                webhook_secret.encode(),
                payload_str.encode(),
                hashlib.sha256
            ).hexdigest()
            headers['X-Integrity-Signature'] = f'sha256={signature}'
        
        # Send webhook
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        response.raise_for_status()
        
        logger.info("Webhook alert sent successfully")
    
    def _generate_email_text(self, alert_data: dict[str, Any]) -> str:
        """Generate plain text email content"""
        report = alert_data['report']
        failed_checks = alert_data['failed_checks']
        warning_checks = alert_data['warning_checks']
        
        content = f"""
FinBrain Data Integrity Alert
============================

Status: {alert_data['severity']}
Run ID: {report.run_id}
Timestamp: {alert_data['timestamp']}

Summary: {report.summary}

Check Results:
- Total Checks: {report.total_checks}
- Passed: {report.passed}
- Failed: {report.failed}
- Warnings: {report.warnings}

"""
        
        if failed_checks:
            content += "\nFAILED CHECKS:\n"
            for check in failed_checks:
                content += f"❌ {check.check_name}\n"
                content += f"   {check.message}\n"
                if check.affected_count:
                    content += f"   Affected: {check.affected_count} items\n"
                if check.affected_users:
                    content += f"   Users: {', '.join(check.affected_users[:3])}\n"
                content += "\n"
        
        if warning_checks:
            content += "\nWARNING CHECKS:\n"
            for check in warning_checks:
                content += f"⚠️ {check.check_name}\n"
                content += f"   {check.message}\n"
                if check.affected_count:
                    content += f"   Affected: {check.affected_count} items\n"
                content += "\n"
        
        content += f"""
Next Steps:
1. Review detailed report: {os.getenv('APP_BASE_URL', 'https://finbrain.app')}/api/integrity/last-report
2. Check system health: {os.getenv('APP_BASE_URL', 'https://finbrain.app')}/api/health/integrity
3. Investigate affected users and data discrepancies
4. Run manual integrity check if needed: POST /api/integrity/run

This alert was generated automatically by FinBrain's data integrity monitoring system.
"""
        
        return content
    
    def _generate_email_html(self, alert_data: dict[str, Any]) -> str:
        """Generate HTML email content"""
        report = alert_data['report']
        failed_checks = alert_data['failed_checks']
        warning_checks = alert_data['warning_checks']
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>FinBrain Data Integrity Alert</title>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .header {{ background: {alert_data['color']}; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; }}
        .status {{ font-size: 18px; font-weight: bold; }}
        .summary {{ background: #f5f5f5; padding: 15px; border-left: 4px solid {alert_data['color']}; }}
        .checks {{ margin: 20px 0; }}
        .check-item {{ margin: 10px 0; padding: 10px; border-left: 3px solid #ddd; }}
        .failed {{ border-left-color: #ff0000; background: #ffe6e6; }}
        .warning {{ border-left-color: #ffaa00; background: #fff8e6; }}
        .footer {{ background: #f9f9f9; padding: 15px; font-size: 12px; color: #666; }}
        .button {{ display: inline-block; padding: 10px 20px; background: {alert_data['color']}; color: white; text-decoration: none; border-radius: 4px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{alert_data['emoji']} FinBrain Data Integrity Alert</h1>
        <div class="status">{alert_data['severity']}</div>
    </div>
    
    <div class="content">
        <div class="summary">
            <strong>Summary:</strong> {report.summary}
        </div>
        
        <p><strong>Run ID:</strong> {report.run_id}</p>
        <p><strong>Timestamp:</strong> {alert_data['timestamp']}</p>
        
        <h3>Check Results</h3>
        <ul>
            <li>Total Checks: {report.total_checks}</li>
            <li>✅ Passed: {report.passed}</li>
            <li>❌ Failed: {report.failed}</li>
            <li>⚠️ Warnings: {report.warnings}</li>
        </ul>
"""
        
        if failed_checks:
            html += "<h3>❌ Failed Checks</h3><div class='checks'>"
            for check in failed_checks:
                html += f"""
                <div class="check-item failed">
                    <strong>{check.check_name}</strong><br>
                    {check.message}
                    {f'<br><small>Affected: {check.affected_count} items</small>' if check.affected_count else ''}
                </div>
                """
            html += "</div>"
        
        if warning_checks:
            html += "<h3>⚠️ Warning Checks</h3><div class='checks'>"
            for check in warning_checks:
                html += f"""
                <div class="check-item warning">
                    <strong>{check.check_name}</strong><br>
                    {check.message}
                    {f'<br><small>Affected: {check.affected_count} items</small>' if check.affected_count else ''}
                </div>
                """
            html += "</div>"
        
        html += f"""
        <h3>Next Steps</h3>
        <ol>
            <li>Review the detailed report</li>
            <li>Check system health status</li>
            <li>Investigate affected users and data discrepancies</li>
            <li>Run manual integrity check if needed</li>
        </ol>
        
        <p>
            <a href="{os.getenv('APP_BASE_URL', 'https://finbrain.app')}/api/integrity/last-report" class="button">View Detailed Report</a>
            &nbsp;
            <a href="{os.getenv('APP_BASE_URL', 'https://finbrain.app')}/api/health/integrity" class="button">Check Health Status</a>
        </p>
    </div>
    
    <div class="footer">
        This alert was generated automatically by FinBrain's data integrity monitoring system.
    </div>
</body>
</html>
"""
        return html

# Global instance
integrity_alerting = IntegrityAlerting()