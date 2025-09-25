"""
👻 GHOST MONITORING ENDPOINTS
Real-time dead code detection and test coverage monitoring
"""

import logging
import os
import re
import time
from pathlib import Path

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

# Create blueprint for ghost monitoring
ghost_monitoring_bp = Blueprint('ghost_monitoring', __name__)

@ghost_monitoring_bp.route('/ops/ghosts/quick-scan', methods=['GET'])
def quick_ghost_scan():
    """
    👻 QUICK GHOST SCAN
    Fast scan for obvious dead code patterns in critical files
    """
    try:
        critical_files = [
            'backend_assistant.py',
            'handlers/expense.py',
            'utils/single_writer_guard.py'
        ]
        
        ghost_report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'critical_files_analyzed': len(critical_files),
            'ghosts_detected': [],
            'overall_health': 'HEALTHY'
        }
        
        for file_path in critical_files:
            if os.path.exists(file_path):
                file_ghosts = _scan_file_for_ghosts(file_path)
                ghost_report['ghosts_detected'].extend(file_ghosts)
        
        # Determine health status
        if len(ghost_report['ghosts_detected']) > 0:
            ghost_report['overall_health'] = 'NEEDS_ATTENTION'
            
        return jsonify({
            'success': True,
            'ghost_scan': ghost_report
        })
        
    except Exception as e:
        logger.error(f"Quick ghost scan failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ghost_monitoring_bp.route('/ops/ghosts/coverage-check', methods=['GET'])
def coverage_check():
    """
    📊 COVERAGE CHECK
    Check test coverage for critical expense routing paths
    """
    try:
        coverage_report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'coverage_available': False,
            'message': 'Coverage analysis requires pytest-cov installation'
        }
        
        # Try to check if coverage tools are available
        if os.path.exists('coverage.json'):
            with open('coverage.json') as f:
                import json
                coverage_data = json.load(f)
                
            coverage_report['coverage_available'] = True
            coverage_report['overall_coverage'] = coverage_data.get('totals', {}).get('percent_covered', 0)
            coverage_report['critical_files'] = _analyze_critical_file_coverage(coverage_data)
        
        return jsonify({
            'success': True,
            'coverage_report': coverage_report
        })
        
    except Exception as e:
        logger.error(f"Coverage check failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@ghost_monitoring_bp.route('/ops/ghosts/legacy-cleanup', methods=['GET'])
def legacy_cleanup_scan():
    """
    🏚️ LEGACY CLEANUP SCAN
    Identify legacy code patterns that should be cleaned up
    """
    try:
        legacy_patterns = [
            (r'create_expense\s*\(', 'Legacy expense creation - use backend_assistant.add_expense'),
            (r'["\']messenger["\']', 'Deprecated messenger source'),
            (r'["\']form["\']', 'Deprecated form source'),
            (r'print\s*\(', 'Debug print statement')
        ]
        
        legacy_report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'legacy_items_found': [],
            'cleanup_priority': 'LOW'
        }
        
        # Scan critical files for legacy patterns
        for py_file in Path('.').glob('**/*.py'):
            if _should_skip_file(py_file):
                continue
                
            try:
                with open(py_file, encoding='utf-8') as f:
                    lines = f.readlines()
                
                for i, line in enumerate(lines, 1):
                    for pattern, description in legacy_patterns:
                        if re.search(pattern, line):
                            legacy_report['legacy_items_found'].append({
                                'file': str(py_file),
                                'line': i,
                                'pattern': description,
                                'content': line.strip()[:100]  # Limit content length
                            })
                            
            except Exception as e:
                logger.warning(f"Could not scan {py_file}: {e}")
        
        # Determine cleanup priority
        if len(legacy_report['legacy_items_found']) > 10:
            legacy_report['cleanup_priority'] = 'HIGH'
        elif len(legacy_report['legacy_items_found']) > 5:
            legacy_report['cleanup_priority'] = 'MEDIUM'
        
        return jsonify({
            'success': True,
            'legacy_report': legacy_report
        })
        
    except Exception as e:
        logger.error(f"Legacy cleanup scan failed: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

def _scan_file_for_ghosts(file_path: str) -> list:
    """Scan a single file for obvious ghost patterns"""
    ghosts = []
    
    ghost_patterns = [
        (r'print\s*\(', 'Debug print statement'),
        (r'console\.log\s*\(', 'Debug console.log'),
        (r'#.*TODO|#.*FIXME|#.*XXX', 'TODO/FIXME comment'),
        (r'if\s+False\s*:', 'Unreachable if False branch')
    ]
    
    try:
        with open(file_path, encoding='utf-8') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines, 1):
            for pattern, description in ghost_patterns:
                if re.search(pattern, line):
                    ghosts.append({
                        'file': file_path,
                        'line': i,
                        'type': description,
                        'content': line.strip()[:100]
                    })
                    
    except Exception as e:
        logger.warning(f"Could not scan {file_path}: {e}")
    
    return ghosts

def _analyze_critical_file_coverage(coverage_data: dict) -> dict:
    """Analyze coverage for critical expense routing files"""
    critical_files = [
        'backend_assistant.py',
        'handlers/expense.py',
        'utils/single_writer_guard.py'
    ]
    
    critical_coverage = {}
    files_data = coverage_data.get('files', {})
    
    for critical_file in critical_files:
        for file_key in files_data.keys():
            if critical_file in file_key:
                file_data = files_data[file_key]
                critical_coverage[critical_file] = {
                    'coverage_percent': file_data.get('summary', {}).get('percent_covered', 0),
                    'missing_lines': len(file_data.get('missing_lines', [])),
                    'total_lines': file_data.get('summary', {}).get('num_statements', 0)
                }
                break
    
    return critical_coverage

def _should_skip_file(file_path: Path) -> bool:
    """Determine if file should be skipped during analysis"""
    skip_patterns = [
        '__pycache__',
        '.git',
        'node_modules',
        '.venv',
        'test_',
        'conftest.py'
    ]
    
    file_str = str(file_path)
    return any(pattern in file_str for pattern in skip_patterns)

# Error handlers
@ghost_monitoring_bp.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'Ghost monitoring endpoint not found'
    }), 404

@ghost_monitoring_bp.errorhandler(500)
def internal_error(error):
    return jsonify({
        'success': False,
        'error': 'Internal server error in ghost monitoring'
    }), 500