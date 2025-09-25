"""
Nightly SQL Data Integrity Check System for FinBrain
Validates "itemized sum == report total" to detect data integrity issues before users notice them.

This script can be run as:
1. Scheduled task via APScheduler (nightly)
2. Standalone script for manual execution
3. Health check endpoint for monitoring

Key Integrity Checks:
- Individual expense sums vs User.total_expenses
- Individual expense counts vs User.expense_count
- Monthly aggregations vs MonthlySummary totals
- Category breakdown consistency
- Orphaned records detection
- Invalid data detection
- Superseded expense handling
"""

import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import text

from db_base import db

logger = logging.getLogger(__name__)

@dataclass
class IntegrityCheckResult:
    """Result of a single integrity check"""
    check_name: str
    status: str  # 'PASS', 'FAIL', 'WARNING'
    message: str
    affected_users: list[str] = None
    affected_count: int = 0
    expected_value: Any = None
    actual_value: Any = None
    timestamp: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()
        if self.affected_users is None:
            self.affected_users = []

@dataclass
class IntegrityReport:
    """Complete integrity check report"""
    run_id: str
    start_time: str
    end_time: str
    total_checks: int
    passed: int
    failed: int
    warnings: int
    overall_status: str
    checks: list[IntegrityCheckResult]
    summary: str
    
    def to_dict(self) -> dict:
        return asdict(self)

class DataIntegrityChecker:
    """Main data integrity checking engine"""
    
    def __init__(self):
        self.run_id = f"integrity_{int(time.time())}"
        self.start_time = datetime.utcnow()
        self.checks = []
        self.max_affected_users_to_log = 10  # Limit detailed user logging
        
    def run_all_checks(self) -> IntegrityReport:
        """Run all integrity checks and return comprehensive report"""
        logger.info(f"Starting data integrity check run: {self.run_id}")
        
        # Run all integrity checks
        check_methods = [
            self._check_user_total_expenses,
            self._check_user_expense_counts,
            self._check_monthly_summary_amounts,
            self._check_monthly_summary_counts,
            self._check_monthly_category_breakdowns,
            self._check_orphaned_expenses,
            self._check_orphaned_monthly_summaries,
            self._check_invalid_amounts,
            self._check_superseded_expenses,
            self._check_duplicate_expenses,
            self._check_negative_user_totals,
            self._check_future_dated_expenses
        ]
        
        for check_method in check_methods:
            try:
                result = check_method()
                self.checks.append(result)
                logger.info(f"Check '{result.check_name}': {result.status} - {result.message}")
            except Exception as e:
                error_result = IntegrityCheckResult(
                    check_name=check_method.__name__,
                    status='FAIL',
                    message=f"Check failed with exception: {str(e)}",
                    affected_count=0
                )
                self.checks.append(error_result)
                logger.error(f"Integrity check {check_method.__name__} failed: {e}")
        
        return self._generate_report()
    
    def _check_user_total_expenses(self) -> IntegrityCheckResult:
        """Check if User.total_expenses matches sum of individual expenses"""
        try:
            # SQL query to compare user totals with actual expense sums
            query = text("""
                SELECT 
                    u.user_id_hash,
                    u.total_expenses as user_total,
                    COALESCE(SUM(e.amount), 0) as actual_sum,
                    COUNT(e.id) as expense_count
                FROM users u
                LEFT JOIN expenses e ON u.user_id_hash = e.user_id_hash 
                    AND e.superseded_by IS NULL  -- Only active expenses
                GROUP BY u.user_id_hash, u.total_expenses
                HAVING ABS(COALESCE(u.total_expenses, 0) - COALESCE(SUM(e.amount), 0)) > 0.01
                ORDER BY ABS(COALESCE(u.total_expenses, 0) - COALESCE(SUM(e.amount), 0)) DESC
                LIMIT 100
            """)
            
            result = db.session.execute(query).fetchall()
            
            if not result:
                return IntegrityCheckResult(
                    check_name="User Total Expenses",
                    status="PASS",
                    message="All user total expenses match individual expense sums"
                )
            
            affected_users = []
            for row in result[:self.max_affected_users_to_log]:
                user_hash = row[0]
                user_total = float(row[1] or 0)
                actual_sum = float(row[2] or 0)
                affected_users.append(f"{user_hash[:8]}... (expected: {user_total}, actual: {actual_sum})")
            
            return IntegrityCheckResult(
                check_name="User Total Expenses",
                status="FAIL",
                message=f"Found {len(result)} users with mismatched total expenses",
                affected_users=affected_users,
                affected_count=len(result)
            )
            
        except Exception as e:
            return IntegrityCheckResult(
                check_name="User Total Expenses",
                status="FAIL",
                message=f"Check failed: {str(e)}"
            )
    
    def _check_user_expense_counts(self) -> IntegrityCheckResult:
        """Check if User.expense_count matches actual count of expenses"""
        try:
            query = text("""
                SELECT 
                    u.user_id_hash,
                    u.expense_count as user_count,
                    COUNT(e.id) as actual_count
                FROM users u
                LEFT JOIN expenses e ON u.user_id_hash = e.user_id_hash 
                    AND e.superseded_by IS NULL  -- Only active expenses
                GROUP BY u.user_id_hash, u.expense_count
                HAVING COALESCE(u.expense_count, 0) != COUNT(e.id)
                ORDER BY ABS(COALESCE(u.expense_count, 0) - COUNT(e.id)) DESC
                LIMIT 100
            """)
            
            result = db.session.execute(query).fetchall()
            
            if not result:
                return IntegrityCheckResult(
                    check_name="User Expense Counts",
                    status="PASS",
                    message="All user expense counts match actual expense counts"
                )
            
            affected_users = []
            for row in result[:self.max_affected_users_to_log]:
                user_hash = row[0]
                user_count = int(row[1] or 0)
                actual_count = int(row[2])
                affected_users.append(f"{user_hash[:8]}... (expected: {user_count}, actual: {actual_count})")
            
            return IntegrityCheckResult(
                check_name="User Expense Counts",
                status="FAIL",
                message=f"Found {len(result)} users with mismatched expense counts",
                affected_users=affected_users,
                affected_count=len(result)
            )
            
        except Exception as e:
            return IntegrityCheckResult(
                check_name="User Expense Counts",
                status="FAIL",
                message=f"Check failed: {str(e)}"
            )
    
    def _check_monthly_summary_amounts(self) -> IntegrityCheckResult:
        """Check if MonthlySummary.total_amount matches sum of expenses for that month"""
        try:
            query = text("""
                SELECT 
                    ms.user_id_hash,
                    ms.month,
                    ms.total_amount as summary_total,
                    COALESCE(SUM(e.amount), 0) as actual_sum
                FROM monthly_summaries ms
                LEFT JOIN expenses e ON ms.user_id_hash = e.user_id_hash 
                    AND e.month = ms.month
                    AND e.superseded_by IS NULL  -- Only active expenses
                GROUP BY ms.user_id_hash, ms.month, ms.total_amount
                HAVING ABS(COALESCE(ms.total_amount, 0) - COALESCE(SUM(e.amount), 0)) > 0.01
                ORDER BY ABS(COALESCE(ms.total_amount, 0) - COALESCE(SUM(e.amount), 0)) DESC
                LIMIT 100
            """)
            
            result = db.session.execute(query).fetchall()
            
            if not result:
                return IntegrityCheckResult(
                    check_name="Monthly Summary Amounts",
                    status="PASS",
                    message="All monthly summary amounts match individual expense sums"
                )
            
            affected_users = []
            for row in result[:self.max_affected_users_to_log]:
                user_hash = row[0]
                month = row[1]
                summary_total = float(row[2] or 0)
                actual_sum = float(row[3] or 0)
                affected_users.append(f"{user_hash[:8]}.../{month} (expected: {summary_total}, actual: {actual_sum})")
            
            return IntegrityCheckResult(
                check_name="Monthly Summary Amounts",
                status="FAIL",
                message=f"Found {len(result)} monthly summaries with mismatched amounts",
                affected_users=affected_users,
                affected_count=len(result)
            )
            
        except Exception as e:
            return IntegrityCheckResult(
                check_name="Monthly Summary Amounts",
                status="FAIL",
                message=f"Check failed: {str(e)}"
            )
    
    def _check_monthly_summary_counts(self) -> IntegrityCheckResult:
        """Check if MonthlySummary.expense_count matches actual count of expenses for that month"""
        try:
            query = text("""
                SELECT 
                    ms.user_id_hash,
                    ms.month,
                    ms.expense_count as summary_count,
                    COUNT(e.id) as actual_count
                FROM monthly_summaries ms
                LEFT JOIN expenses e ON ms.user_id_hash = e.user_id_hash 
                    AND e.month = ms.month
                    AND e.superseded_by IS NULL  -- Only active expenses
                GROUP BY ms.user_id_hash, ms.month, ms.expense_count
                HAVING COALESCE(ms.expense_count, 0) != COUNT(e.id)
                ORDER BY ABS(COALESCE(ms.expense_count, 0) - COUNT(e.id)) DESC
                LIMIT 100
            """)
            
            result = db.session.execute(query).fetchall()
            
            if not result:
                return IntegrityCheckResult(
                    check_name="Monthly Summary Counts",
                    status="PASS",
                    message="All monthly summary counts match actual expense counts"
                )
            
            affected_users = []
            for row in result[:self.max_affected_users_to_log]:
                user_hash = row[0]
                month = row[1]
                summary_count = int(row[2] or 0)
                actual_count = int(row[3])
                affected_users.append(f"{user_hash[:8]}.../{month} (expected: {summary_count}, actual: {actual_count})")
            
            return IntegrityCheckResult(
                check_name="Monthly Summary Counts",
                status="FAIL",
                message=f"Found {len(result)} monthly summaries with mismatched counts",
                affected_users=affected_users,
                affected_count=len(result)
            )
            
        except Exception as e:
            return IntegrityCheckResult(
                check_name="Monthly Summary Counts",
                status="FAIL",
                message=f"Check failed: {str(e)}"
            )
    
    def _check_monthly_category_breakdowns(self) -> IntegrityCheckResult:
        """Check if MonthlySummary.categories matches actual category sums"""
        try:
            # This is more complex - we need to check JSON category breakdowns
            query = text("""
                SELECT 
                    ms.user_id_hash,
                    ms.month,
                    ms.categories::text as summary_categories,
                    jsonb_object_agg(e.category, COALESCE(SUM(e.amount), 0)) as actual_categories
                FROM monthly_summaries ms
                LEFT JOIN expenses e ON ms.user_id_hash = e.user_id_hash 
                    AND e.month = ms.month
                    AND e.superseded_by IS NULL
                WHERE ms.categories IS NOT NULL
                GROUP BY ms.user_id_hash, ms.month, ms.categories
                LIMIT 50  -- Limit for performance
            """)
            
            result = db.session.execute(query).fetchall()
            mismatches = 0
            affected_users = []
            
            for row in result:
                user_hash = row[0]
                month = row[1]
                summary_categories_str = row[2]
                actual_categories = row[3] or {}
                
                try:
                    # Parse the stored categories
                    summary_categories = json.loads(summary_categories_str) if summary_categories_str else {}
                    
                    # Compare category totals (allowing small floating point differences)
                    for category, summary_amount in summary_categories.items():
                        actual_amount = actual_categories.get(category, 0)
                        if abs(float(summary_amount) - float(actual_amount)) > 0.01:
                            mismatches += 1
                            if len(affected_users) < self.max_affected_users_to_log:
                                affected_users.append(f"{user_hash[:8]}.../{month}/{category} (expected: {summary_amount}, actual: {actual_amount})")
                            break
                            
                except (json.JSONDecodeError, TypeError, ValueError) as e:
                    mismatches += 1
                    if len(affected_users) < self.max_affected_users_to_log:
                        affected_users.append(f"{user_hash[:8]}.../{month} (invalid JSON: {str(e)})")
            
            if mismatches == 0:
                return IntegrityCheckResult(
                    check_name="Monthly Category Breakdowns",
                    status="PASS",
                    message="All monthly category breakdowns match actual category sums"
                )
            
            return IntegrityCheckResult(
                check_name="Monthly Category Breakdowns",
                status="FAIL",
                message=f"Found {mismatches} monthly summaries with mismatched category breakdowns",
                affected_users=affected_users,
                affected_count=mismatches
            )
            
        except Exception as e:
            return IntegrityCheckResult(
                check_name="Monthly Category Breakdowns",
                status="FAIL",
                message=f"Check failed: {str(e)}"
            )
    
    def _check_orphaned_expenses(self) -> IntegrityCheckResult:
        """Check for expenses without corresponding users"""
        try:
            query = text("""
                SELECT e.user_id_hash, COUNT(*) as orphaned_count
                FROM expenses e
                LEFT JOIN users u ON e.user_id_hash = u.user_id_hash
                WHERE u.user_id_hash IS NULL
                GROUP BY e.user_id_hash
                ORDER BY orphaned_count DESC
                LIMIT 100
            """)
            
            result = db.session.execute(query).fetchall()
            
            if not result:
                return IntegrityCheckResult(
                    check_name="Orphaned Expenses",
                    status="PASS",
                    message="No orphaned expenses found"
                )
            
            total_orphaned = sum(row[1] for row in result)
            affected_users = [f"{row[0][:8]}... ({row[1]} expenses)" for row in result[:self.max_affected_users_to_log]]
            
            return IntegrityCheckResult(
                check_name="Orphaned Expenses",
                status="FAIL",
                message=f"Found {total_orphaned} orphaned expenses across {len(result)} user hashes",
                affected_users=affected_users,
                affected_count=total_orphaned
            )
            
        except Exception as e:
            return IntegrityCheckResult(
                check_name="Orphaned Expenses",
                status="FAIL",
                message=f"Check failed: {str(e)}"
            )
    
    def _check_orphaned_monthly_summaries(self) -> IntegrityCheckResult:
        """Check for monthly summaries without corresponding users"""
        try:
            query = text("""
                SELECT ms.user_id_hash, COUNT(*) as orphaned_count
                FROM monthly_summaries ms
                LEFT JOIN users u ON ms.user_id_hash = u.user_id_hash
                WHERE u.user_id_hash IS NULL
                GROUP BY ms.user_id_hash
                ORDER BY orphaned_count DESC
                LIMIT 100
            """)
            
            result = db.session.execute(query).fetchall()
            
            if not result:
                return IntegrityCheckResult(
                    check_name="Orphaned Monthly Summaries",
                    status="PASS",
                    message="No orphaned monthly summaries found"
                )
            
            total_orphaned = sum(row[1] for row in result)
            affected_users = [f"{row[0][:8]}... ({row[1]} summaries)" for row in result[:self.max_affected_users_to_log]]
            
            return IntegrityCheckResult(
                check_name="Orphaned Monthly Summaries",
                status="FAIL",
                message=f"Found {total_orphaned} orphaned monthly summaries across {len(result)} user hashes",
                affected_users=affected_users,
                affected_count=total_orphaned
            )
            
        except Exception as e:
            return IntegrityCheckResult(
                check_name="Orphaned Monthly Summaries",
                status="FAIL",
                message=f"Check failed: {str(e)}"
            )
    
    def _check_invalid_amounts(self) -> IntegrityCheckResult:
        """Check for invalid amounts (negative, null, or extremely large)"""
        try:
            query = text("""
                SELECT 
                    user_id_hash,
                    id,
                    amount,
                    CASE 
                        WHEN amount IS NULL THEN 'NULL'
                        WHEN amount < 0 THEN 'NEGATIVE'
                        WHEN amount > 99999999 THEN 'TOO_LARGE'
                        ELSE 'UNKNOWN'
                    END as issue_type
                FROM expenses
                WHERE amount IS NULL 
                   OR amount < 0 
                   OR amount > 99999999
                ORDER BY amount DESC
                LIMIT 100
            """)
            
            result = db.session.execute(query).fetchall()
            
            if not result:
                return IntegrityCheckResult(
                    check_name="Invalid Amounts",
                    status="PASS",
                    message="No invalid amounts found"
                )
            
            affected_users = []
            for row in result[:self.max_affected_users_to_log]:
                user_hash = row[0]
                expense_id = row[1]
                amount = row[2]
                issue_type = row[3]
                affected_users.append(f"{user_hash[:8]}... expense_id:{expense_id} amount:{amount} ({issue_type})")
            
            return IntegrityCheckResult(
                check_name="Invalid Amounts",
                status="FAIL",
                message=f"Found {len(result)} expenses with invalid amounts",
                affected_users=affected_users,
                affected_count=len(result)
            )
            
        except Exception as e:
            return IntegrityCheckResult(
                check_name="Invalid Amounts",
                status="FAIL",
                message=f"Check failed: {str(e)}"
            )
    
    def _check_superseded_expenses(self) -> IntegrityCheckResult:
        """Check for issues with superseded expenses"""
        try:
            # Check for superseded expenses that still point to non-existent expenses
            query = text("""
                SELECT 
                    e1.user_id_hash,
                    e1.id as superseded_id,
                    e1.superseded_by,
                    e1.amount
                FROM expenses e1
                LEFT JOIN expenses e2 ON e1.superseded_by = e2.id
                WHERE e1.superseded_by IS NOT NULL 
                  AND e2.id IS NULL
                ORDER BY e1.created_at DESC
                LIMIT 100
            """)
            
            result = db.session.execute(query).fetchall()
            
            if not result:
                return IntegrityCheckResult(
                    check_name="Superseded Expenses",
                    status="PASS",
                    message="All superseded expenses point to valid replacement expenses"
                )
            
            affected_users = []
            for row in result[:self.max_affected_users_to_log]:
                user_hash = row[0]
                expense_id = row[1]
                superseded_by = row[2]
                amount = row[3]
                affected_users.append(f"{user_hash[:8]}... expense_id:{expense_id} superseded_by:{superseded_by} (missing)")
            
            return IntegrityCheckResult(
                check_name="Superseded Expenses",
                status="FAIL",
                message=f"Found {len(result)} superseded expenses pointing to missing expenses",
                affected_users=affected_users,
                affected_count=len(result)
            )
            
        except Exception as e:
            return IntegrityCheckResult(
                check_name="Superseded Expenses",
                status="FAIL",
                message=f"Check failed: {str(e)}"
            )
    
    def _check_duplicate_expenses(self) -> IntegrityCheckResult:
        """Check for potential duplicate expenses (same user, amount, category, close time)"""
        try:
            query = text("""
                SELECT 
                    user_id_hash,
                    amount,
                    category,
                    DATE(created_at) as date,
                    COUNT(*) as duplicate_count,
                    array_agg(id ORDER BY created_at) as expense_ids
                FROM expenses
                WHERE superseded_by IS NULL
                GROUP BY user_id_hash, amount, category, DATE(created_at)
                HAVING COUNT(*) > 1
                ORDER BY duplicate_count DESC
                LIMIT 50
            """)
            
            result = db.session.execute(query).fetchall()
            
            if not result:
                return IntegrityCheckResult(
                    check_name="Duplicate Expenses",
                    status="PASS",
                    message="No potential duplicate expenses found"
                )
            
            total_duplicates = sum(row[4] for row in result)
            affected_users = []
            for row in result[:self.max_affected_users_to_log]:
                user_hash = row[0]
                amount = row[1]
                category = row[2]
                date_val = row[3]
                count = row[4]
                affected_users.append(f"{user_hash[:8]}... {amount} {category} on {date_val} ({count} duplicates)")
            
            return IntegrityCheckResult(
                check_name="Duplicate Expenses",
                status="WARNING",
                message=f"Found {len(result)} groups of potential duplicate expenses ({total_duplicates} total)",
                affected_users=affected_users,
                affected_count=total_duplicates
            )
            
        except Exception as e:
            return IntegrityCheckResult(
                check_name="Duplicate Expenses",
                status="FAIL",
                message=f"Check failed: {str(e)}"
            )
    
    def _check_negative_user_totals(self) -> IntegrityCheckResult:
        """Check for users with negative total expenses"""
        try:
            query = text("""
                SELECT user_id_hash, total_expenses, expense_count
                FROM users
                WHERE total_expenses < 0 OR expense_count < 0
                ORDER BY total_expenses ASC
                LIMIT 100
            """)
            
            result = db.session.execute(query).fetchall()
            
            if not result:
                return IntegrityCheckResult(
                    check_name="Negative User Totals",
                    status="PASS",
                    message="No users with negative totals found"
                )
            
            affected_users = []
            for row in result[:self.max_affected_users_to_log]:
                user_hash = row[0]
                total_expenses = row[1]
                expense_count = row[2]
                affected_users.append(f"{user_hash[:8]}... total:{total_expenses} count:{expense_count}")
            
            return IntegrityCheckResult(
                check_name="Negative User Totals",
                status="FAIL",
                message=f"Found {len(result)} users with negative totals",
                affected_users=affected_users,
                affected_count=len(result)
            )
            
        except Exception as e:
            return IntegrityCheckResult(
                check_name="Negative User Totals",
                status="FAIL",
                message=f"Check failed: {str(e)}"
            )
    
    def _check_future_dated_expenses(self) -> IntegrityCheckResult:
        """Check for expenses dated more than 1 day in the future"""
        try:
            query = text("""
                SELECT user_id_hash, id, amount, date, created_at
                FROM expenses
                WHERE date > CURRENT_DATE + INTERVAL '1 day'
                ORDER BY date DESC
                LIMIT 100
            """)
            
            result = db.session.execute(query).fetchall()
            
            if not result:
                return IntegrityCheckResult(
                    check_name="Future Dated Expenses",
                    status="PASS",
                    message="No future-dated expenses found"
                )
            
            affected_users = []
            for row in result[:self.max_affected_users_to_log]:
                user_hash = row[0]
                expense_id = row[1]
                amount = row[2]
                expense_date = row[3]
                affected_users.append(f"{user_hash[:8]}... expense_id:{expense_id} amount:{amount} date:{expense_date}")
            
            return IntegrityCheckResult(
                check_name="Future Dated Expenses",
                status="WARNING",
                message=f"Found {len(result)} expenses dated in the future",
                affected_users=affected_users,
                affected_count=len(result)
            )
            
        except Exception as e:
            return IntegrityCheckResult(
                check_name="Future Dated Expenses",
                status="FAIL",
                message=f"Check failed: {str(e)}"
            )
    
    def _generate_report(self) -> IntegrityReport:
        """Generate comprehensive integrity report"""
        end_time = datetime.utcnow()
        
        passed = len([c for c in self.checks if c.status == 'PASS'])
        failed = len([c for c in self.checks if c.status == 'FAIL'])
        warnings = len([c for c in self.checks if c.status == 'WARNING'])
        
        if failed > 0:
            overall_status = 'CRITICAL'
        elif warnings > 0:
            overall_status = 'WARNING'
        else:
            overall_status = 'HEALTHY'
        
        # Generate summary
        if failed == 0 and warnings == 0:
            summary = f"✅ ALL CHECKS PASSED - Data integrity is healthy ({passed} checks)"
        elif failed > 0:
            summary = f"❌ CRITICAL ISSUES FOUND - {failed} failures, {warnings} warnings, {passed} passed"
        else:
            summary = f"⚠️ WARNINGS DETECTED - {warnings} warnings, {passed} passed"
        
        return IntegrityReport(
            run_id=self.run_id,
            start_time=self.start_time.isoformat(),
            end_time=end_time.isoformat(),
            total_checks=len(self.checks),
            passed=passed,
            failed=failed,
            warnings=warnings,
            overall_status=overall_status,
            checks=self.checks,
            summary=summary
        )

def run_integrity_check() -> IntegrityReport:
    """Main entry point for running integrity checks"""
    checker = DataIntegrityChecker()
    return checker.run_all_checks()

if __name__ == "__main__":
    # Standalone execution
    from app import app
    
    with app.app_context():
        print("=" * 80)
        print("FINBRAIN DATA INTEGRITY CHECK")
        print("=" * 80)
        
        report = run_integrity_check()
        
        print(f"\nRun ID: {report.run_id}")
        print(f"Overall Status: {report.overall_status}")
        print(f"Summary: {report.summary}")
        print(f"Duration: {(datetime.fromisoformat(report.end_time) - datetime.fromisoformat(report.start_time)).total_seconds():.2f} seconds")
        
        print(f"\n{'='*80}")
        print("DETAILED RESULTS")
        print("="*80)
        
        for check in report.checks:
            status_emoji = "✅" if check.status == "PASS" else "❌" if check.status == "FAIL" else "⚠️"
            print(f"\n{status_emoji} {check.check_name}: {check.status}")
            print(f"   {check.message}")
            
            if check.affected_users:
                print(f"   Affected users: {', '.join(check.affected_users)}")
        
        # Exit with appropriate code
        exit_code = 0 if report.overall_status == 'HEALTHY' else 1
        print(f"\nExit code: {exit_code}")
        exit(exit_code)