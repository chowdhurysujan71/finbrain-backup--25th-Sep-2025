"""
UAT Executor and Report Generator
Executes comprehensive UAT and generates detailed audit reports
"""

import logging
from datetime import datetime
from typing import Any, Dict

logger = logging.getLogger(__name__)

class UATReportGenerator:
    """Generates comprehensive UAT audit reports"""
    
    @staticmethod
    def generate_detailed_report(audit_report) -> str:
        """Generate detailed UAT audit report"""
        
        report_lines = []
        
        # Header
        report_lines.extend([
            "=" * 80,
            "📋 COMPREHENSIVE END-TO-END UAT AUDIT REPORT",
            "🔍 Report Feedback Feature - Data Handling, Routing, Processing, Storage & Integrity",
            "=" * 80,
            "",
            f"🔬 Test Session ID: {audit_report.test_session_id}",
            f"⏰ Start Time: {audit_report.start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"⏰ End Time: {audit_report.end_time.strftime('%Y-%m-%d %H:%M:%S UTC') if audit_report.end_time else 'Running...'}",
            f"⏱️  Total Duration: {(audit_report.end_time - audit_report.start_time).total_seconds():.1f} seconds" if audit_report.end_time else "",
            ""
        ])
        
        # Executive Summary
        pass_rate = audit_report.coverage_analysis.get("pass_rate_percent", 0)
        report_lines.extend([
            "📊 EXECUTIVE SUMMARY",
            "-" * 40,
            f"Total Tests Executed: {audit_report.total_tests}",
            f"✅ Passed: {audit_report.passed_tests}",
            f"❌ Failed: {audit_report.failed_tests}",
            f"⚠️  Warnings: {audit_report.warning_tests}",
            f"🎯 Pass Rate: {pass_rate:.1f}%",
            ""
        ])
        
        # Deployment Readiness Assessment
        if pass_rate >= 95:
            deployment_status = "🟢 READY FOR PRODUCTION DEPLOYMENT"
        elif pass_rate >= 80:
            deployment_status = "🟡 READY WITH MINOR ISSUES TO ADDRESS"
        else:
            deployment_status = "🔴 NOT READY - CRITICAL ISSUES MUST BE RESOLVED"
        
        report_lines.extend([
            "🚀 DEPLOYMENT READINESS ASSESSMENT",
            "-" * 40,
            deployment_status,
            ""
        ])
        
        # User Category Analysis
        user_types = {}
        for result in audit_report.test_results:
            user_type = result.user_type
            if user_type not in user_types:
                user_types[user_type] = {"total": 0, "passed": 0, "failed": 0, "warnings": 0}
            
            user_types[user_type]["total"] += 1
            if result.status == "PASS":
                user_types[user_type]["passed"] += 1
            elif result.status == "FAIL":
                user_types[user_type]["failed"] += 1
            elif result.status == "WARNING":
                user_types[user_type]["warnings"] += 1
        
        report_lines.extend([
            "👥 USER CATEGORY ANALYSIS",
            "-" * 40
        ])
        
        for user_type, stats in user_types.items():
            pass_rate_type = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
            status_icon = "✅" if pass_rate_type >= 95 else "⚠️" if pass_rate_type >= 80 else "❌"
            
            report_lines.extend([
                f"{status_icon} {user_type.upper()} USERS:",
                f"   Total Tests: {stats['total']}",
                f"   Passed: {stats['passed']} | Failed: {stats['failed']} | Warnings: {stats['warnings']}",
                f"   Pass Rate: {pass_rate_type:.1f}%",
                ""
            ])
        
        # Performance Analysis
        perf_metrics = audit_report.performance_metrics
        report_lines.extend([
            "⚡ PERFORMANCE ANALYSIS",
            "-" * 40,
            f"Average Execution Time: {perf_metrics.get('average_execution_time_ms', 0):.1f}ms",
            f"Maximum Execution Time: {perf_metrics.get('max_execution_time_ms', 0):.1f}ms",
            f"Minimum Execution Time: {perf_metrics.get('min_execution_time_ms', 0):.1f}ms",
            f"Total Test Duration: {perf_metrics.get('total_execution_time_ms', 0):.1f}ms",
            ""
        ])
        
        # Detailed Test Results
        report_lines.extend([
            "🔍 DETAILED TEST RESULTS",
            "-" * 40
        ])
        
        for result in audit_report.test_results:
            status_icon = "✅" if result.status == "PASS" else "❌" if result.status == "FAIL" else "⚠️"
            
            report_lines.extend([
                f"{status_icon} {result.test_name}",
                f"   Test ID: {result.test_id}",
                f"   User Type: {result.user_type}",
                f"   Status: {result.status}",
                f"   Execution Time: {result.execution_time_ms:.1f}ms",
            ])
            
            # Show details
            if result.details:
                report_lines.append("   Details:")
                for key, value in result.details.items():
                    report_lines.append(f"     {key}: {value}")
            
            # Show integrity checks
            if result.data_integrity_checks:
                report_lines.append("   Data Integrity Checks:")
                for check in result.data_integrity_checks:
                    check_icon = "✅" if check.get("status") == "PASS" else "❌" if check.get("status") == "FAIL" else "⚠️"
                    report_lines.append(f"     {check_icon} {check.get('check', 'Unknown')}: {check.get('details', 'No details')}")
            
            # Show errors
            if result.errors:
                report_lines.append("   Errors:")
                for error in result.errors:
                    report_lines.append(f"     ❌ {error}")
            
            # Show warnings
            if result.warnings:
                report_lines.append("   Warnings:")
                for warning in result.warnings:
                    report_lines.append(f"     ⚠️  {warning}")
            
            report_lines.append("")
        
        # Data Integrity Summary
        integrity_summary = UATReportGenerator._analyze_integrity_results(audit_report)
        report_lines.extend([
            "🔐 DATA INTEGRITY ANALYSIS",
            "-" * 40,
            f"Total Integrity Checks: {integrity_summary['total_checks']}",
            f"✅ Passed: {integrity_summary['passed_checks']}",
            f"❌ Failed: {integrity_summary['failed_checks']}",
            f"⚠️  Warnings: {integrity_summary['warning_checks']}",
            f"🎯 Integrity Score: {integrity_summary['integrity_score']:.1f}%",
            ""
        ])
        
        # Critical Issues
        critical_issues = [result for result in audit_report.test_results if result.status == "FAIL"]
        if critical_issues:
            report_lines.extend([
                "🚨 CRITICAL ISSUES REQUIRING ATTENTION",
                "-" * 40
            ])
            for issue in critical_issues:
                report_lines.extend([
                    f"❌ {issue.test_name}",
                    f"   User Type: {issue.user_type}",
                    f"   Errors: {', '.join(issue.errors) if issue.errors else 'No specific errors recorded'}",
                    ""
                ])
        
        # Recommendations
        if audit_report.recommendations:
            report_lines.extend([
                "💡 RECOMMENDATIONS",
                "-" * 40
            ])
            for i, recommendation in enumerate(audit_report.recommendations, 1):
                report_lines.append(f"{i}. {recommendation}")
            report_lines.append("")
        
        # Coverage Analysis Details
        report_lines.extend([
            "📈 COVERAGE ANALYSIS",
            "-" * 40,
            f"User Types Covered: {', '.join(audit_report.coverage_analysis.get('user_types_covered', []))}",
            f"Test Categories: {audit_report.coverage_analysis.get('test_categories', 0)}",
            f"Overall Pass Rate: {audit_report.coverage_analysis.get('pass_rate_percent', 0):.1f}%",
            ""
        ])
        
        # Final Verdict
        report_lines.extend([
            "⚖️  FINAL VERDICT",
            "-" * 40
        ])
        
        if pass_rate >= 95 and integrity_summary['integrity_score'] >= 95:
            verdict = "🎉 EXCELLENT - System demonstrates exceptional reliability and integrity across all user scenarios"
        elif pass_rate >= 90 and integrity_summary['integrity_score'] >= 90:
            verdict = "✅ GOOD - System shows strong performance with minor areas for improvement"
        elif pass_rate >= 80:
            verdict = "⚠️  ACCEPTABLE - System functional but requires attention to failing tests before deployment"
        else:
            verdict = "❌ NEEDS WORK - Critical issues must be resolved before production deployment"
        
        report_lines.extend([
            verdict,
            "",
            "=" * 80,
            f"📋 Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "=" * 80
        ])
        
        return "\\n".join(report_lines)
    
    @staticmethod
    def _analyze_integrity_results(audit_report) -> dict[str, Any]:
        """Analyze data integrity results across all tests"""
        total_checks = 0
        passed_checks = 0
        failed_checks = 0
        warning_checks = 0
        
        for result in audit_report.test_results:
            for check in result.data_integrity_checks:
                total_checks += 1
                status = check.get("status", "").upper()
                if status == "PASS":
                    passed_checks += 1
                elif status == "FAIL":
                    failed_checks += 1
                elif status == "WARNING":
                    warning_checks += 1
        
        integrity_score = (passed_checks / total_checks * 100) if total_checks > 0 else 100
        
        return {
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "warning_checks": warning_checks,
            "integrity_score": integrity_score
        }

def execute_comprehensive_uat() -> str:
    """Execute comprehensive UAT and return detailed report"""
    try:
        from utils.comprehensive_uat import ComprehensiveUATFramework
        
        logger.info("🚀 Starting Comprehensive UAT Execution")
        
        # Create and execute UAT framework
        uat_framework = ComprehensiveUATFramework()
        audit_report = uat_framework.execute_comprehensive_uat()
        
        # Generate detailed report
        detailed_report = UATReportGenerator.generate_detailed_report(audit_report)
        
        logger.info("✅ Comprehensive UAT completed successfully")
        return detailed_report
        
    except Exception as e:
        logger.error(f"❌ Comprehensive UAT failed: {e}")
        return f"❌ UAT Execution Failed: {str(e)}"