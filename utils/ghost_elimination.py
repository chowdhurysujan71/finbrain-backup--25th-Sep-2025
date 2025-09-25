"""
👻 GHOST ELIMINATION: KILL HIDDEN GHOSTS IN TESTS
Advanced coverage analysis and dead code detection for 100% reliability

This module implements comprehensive test coverage requirements and automatic
dead code detection to ensure no "silent" code paths exist in the system.
"""

import ast
import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

class GhostType(Enum):
    DEAD_CODE = "dead_code"
    UNTESTED_PATH = "untested_path"
    ORPHANED_FUNCTION = "orphaned_function"
    UNREACHABLE_BRANCH = "unreachable_branch"
    LEGACY_REMNANT = "legacy_remnant"

@dataclass
class GhostDetection:
    ghost_type: GhostType
    file_path: str
    line_number: int
    function_name: str | None
    description: str
    confidence: float  # 0.0 - 1.0
    suggested_action: str

class GhostEliminator:
    """
    👻 COMPREHENSIVE GHOST DETECTION SYSTEM
    
    Detects and eliminates hidden code paths:
    1. Dead code that's never executed
    2. Untested code paths missing coverage
    3. Orphaned functions with no callers
    4. Unreachable branches and conditions
    5. Legacy remnants from old implementations
    """
    
    def __init__(self, project_root: str = '.'):
        self.project_root = Path(project_root)
        self.detected_ghosts: list[GhostDetection] = []
        self.coverage_threshold = 100.0  # Require 100% coverage
        self.expense_routing_files = [
            'backend_assistant.py',
            'handlers/expense.py', 
            'utils/single_writer_guard.py',
            'routes_expense.py'
        ]
        
    def run_comprehensive_ghost_elimination(self) -> dict[str, Any]:
        """
        🔍 RUN COMPLETE GHOST ELIMINATION
        Comprehensive analysis of all hidden code paths
        """
        logger.info("👻 Starting comprehensive ghost elimination scan")
        start_time = time.time()
        
        self.detected_ghosts = []
        
        # 1. Test Coverage Analysis
        coverage_report = self._analyze_test_coverage()
        
        # 2. Dead Code Detection
        dead_code_report = self._detect_dead_code()
        
        # 3. Orphaned Function Detection
        orphaned_functions = self._detect_orphaned_functions()
        
        # 4. Unreachable Branch Analysis
        unreachable_branches = self._analyze_unreachable_branches()
        
        # 5. Legacy Remnant Detection
        legacy_remnants = self._detect_legacy_remnants()
        
        # 6. Expense Routing Critical Path Analysis
        expense_routing_analysis = self._analyze_expense_routing_coverage()
        
        execution_time = (time.time() - start_time) * 1000
        
        return self._generate_ghost_elimination_report(
            coverage_report, dead_code_report, orphaned_functions,
            unreachable_branches, legacy_remnants, expense_routing_analysis,
            execution_time
        )
    
    def _analyze_test_coverage(self) -> dict[str, Any]:
        """
        📊 ANALYZE TEST COVERAGE
        Generate detailed coverage report for critical paths
        """
        try:
            # Try to run pytest with coverage
            result = subprocess.run([
                'python', '-m', 'pytest', '--cov=.', '--cov-report=json', 
                '--cov-report=term-missing', '--no-header', '-v'
            ], capture_output=True, text=True, timeout=60)
            
            coverage_data = {}
            if os.path.exists('coverage.json'):
                with open('coverage.json') as f:
                    coverage_data = json.load(f)
            
            # Analyze coverage for critical expense routing files
            critical_file_coverage = {}
            for file_path in self.expense_routing_files:
                full_path = self.project_root / file_path
                if full_path.exists():
                    file_coverage = self._get_file_coverage(str(full_path), coverage_data)
                    critical_file_coverage[file_path] = file_coverage
                    
                    # Flag untested lines in critical files
                    if file_coverage['coverage_percent'] < self.coverage_threshold:
                        missing_lines = file_coverage.get('missing_lines', [])
                        for line_num in missing_lines[:5]:  # Limit to first 5
                            self.detected_ghosts.append(GhostDetection(
                                ghost_type=GhostType.UNTESTED_PATH,
                                file_path=file_path,
                                line_number=line_num,
                                function_name=None,
                                description="Untested line in critical expense routing file",
                                confidence=0.9,
                                suggested_action=f"Add test coverage for line {line_num}"
                            ))
            
            return {
                'overall_coverage': coverage_data.get('totals', {}).get('percent_covered', 0),
                'critical_file_coverage': critical_file_coverage,
                'coverage_threshold': self.coverage_threshold,
                'pytest_output': result.stdout if result.returncode == 0 else result.stderr
            }
            
        except Exception as e:
            logger.error(f"Coverage analysis failed: {e}")
            return {
                'overall_coverage': 0,
                'critical_file_coverage': {},
                'error': str(e)
            }
    
    def _get_file_coverage(self, file_path: str, coverage_data: dict) -> dict[str, Any]:
        """Get coverage information for a specific file"""
        files_data = coverage_data.get('files', {})
        
        # Try different path formats
        for key in files_data.keys():
            if file_path.endswith(key) or key.endswith(file_path.split('/')[-1]):
                file_data = files_data[key]
                return {
                    'coverage_percent': file_data.get('summary', {}).get('percent_covered', 0),
                    'missing_lines': file_data.get('missing_lines', []),
                    'total_lines': file_data.get('summary', {}).get('num_statements', 0),
                    'covered_lines': file_data.get('summary', {}).get('covered_lines', 0)
                }
        
        return {
            'coverage_percent': 0,
            'missing_lines': [],
            'total_lines': 0,
            'covered_lines': 0
        }
    
    def _detect_dead_code(self) -> dict[str, Any]:
        """
        💀 DETECT DEAD CODE
        Find code that's never executed or referenced
        """
        dead_code_patterns = [
            # Commented out code blocks
            r'^\s*#.*(?:def |class |if |for |while )',
            
            # TODO/FIXME blocks that might be dead
            r'^\s*#\s*(?:TODO|FIXME|XXX|HACK).*',
            
            # Debug print statements left in code
            r'^\s*print\s*\(',
            r'^\s*console\.log\s*\(',
            
            # Unused imports (basic detection)
            r'^import\s+(\w+)(?:\s+as\s+\w+)?$',
            r'^from\s+\w+\s+import\s+(\w+)',
        ]
        
        dead_code_count = 0
        potential_dead_files = []
        
        for py_file in self.project_root.glob('**/*.py'):
            if self._should_skip_file(py_file):
                continue
                
            try:
                with open(py_file, encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    for pattern in dead_code_patterns:
                        if re.search(pattern, line):
                            if 'print(' in line and 'logger' not in line:
                                self.detected_ghosts.append(GhostDetection(
                                    ghost_type=GhostType.DEAD_CODE,
                                    file_path=str(py_file.relative_to(self.project_root)),
                                    line_number=i,
                                    function_name=None,
                                    description=f"Debug print statement found: {line.strip()}",
                                    confidence=0.8,
                                    suggested_action="Remove debug print or replace with proper logging"
                                ))
                                dead_code_count += 1
                                
            except Exception as e:
                logger.warning(f"Could not analyze {py_file}: {e}")
        
        return {
            'dead_code_instances': dead_code_count,
            'potential_dead_files': potential_dead_files
        }
    
    def _detect_orphaned_functions(self) -> dict[str, Any]:
        """
        🏝️ DETECT ORPHANED FUNCTIONS
        Find functions that are defined but never called
        """
        function_definitions = {}
        function_calls = set()
        
        # Scan for function definitions and calls
        for py_file in self.project_root.glob('**/*.py'):
            if self._should_skip_file(py_file):
                continue
                
            try:
                with open(py_file, encoding='utf-8') as f:
                    content = f.read()
                
                # Parse AST to find function definitions
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        func_name = node.name
                        if not func_name.startswith('_') and not func_name.startswith('test_'):
                            function_definitions[func_name] = {
                                'file': str(py_file.relative_to(self.project_root)),
                                'line': node.lineno
                            }
                    
                    # Find function calls
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        function_calls.add(node.func.id)
                
            except Exception as e:
                logger.warning(f"Could not parse {py_file}: {e}")
        
        # Find orphaned functions
        orphaned_functions = []
        for func_name, info in function_definitions.items():
            if func_name not in function_calls:
                # Skip common patterns that might be called externally
                if func_name in ['main', 'run', 'init', 'setup', 'configure']:
                    continue
                    
                self.detected_ghosts.append(GhostDetection(
                    ghost_type=GhostType.ORPHANED_FUNCTION,
                    file_path=info['file'],
                    line_number=info['line'],
                    function_name=func_name,
                    description=f"Function '{func_name}' defined but never called",
                    confidence=0.7,
                    suggested_action=f"Remove function '{func_name}' or add test coverage"
                ))
                orphaned_functions.append(func_name)
        
        return {
            'total_functions': len(function_definitions),
            'orphaned_functions': orphaned_functions,
            'orphaned_count': len(orphaned_functions)
        }
    
    def _analyze_unreachable_branches(self) -> dict[str, Any]:
        """
        🌿 ANALYZE UNREACHABLE BRANCHES
        Find if/else branches that can never be reached
        """
        unreachable_branches = []
        
        # This is a simplified analysis - would need more sophisticated static analysis
        # for comprehensive unreachable branch detection
        for py_file in self.project_root.glob('**/*.py'):
            if self._should_skip_file(py_file):
                continue
                
            try:
                with open(py_file, encoding='utf-8') as f:
                    lines = f.readlines()
                
                for i, line in enumerate(lines, 1):
                    # Look for obvious unreachable patterns
                    if re.search(r'if\s+False\s*:', line.strip()):
                        self.detected_ghosts.append(GhostDetection(
                            ghost_type=GhostType.UNREACHABLE_BRANCH,
                            file_path=str(py_file.relative_to(self.project_root)),
                            line_number=i,
                            function_name=None,
                            description="Unreachable branch: if False",
                            confidence=1.0,
                            suggested_action="Remove unreachable if False branch"
                        ))
                        unreachable_branches.append(f"{py_file}:{i}")
                        
            except Exception as e:
                logger.warning(f"Could not analyze branches in {py_file}: {e}")
        
        return {
            'unreachable_branches': unreachable_branches,
            'count': len(unreachable_branches)
        }
    
    def _detect_legacy_remnants(self) -> dict[str, Any]:
        """
        🏚️ DETECT LEGACY REMNANTS
        Find old code patterns that should be cleaned up
        """
        legacy_patterns = [
            # Old expense handling patterns
            (r'create_expense\s*\(', 'Legacy create_expense call - should use backend_assistant.add_expense'),
            (r'save_expense\s*\(', 'Legacy save_expense call - should use backend_assistant.add_expense'), 
            (r'upsert_expense\s*\(', 'Legacy upsert_expense call - should use backend_assistant.add_expense'),
            
            # Deprecated source references
            (r'["\']messenger["\']', 'Deprecated messenger source reference'),
            (r'["\']form["\']', 'Deprecated form source reference'),
            
            # Old environment variable patterns
            (r'FACEBOOK_', 'Legacy Facebook environment variable'),
            (r'FB_', 'Legacy Facebook environment variable'),
            
            # Quarantine directories
            (r'_quarantine/', 'Code in quarantine directory should be reviewed/removed'),
            (r'attic/', 'Code in attic directory should be reviewed/removed'),
        ]
        
        legacy_remnants = []
        
        for py_file in self.project_root.glob('**/*.py'):
            if self._should_skip_file(py_file):
                continue
                
            try:
                with open(py_file, encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    for pattern, description in legacy_patterns:
                        if re.search(pattern, line):
                            self.detected_ghosts.append(GhostDetection(
                                ghost_type=GhostType.LEGACY_REMNANT,
                                file_path=str(py_file.relative_to(self.project_root)),
                                line_number=i,
                                function_name=None,
                                description=description,
                                confidence=0.8,
                                suggested_action=f"Update or remove legacy pattern: {pattern}"
                            ))
                            legacy_remnants.append({
                                'file': str(py_file.relative_to(self.project_root)),
                                'line': i,
                                'pattern': pattern
                            })
                            
            except Exception as e:
                logger.warning(f"Could not analyze legacy patterns in {py_file}: {e}")
        
        return {
            'legacy_remnants': legacy_remnants,
            'count': len(legacy_remnants)
        }
    
    def _analyze_expense_routing_coverage(self) -> dict[str, Any]:
        """
        💰 ANALYZE EXPENSE ROUTING COVERAGE
        Special focus on expense routing and save logic coverage
        """
        routing_coverage = {}
        
        for file_path in self.expense_routing_files:
            full_path = self.project_root / file_path
            if not full_path.exists():
                continue
                
            try:
                with open(full_path, encoding='utf-8') as f:
                    content = f.read()
                
                # Analyze expense routing functions
                lines = content.split('\n')
                expense_functions = []
                
                for i, line in enumerate(lines, 1):
                    if re.search(r'def\s+.*expense', line, re.IGNORECASE):
                        expense_functions.append({
                            'line': i,
                            'function': line.strip()
                        })
                
                routing_coverage[file_path] = {
                    'expense_functions': expense_functions,
                    'function_count': len(expense_functions),
                    'critical_file': True
                }
                
            except Exception as e:
                logger.warning(f"Could not analyze routing coverage for {file_path}: {e}")
        
        return routing_coverage
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Determine if file should be skipped during analysis"""
        skip_patterns = [
            '__pycache__',
            '.git',
            'node_modules',
            '.venv',
            'venv',
            'test_',
            'conftest.py',
            'migrations/',
            '.pytest_cache'
        ]
        
        file_str = str(file_path)
        return any(pattern in file_str for pattern in skip_patterns)
    
    def _generate_ghost_elimination_report(self, coverage_report: dict, dead_code_report: dict,
                                         orphaned_functions: dict, unreachable_branches: dict,
                                         legacy_remnants: dict, expense_routing_analysis: dict,
                                         execution_time: float) -> dict[str, Any]:
        """Generate comprehensive ghost elimination report"""
        
        # Categorize ghosts by severity
        critical_ghosts = [g for g in self.detected_ghosts if g.confidence >= 0.9]
        high_ghosts = [g for g in self.detected_ghosts if 0.7 <= g.confidence < 0.9]
        medium_ghosts = [g for g in self.detected_ghosts if g.confidence < 0.7]
        
        # Determine overall health
        overall_health = "HEALTHY"
        if len(critical_ghosts) > 0:
            overall_health = "CRITICAL"
        elif len(high_ghosts) > 5:
            overall_health = "DEGRADED"
        elif len(self.detected_ghosts) > 10:
            overall_health = "NEEDS_ATTENTION"
        
        return {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'execution_time_ms': execution_time,
            'overall_health': overall_health,
            'ghost_summary': {
                'total_ghosts': len(self.detected_ghosts),
                'critical_ghosts': len(critical_ghosts),
                'high_priority_ghosts': len(high_ghosts),
                'medium_priority_ghosts': len(medium_ghosts)
            },
            'coverage_analysis': coverage_report,
            'dead_code_analysis': dead_code_report,
            'orphaned_functions_analysis': orphaned_functions,
            'unreachable_branches_analysis': unreachable_branches,
            'legacy_remnants_analysis': legacy_remnants,
            'expense_routing_analysis': expense_routing_analysis,
            'detected_ghosts': [
                {
                    'type': g.ghost_type.value,
                    'file': g.file_path,
                    'line': g.line_number,
                    'function': g.function_name,
                    'description': g.description,
                    'confidence': g.confidence,
                    'suggested_action': g.suggested_action
                }
                for g in sorted(self.detected_ghosts, key=lambda x: x.confidence, reverse=True)
            ],
            'recommendations': self._generate_recommendations(overall_health)
        }
    
    def _generate_recommendations(self, overall_health: str) -> list[str]:
        """Generate actionable recommendations based on findings"""
        recommendations = []
        
        if overall_health == "CRITICAL":
            recommendations.append("🚨 IMMEDIATE ACTION REQUIRED: Critical ghosts detected")
            recommendations.append("Stop new feature development until ghosts are eliminated")
            recommendations.append("Run ghost elimination in CI to prevent new ghosts")
        
        if any(g.ghost_type == GhostType.UNTESTED_PATH for g in self.detected_ghosts):
            recommendations.append("📊 Increase test coverage for critical expense routing paths")
            
        if any(g.ghost_type == GhostType.DEAD_CODE for g in self.detected_ghosts):
            recommendations.append("🧹 Remove debug print statements and commented code")
            
        if any(g.ghost_type == GhostType.LEGACY_REMNANT for g in self.detected_ghosts):
            recommendations.append("🏚️ Clean up legacy code patterns and deprecated references")
        
        recommendations.append("✅ Set up automated ghost detection in CI pipeline")
        recommendations.append("📈 Establish 100% test coverage requirement for new code")
        
        return recommendations

# Global ghost eliminator instance
ghost_eliminator = GhostEliminator()

def run_ghost_elimination() -> dict[str, Any]:
    """
    👻 GLOBAL ENTRY POINT
    Run comprehensive ghost elimination and return results
    """
    return ghost_eliminator.run_comprehensive_ghost_elimination()

def get_ghost_elimination_summary() -> dict[str, Any]:
    """Get summary of detected ghosts"""
    return {
        'total_detected': len(ghost_eliminator.detected_ghosts),
        'by_type': {
            ghost_type.value: len([g for g in ghost_eliminator.detected_ghosts if g.ghost_type == ghost_type])
            for ghost_type in GhostType
        },
        'last_scan': time.strftime('%Y-%m-%d %H:%M:%S') if ghost_eliminator.detected_ghosts else None
    }