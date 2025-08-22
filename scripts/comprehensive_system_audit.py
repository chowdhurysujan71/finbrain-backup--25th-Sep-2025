#!/usr/bin/env python3
"""
FinBrain Comprehensive System Audit
Generates a structured diagnostic report of all system components
"""

import os
import sys
import time
import json
from datetime import datetime, timedelta
from decimal import Decimal

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_comprehensive_audit():
    """Run comprehensive system audit within application context"""
    
    from app import app, db
    from models import Expense, User
    from utils.feature_flags import get_canary_status, is_smart_nlp_enabled, is_smart_corrections_enabled
    from utils.identity import psid_hash
    from finbrain.router import contains_money, normalize_text
    from parsers.expense import parse_expense, is_correction_message, CORRECTION_PATTERNS
    from utils.production_router import production_router
    import traceback
    
    print("=" * 80)
    print("FINBRAIN COMPREHENSIVE SYSTEM AUDIT")
    print(f"Timestamp: {datetime.utcnow().isoformat()}Z")
    print("=" * 80)
    
    audit_results = {
        'timestamp': datetime.utcnow().isoformat(),
        'environment': {},
        'feature_flags': {},
        'router': {},
        'nlp_parser': {},
        'database': {},
        'corrections': {},
        'telemetry': {},
        'performance': {},
        'issues': [],
        'verdict': 'UNKNOWN'
    }
    
    with app.app_context():
        
        # === 1. ENVIRONMENT & FLAGS AUDIT ===
        print("\n1. ENVIRONMENT & FLAGS AUDIT")
        print("-" * 40)
        
        env_vars = {
            'SMART_NLP_ROUTING_DEFAULT': os.environ.get('SMART_NLP_ROUTING_DEFAULT', 'NOT_SET'),
            'SMART_NLP_TONE_FOR_STD': os.environ.get('SMART_NLP_TONE_FOR_STD', 'NOT_SET'),
            'SMART_CORRECTIONS_DEFAULT': os.environ.get('SMART_CORRECTIONS_DEFAULT', 'NOT_SET'),
            'FEATURE_ALLOWLIST_SMART_NLP_ROUTING': os.environ.get('FEATURE_ALLOWLIST_SMART_NLP_ROUTING', 'NOT_SET'),
            'FEATURE_ALLOWLIST_SMART_CORRECTIONS': os.environ.get('FEATURE_ALLOWLIST_SMART_CORRECTIONS', 'NOT_SET'),
            'DATABASE_URL': 'SET' if os.environ.get('DATABASE_URL') else 'NOT_SET',
            'PAGE_ACCESS_TOKEN': 'SET' if os.environ.get('PAGE_ACCESS_TOKEN') else 'NOT_SET'
        }
        
        audit_results['environment'] = env_vars
        
        for key, value in env_vars.items():
            print(f"  {key}: {value}")
        
        # Feature flag status
        flag_status = get_canary_status()
        audit_results['feature_flags'] = flag_status
        
        print(f"  Flag Status: {flag_status}")
        
        # Test specific PSIDs
        test_psids = ['test_user_123', 'allowlist_user_abc123']
        flag_tests = {}
        
        for psid in test_psids:
            user_hash = psid_hash(psid)
            flag_tests[psid] = {
                'hash': user_hash[:8] + '...',
                'smart_nlp': is_smart_nlp_enabled(user_hash),
                'smart_corrections': is_smart_corrections_enabled(user_hash)
            }
            print(f"  PSID {psid}: NLP={flag_tests[psid]['smart_nlp']}, CORRECTIONS={flag_tests[psid]['smart_corrections']}")
        
        audit_results['feature_flags']['test_results'] = flag_tests
        
        # === 2. ROUTER & NLP PARSER AUDIT ===
        print("\n2. ROUTER & NLP PARSER AUDIT")
        print("-" * 40)
        
        money_tests = [
            ('coffee 100', True, 'Basic food expense'),
            ('spent $5 at Starbucks', True, 'USD with merchant'),
            ('৳250 groceries from Mina Bazar', True, 'BDT with merchant'),
            ('blew 1.2k tk', True, 'Shorthand amount'),
            ('summary', False, 'Summary request'),
            ('help', False, 'Help request')
        ]
        
        money_results = {}
        for text, expected, desc in money_tests:
            detected = contains_money(text)
            status = 'PASS' if detected == expected else 'FAIL'
            money_results[text] = {'detected': detected, 'expected': expected, 'status': status, 'desc': desc}
            print(f"  Money Detection: \"{text}\" → {detected} ({status})")
            
            if status == 'FAIL':
                audit_results['issues'].append(f"Money detection failed: \"{text}\" expected {expected}, got {detected}")
        
        audit_results['nlp_parser']['money_detection'] = money_results
        
        # Parsing tests
        expense_texts = [
            'coffee 100',
            'spent $5 at Starbucks', 
            '৳250 groceries from Mina Bazar',
            'blew 1.2k tk on fuel yesterday'
        ]
        
        parsing_results = {}
        for text in expense_texts:
            try:
                start = time.time()
                result = parse_expense(text, datetime.utcnow())
                parse_time = (time.time() - start) * 1000
                
                if result:
                    parsing_results[text] = {
                        'success': True,
                        'amount': float(result.get('amount', 0)),
                        'currency': result.get('currency'),
                        'category': result.get('category'),
                        'merchant': result.get('merchant'),
                        'parse_time_ms': parse_time
                    }
                    print(f"  Parse \"{text}\": ✅ {result['amount']} {result['currency']} ({parse_time:.1f}ms)")
                else:
                    parsing_results[text] = {'success': False, 'parse_time_ms': parse_time}
                    print(f"  Parse \"{text}\": ❌ FAILED ({parse_time:.1f}ms)")
                    audit_results['issues'].append(f"Parsing failed for: \"{text}\"")
                    
            except Exception as e:
                parsing_results[text] = {'success': False, 'error': str(e)}
                print(f"  Parse \"{text}\": ❌ ERROR: {e}")
                audit_results['issues'].append(f"Parsing error for \"{text}\": {e}")
        
        audit_results['nlp_parser']['parsing'] = parsing_results
        
        # === 3. CORRECTION DETECTION AUDIT ===
        print("\n3. CORRECTION DETECTION AUDIT")
        print("-" * 40)
        
        correction_tests = [
            ('sorry, I meant 500', True, 'Classic correction phrase'),
            ('actually 300 for lunch', True, 'Actually pattern'),
            ('typo - make it $100', True, 'Typo fix with USD'),
            ('replace last with 400', True, 'Replace pattern'),
            ('correction: should be 250', True, 'Correction label'),
            ('sorry for the delay', False, 'Apology without money'),
            ('coffee 50', False, 'Regular expense')
        ]
        
        correction_results = {}
        print(f"  Pattern: {CORRECTION_PATTERNS.pattern}")
        
        for text, expected, desc in correction_tests:
            pattern_match = bool(CORRECTION_PATTERNS.search(text))
            has_money = contains_money(text)
            detected = is_correction_message(text)
            status = 'PASS' if detected == expected else 'FAIL'
            
            correction_results[text] = {
                'pattern_match': pattern_match,
                'has_money': has_money,
                'detected': detected,
                'expected': expected,
                'status': status,
                'desc': desc
            }
            
            print(f"  \"{text}\" ({desc})")
            print(f"    Pattern: {pattern_match}, Money: {has_money}, Result: {detected} ({status})")
            
            if status == 'FAIL':
                audit_results['issues'].append(f"Correction detection failed: \"{text}\" expected {expected}, got {detected}")
        
        audit_results['corrections']['detection'] = correction_results
        
        # === 4. DATABASE AUDIT ===
        print("\n4. DATABASE AUDIT")
        print("-" * 40)
        
        try:
            # Test connection
            start = time.time()
            db.session.execute(db.text('SELECT 1')).scalar()
            conn_time = (time.time() - start) * 1000
            print(f"  Connection time: {conn_time:.1f}ms")
            
            # Test counts
            expense_count = db.session.query(Expense).count()
            user_count = db.session.query(User).count()
            active_expenses = db.session.query(Expense).filter(Expense.superseded_by.is_(None)).count()
            superseded_expenses = db.session.query(Expense).filter(Expense.superseded_by.isnot(None)).count()
            
            print(f"  Total expenses: {expense_count}")
            print(f"  Active expenses: {active_expenses}")
            print(f"  Superseded expenses: {superseded_expenses}")
            print(f"  Total users: {user_count}")
            
            # Test query performance
            start = time.time()
            recent_expenses = db.session.query(Expense).filter(
                Expense.created_at >= datetime.utcnow() - timedelta(hours=24)
            ).count()
            query_time = (time.time() - start) * 1000
            print(f"  Recent expenses (24h): {recent_expenses} ({query_time:.1f}ms)")
            
            audit_results['database'] = {
                'connection_time_ms': conn_time,
                'total_expenses': expense_count,
                'active_expenses': active_expenses,
                'superseded_expenses': superseded_expenses,
                'total_users': user_count,
                'recent_expenses_24h': recent_expenses,
                'query_time_ms': query_time,
                'status': 'HEALTHY'
            }
            
            # Performance check
            if conn_time > 100:
                audit_results['issues'].append(f"Database connection slow: {conn_time:.1f}ms > 100ms")
            if query_time > 500:
                audit_results['issues'].append(f"Query performance slow: {query_time:.1f}ms > 500ms")
                
        except Exception as e:
            print(f"  Database error: {e}")
            audit_results['database'] = {'status': 'FAILED', 'error': str(e)}
            audit_results['issues'].append(f"Database connectivity failed: {e}")
        
        # === 5. ROUTER PRECEDENCE AUDIT ===
        print("\n5. ROUTER PRECEDENCE AUDIT")
        print("-" * 40)
        
        test_psid = f"audit_user_{int(time.time())}"
        router_tests = [
            ('coffee 100', 'LOG', 'Basic expense - should be LOG'),
            ('summary', 'SUMMARY', 'Summary request - should be SUMMARY'),
            ('spent 50 at cafe', 'LOG', 'Expense with money - should override SUMMARY'),
            ('help', 'HELP', 'Help request - should be deterministic')
        ]
        
        router_results = {}
        for text, expected_intent, desc in router_tests:
            try:
                start = time.time()
                response, intent, category, amount = production_router.route_message(
                    text, test_psid, f'test_msg_{int(time.time()*1000)}'
                )
                duration = (time.time() - start) * 1000
                
                # Normalize intent for comparison
                actual_intent = intent.upper() if intent else 'ERROR'
                if actual_intent == 'LOG_EXPENSE':
                    actual_intent = 'LOG'
                
                status = 'PASS' if actual_intent == expected_intent else 'FAIL'
                
                router_results[text] = {
                    'expected_intent': expected_intent,
                    'actual_intent': actual_intent,
                    'category': category,
                    'amount': amount,
                    'duration_ms': duration,
                    'status': status,
                    'response_preview': response[:100] + '...' if len(response) > 100 else response
                }
                
                print(f"  \"{text}\" ({desc})")
                print(f"    Intent: {actual_intent} (expected {expected_intent}) - {status}")
                print(f"    Duration: {duration:.1f}ms")
                
                if status == 'FAIL':
                    audit_results['issues'].append(f"Router precedence failed: \"{text}\" expected {expected_intent}, got {actual_intent}")
                
                if duration > 1000:
                    audit_results['issues'].append(f"Router performance slow: \"{text}\" took {duration:.1f}ms > 1000ms")
                    
            except Exception as e:
                router_results[text] = {'status': 'ERROR', 'error': str(e)}
                print(f"  \"{text}\" - ERROR: {e}")
                audit_results['issues'].append(f"Router error for \"{text}\": {e}")
        
        audit_results['router']['precedence_tests'] = router_results
    
    # === 6. FINAL VERDICT ===
    print("\n6. AUDIT SUMMARY")
    print("-" * 40)
    
    critical_issues = []
    warnings = []
    
    for issue in audit_results['issues']:
        if any(keyword in issue.lower() for keyword in ['failed', 'error', 'connectivity']):
            critical_issues.append(issue)
        else:
            warnings.append(issue)
    
    print(f"  Critical Issues: {len(critical_issues)}")
    for issue in critical_issues:
        print(f"    ❌ {issue}")
    
    print(f"  Warnings: {len(warnings)}")
    for warning in warnings:
        print(f"    ⚠️  {warning}")
    
    # Determine verdict
    if len(critical_issues) == 0:
        if len(warnings) == 0:
            audit_results['verdict'] = '✅ READY FOR ROLLOUT'
        else:
            audit_results['verdict'] = '⚠️  READY WITH WARNINGS'
    else:
        audit_results['verdict'] = '❌ NEEDS FIXES'
    
    print(f"\n  FINAL VERDICT: {audit_results['verdict']}")
    
    # === 7. STRUCTURED OUTPUT ===
    audit_filename = f"audit_results_{int(time.time())}.json"
    with open(audit_filename, 'w') as f:
        json.dump(audit_results, f, indent=2, default=str)
    
    print(f"\n  Detailed results saved to: {audit_filename}")
    
    return audit_results

if __name__ == "__main__":
    try:
        results = run_comprehensive_audit()
        sys.exit(0 if '✅' in results['verdict'] else 1)
    except Exception as e:
        print(f"AUDIT FAILED: {e}")
        traceback.print_exc()
        sys.exit(1)