#!/usr/bin/env python3
"""
📊 FinBrain Data Consistency Validator
Ensures data integrity across the single writer system
"""

import os
import sys
import logging
from typing import List, Dict, Any, Optional
from decimal import Decimal, ROUND_HALF_UP
import psycopg2
from urllib.parse import urlparse

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DataConsistencyValidator:
    """Validates and enforces data consistency standards"""
    
    # Standard source values (enforced in backend_assistant.py)
    VALID_SOURCES = {'chat', 'form', 'messenger'}
    
    # Standard currency configuration
    DEFAULT_CURRENCY = 'BDT'
    SUPPORTED_CURRENCIES = {'BDT', 'USD', 'EUR', 'GBP'}
    
    # Currency precision (2 decimal places for standard currencies)
    CURRENCY_PRECISION = 2
    
    def __init__(self):
        self.violations = []
        self.stats = {
            'records_checked': 0,
            'currency_inconsistencies': 0,
            'amount_precision_errors': 0,
            'source_violations': 0,
            'null_value_issues': 0
        }
    
    def get_db_connection(self):
        """Get database connection"""
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL environment variable not found")
        return psycopg2.connect(database_url)
    
    def validate_currency_consistency(self) -> List[Dict]:
        """Check currency field consistency"""
        violations = []
        
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            
            # Check for non-standard currencies
            cur.execute("""
                SELECT DISTINCT currency, COUNT(*) as count 
                FROM transactions_effective 
                WHERE currency IS NOT NULL 
                GROUP BY currency
            """)
            
            currency_data = cur.fetchall()
            
            for currency, count in currency_data:
                if currency not in self.SUPPORTED_CURRENCIES:
                    violations.append({
                        'type': 'currency_violation',
                        'currency': currency,
                        'count': count,
                        'severity': 'MEDIUM',
                        'message': f'Non-standard currency "{currency}" found in {count} records'
                    })
                    self.stats['currency_inconsistencies'] += count
            
            # Check for null/empty currencies
            cur.execute("""
                SELECT COUNT(*) 
                FROM transactions_effective 
                WHERE currency IS NULL OR currency = ''
            """)
            
            null_currency_count = cur.fetchone()[0]
            if null_currency_count > 0:
                violations.append({
                    'type': 'null_currency',
                    'count': null_currency_count,
                    'severity': 'HIGH',
                    'message': f'{null_currency_count} records have null/empty currency'
                })
                self.stats['null_value_issues'] += null_currency_count
            
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Currency validation failed: {e}")
            violations.append({
                'type': 'validation_error',
                'severity': 'HIGH',
                'message': f'Currency validation failed: {e}'
            })
        
        return violations
    
    def validate_amount_precision(self) -> List[Dict]:
        """Check amount precision and formatting"""
        violations = []
        
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            
            # Check for amounts with more than 2 decimal places
            cur.execute("""
                SELECT id, amount, 
                       CASE 
                           WHEN amount::text ~ '\\.[0-9]{3,}$' THEN 'excess_precision'
                           WHEN amount = 0 THEN 'zero_amount'
                           WHEN amount < 0 THEN 'negative_amount'
                           ELSE 'valid'
                       END as issue_type
                FROM transactions_effective
                WHERE amount IS NOT NULL
                  AND (amount::text ~ '\\.[0-9]{3,}$' OR amount = 0 OR amount < 0)
            """)
            
            precision_issues = cur.fetchall()
            
            for record_id, amount, issue_type in precision_issues:
                violations.append({
                    'type': 'amount_precision',
                    'record_id': record_id,
                    'amount': str(amount),
                    'issue_type': issue_type,
                    'severity': 'MEDIUM' if issue_type == 'excess_precision' else 'HIGH',
                    'message': f'Amount precision issue: {issue_type} for amount {amount}'
                })
                self.stats['amount_precision_errors'] += 1
            
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Amount validation failed: {e}")
            violations.append({
                'type': 'validation_error',
                'severity': 'HIGH',
                'message': f'Amount validation failed: {e}'
            })
        
        return violations
    
    def validate_required_fields(self) -> List[Dict]:
        """Check for missing required fields"""
        violations = []
        
        required_fields = [
            ('user_id', 'User identification'),
            ('amount', 'Transaction amount'),
            ('currency', 'Currency code'),
            ('category', 'Expense category'),
            ('transaction_date', 'Transaction date')
        ]
        
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            
            for field, description in required_fields:
                cur.execute(f"""
                    SELECT COUNT(*) 
                    FROM transactions_effective 
                    WHERE {field} IS NULL OR {field} = ''
                """)
                
                null_count = cur.fetchone()[0]
                if null_count > 0:
                    violations.append({
                        'type': 'missing_required_field',
                        'field': field,
                        'count': null_count,
                        'severity': 'HIGH',
                        'message': f'{null_count} records missing required field: {description}'
                    })
                    self.stats['null_value_issues'] += null_count
            
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Required fields validation failed: {e}")
            violations.append({
                'type': 'validation_error',
                'severity': 'HIGH',
                'message': f'Required fields validation failed: {e}'
            })
        
        return violations
    
    def check_data_quality_metrics(self) -> Dict[str, Any]:
        """Generate data quality metrics"""
        metrics = {}
        
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            
            # Total records
            cur.execute("SELECT COUNT(*) FROM transactions_effective")
            metrics['total_records'] = cur.fetchone()[0]
            
            # Currency distribution
            cur.execute("""
                SELECT currency, COUNT(*) as count, 
                       ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
                FROM transactions_effective 
                WHERE currency IS NOT NULL
                GROUP BY currency 
                ORDER BY count DESC
            """)
            metrics['currency_distribution'] = cur.fetchall()
            
            # Amount statistics
            cur.execute("""
                SELECT 
                    MIN(amount) as min_amount,
                    MAX(amount) as max_amount,
                    AVG(amount) as avg_amount,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY amount) as median_amount
                FROM transactions_effective 
                WHERE amount IS NOT NULL AND amount > 0
            """)
            amount_stats = cur.fetchone()
            if amount_stats:
                metrics['amount_statistics'] = {
                    'min': float(amount_stats[0]) if amount_stats[0] else 0,
                    'max': float(amount_stats[1]) if amount_stats[1] else 0,
                    'avg': float(amount_stats[2]) if amount_stats[2] else 0,
                    'median': float(amount_stats[3]) if amount_stats[3] else 0
                }
            
            cur.close()
            conn.close()
            
        except Exception as e:
            logger.error(f"Metrics generation failed: {e}")
            metrics['error'] = str(e)
        
        return metrics
    
    def run_full_validation(self) -> Dict[str, Any]:
        """Run comprehensive data consistency validation"""
        logger.info("🔍 Starting comprehensive data consistency validation...")
        
        all_violations = []
        
        # 1. Currency consistency
        logger.info("💰 Validating currency consistency...")
        currency_violations = self.validate_currency_consistency()
        all_violations.extend(currency_violations)
        
        # 2. Amount precision
        logger.info("📊 Validating amount precision...")
        amount_violations = self.validate_amount_precision()
        all_violations.extend(amount_violations)
        
        # 3. Required fields
        logger.info("📋 Validating required fields...")
        field_violations = self.validate_required_fields()
        all_violations.extend(field_violations)
        
        # 4. Generate metrics
        logger.info("📈 Generating data quality metrics...")
        metrics = self.check_data_quality_metrics()
        
        self.violations = all_violations
        
        return {
            'total_violations': len(all_violations),
            'violations': all_violations,
            'statistics': self.stats,
            'data_quality_metrics': metrics,
            'validation_summary': self.generate_summary()
        }
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate validation summary"""
        violations_by_severity = {}
        violations_by_type = {}
        
        for violation in self.violations:
            severity = violation.get('severity', 'UNKNOWN')
            violations_by_severity[severity] = violations_by_severity.get(severity, 0) + 1
            
            v_type = violation['type']
            violations_by_type[v_type] = violations_by_type.get(v_type, 0) + 1
        
        return {
            'by_severity': violations_by_severity,
            'by_type': violations_by_type,
            'statistics': self.stats
        }
    
    def generate_report(self) -> str:
        """Generate comprehensive data consistency report"""
        report_lines = [
            "📊 FINBRAIN DATA CONSISTENCY REPORT",
            "=" * 50,
            "",
            f"🎯 VALIDATION STATISTICS:",
            f"  Total Violations: {len(self.violations)}",
            f"  Records Checked: {self.stats['records_checked']}",
            f"  Currency Issues: {self.stats['currency_inconsistencies']}",
            f"  Amount Precision Errors: {self.stats['amount_precision_errors']}",
            f"  Null Value Issues: {self.stats['null_value_issues']}",
            ""
        ]
        
        if not self.violations:
            report_lines.extend([
                "✅ NO DATA CONSISTENCY VIOLATIONS FOUND!",
                "🎉 Your data follows consistency standards.",
                ""
            ])
        else:
            # Group by severity
            high_violations = [v for v in self.violations if v.get('severity') == 'HIGH']
            medium_violations = [v for v in self.violations if v.get('severity') == 'MEDIUM']
            
            if high_violations:
                report_lines.extend([
                    "🚨 HIGH SEVERITY VIOLATIONS:",
                    "-" * 30
                ])
                for violation in high_violations[:10]:  # Show first 10
                    report_lines.append(f"  {violation['message']}")
                    if len(high_violations) > 10:
                        report_lines.append(f"  ... and {len(high_violations) - 10} more")
                        break
                report_lines.append("")
            
            if medium_violations:
                report_lines.extend([
                    "⚠️  MEDIUM SEVERITY VIOLATIONS:",
                    "-" * 30
                ])
                for violation in medium_violations[:5]:  # Show first 5
                    report_lines.append(f"  {violation['message']}")
                    if len(medium_violations) > 5:
                        report_lines.append(f"  ... and {len(medium_violations) - 5} more")
                        break
                report_lines.append("")
        
        return "\n".join(report_lines)

def main():
    """Main data consistency validation entry point"""
    validator = DataConsistencyValidator()
    results = validator.run_full_validation()
    
    # Generate and display report
    report = validator.generate_report()
    print(report)
    
    # Show data quality metrics
    metrics = results.get('data_quality_metrics', {})
    if 'currency_distribution' in metrics:
        print("\n💰 CURRENCY DISTRIBUTION:")
        for currency, count, percentage in metrics['currency_distribution']:
            print(f"  {currency}: {count} records ({percentage}%)")
    
    # Return exit code based on violations
    high_violations = [v for v in validator.violations if v.get('severity') == 'HIGH']
    if high_violations:
        logger.error(f"❌ {len(high_violations)} high severity violations found")
        return 1
    elif validator.violations:
        logger.warning(f"⚠️  {len(validator.violations)} violations found")
        return 0
    else:
        logger.info("✅ No data consistency violations found")
        return 0

if __name__ == "__main__":
    sys.exit(main())