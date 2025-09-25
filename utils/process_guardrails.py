"""
📋 PROCESS GUARDRAILS: CODE OWNERSHIP & ARCHITECTURE PRESERVATION
Comprehensive governance system for maintaining 100% reliability framework

This module implements people and process guardrails to ensure:
- Clear code ownership and accountability
- Architecture preservation over time
- Change approval workflows for critical systems
- Reliability governance and continuous improvement
- Team structure and expertise distribution
"""

import json
import logging
import os
import re
import time
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

class OwnershipLevel(Enum):
    PRIMARY = "primary"           # Primary owner - full responsibility
    SECONDARY = "secondary"       # Secondary owner - backup support
    REVIEWER = "reviewer"         # Code reviewer - approval authority
    CONTRIBUTOR = "contributor"   # Regular contributor
    READ_ONLY = "read_only"      # Read-only access

class ChangeRisk(Enum):
    CRITICAL = "critical"         # Single writer, expense routing, auth
    HIGH = "high"                # Database schemas, API contracts
    MEDIUM = "medium"            # UI changes, non-critical features
    LOW = "low"                  # Documentation, tests, configs

class ApprovalRequirement(Enum):
    ARCHITECT_REVIEW = "architect_review"
    PRIMARY_OWNER = "primary_owner"
    SECONDARY_OWNER = "secondary_owner"
    RELIABILITY_TEAM = "reliability_team"
    NO_APPROVAL = "no_approval"

@dataclass
class CodeOwnership:
    component: str
    primary_owners: list[str]
    secondary_owners: list[str]
    reviewers: list[str]
    description: str
    risk_level: ChangeRisk
    approval_requirements: list[ApprovalRequirement]
    files_patterns: list[str]
    last_updated: str

@dataclass
class ArchitectureRule:
    rule_id: str
    title: str
    description: str
    enforced_by: str  # "automated", "manual", "both"
    violation_severity: str  # "critical", "high", "medium"
    detection_pattern: str
    remediation_action: str
    last_checked: str

@dataclass
class ChangeReview:
    change_id: str
    component: str
    risk_level: ChangeRisk
    submitter: str
    reviewers_required: list[str]
    reviewers_approved: list[str]
    status: str  # "pending", "approved", "rejected", "blocked"
    created_at: str
    files_changed: list[str]

class ProcessGuardrails:
    """
    📋 COMPREHENSIVE PROCESS GUARDRAILS SYSTEM
    
    Manages:
    1. Code ownership assignments and accountability
    2. Architecture preservation rules and enforcement
    3. Change approval workflows and governance
    4. Team structure and expertise distribution
    5. Continuous reliability improvement processes
    """
    
    def __init__(self, config_path: str = "process_guardrails_config.json"):
        self.config_path = config_path
        self.ownerships: dict[str, CodeOwnership] = {}
        self.architecture_rules: dict[str, ArchitectureRule] = {}
        self.pending_reviews: dict[str, ChangeReview] = {}
        
        # Initialize with default configuration
        self._initialize_default_configuration()
        self._load_configuration()
    
    def _initialize_default_configuration(self) -> None:
        """Initialize default process guardrails configuration"""
        
        # Define code ownership for critical components
        default_ownerships = {
            "expense_routing": CodeOwnership(
                component="expense_routing",
                primary_owners=["reliability_team"],
                secondary_owners=["backend_team"],
                reviewers=["architect", "senior_engineer"],
                description="Expense save operations and routing logic",
                risk_level=ChangeRisk.CRITICAL,
                approval_requirements=[
                    ApprovalRequirement.ARCHITECT_REVIEW,
                    ApprovalRequirement.PRIMARY_OWNER,
                    ApprovalRequirement.RELIABILITY_TEAM
                ],
                files_patterns=[
                    "backend_assistant.py",
                    "handlers/expense.py",
                    "utils/single_writer_guard.py",
                    "routes_expense.py"
                ],
                last_updated=time.strftime('%Y-%m-%d %H:%M:%S')
            ),
            
            "authentication_system": CodeOwnership(
                component="authentication_system",
                primary_owners=["security_team"],
                secondary_owners=["backend_team"],
                reviewers=["security_architect", "senior_engineer"],
                description="User authentication and session management",
                risk_level=ChangeRisk.CRITICAL,
                approval_requirements=[
                    ApprovalRequirement.ARCHITECT_REVIEW,
                    ApprovalRequirement.PRIMARY_OWNER
                ],
                files_patterns=[
                    "routes_auth.py",
                    "utils/auth_*.py",
                    "models.py"
                ],
                last_updated=time.strftime('%Y-%m-%d %H:%M:%S')
            ),
            
            "database_schema": CodeOwnership(
                component="database_schema",
                primary_owners=["database_team"],
                secondary_owners=["backend_team"],
                reviewers=["database_architect", "reliability_team"],
                description="Database schemas and migrations",
                risk_level=ChangeRisk.HIGH,
                approval_requirements=[
                    ApprovalRequirement.ARCHITECT_REVIEW,
                    ApprovalRequirement.PRIMARY_OWNER
                ],
                files_patterns=[
                    "models.py",
                    "migrations/*",
                    "utils/*db*.py"
                ],
                last_updated=time.strftime('%Y-%m-%d %H:%M:%S')
            ),
            
            "reliability_framework": CodeOwnership(
                component="reliability_framework",
                primary_owners=["reliability_team"],
                secondary_owners=["senior_engineer"],
                reviewers=["architect", "reliability_lead"],
                description="100% reliability framework components",
                risk_level=ChangeRisk.CRITICAL,
                approval_requirements=[
                    ApprovalRequirement.ARCHITECT_REVIEW,
                    ApprovalRequirement.RELIABILITY_TEAM
                ],
                files_patterns=[
                    "utils/unbreakable_invariants.py",
                    "utils/production_smoke_tests.py",
                    "utils/ghost_elimination.py",
                    "utils/slo_monitoring.py",
                    "utils/single_writer_guard.py",
                    "utils/ci_invariant_enforcement.py"
                ],
                last_updated=time.strftime('%Y-%m-%d %H:%M:%S')
            ),
            
            "frontend_ui": CodeOwnership(
                component="frontend_ui",
                primary_owners=["frontend_team"],
                secondary_owners=["fullstack_engineer"],
                reviewers=["ui_designer", "senior_engineer"],
                description="User interface and PWA components",
                risk_level=ChangeRisk.MEDIUM,
                approval_requirements=[
                    ApprovalRequirement.PRIMARY_OWNER
                ],
                files_patterns=[
                    "static/*",
                    "templates/*",
                    "routes_ui.py"
                ],
                last_updated=time.strftime('%Y-%m-%d %H:%M:%S')
            )
        }
        
        # Define architecture preservation rules
        default_architecture_rules = {
            "single_writer_enforcement": ArchitectureRule(
                rule_id="single_writer_enforcement",
                title="Single Writer Pattern Enforcement",
                description="All expense operations must use backend_assistant.add_expense",
                enforced_by="automated",
                violation_severity="critical",
                detection_pattern=r"(create_expense|save_expense|upsert_expense)\s*\(",
                remediation_action="Replace with backend_assistant.add_expense call",
                last_checked=time.strftime('%Y-%m-%d %H:%M:%S')
            ),
            
            "allowed_sources_integrity": ArchitectureRule(
                rule_id="allowed_sources_integrity",
                title="ALLOWED_SOURCES Integrity",
                description="Only 'chat' source allowed in web-only architecture",
                enforced_by="automated",
                violation_severity="critical",
                detection_pattern=r"['\"](?:messenger|form|sms)['\"]",
                remediation_action="Remove deprecated source references",
                last_checked=time.strftime('%Y-%m-%d %H:%M:%S')
            ),
            
            "authentication_requirement": ArchitectureRule(
                rule_id="authentication_requirement",
                title="Authentication Required for Expense Operations",
                description="All expense endpoints must require authentication",
                enforced_by="manual",
                violation_severity="critical",
                detection_pattern=r"@app\.route.*expense.*methods.*POST",
                remediation_action="Add @login_required decorator",
                last_checked=time.strftime('%Y-%m-%d %H:%M:%S')
            ),
            
            "database_migrations_safety": ArchitectureRule(
                rule_id="database_migrations_safety",
                title="Database Migration Safety",
                description="Use Alembic for all schema changes, never manual SQL",
                enforced_by="manual",
                violation_severity="high",
                detection_pattern=r"ALTER TABLE|DROP TABLE|CREATE TABLE",
                remediation_action="Use Alembic migration instead of manual SQL",
                last_checked=time.strftime('%Y-%m-%d %H:%M:%S')
            ),
            
            "error_handling_consistency": ArchitectureRule(
                rule_id="error_handling_consistency",
                title="Consistent Error Handling",
                description="Use standardized error response format",
                enforced_by="both",
                violation_severity="medium",
                detection_pattern=r"return.*error.*[^{]",
                remediation_action="Use standardized error response format",
                last_checked=time.strftime('%Y-%m-%d %H:%M:%S')
            )
        }
        
        self.ownerships = default_ownerships
        self.architecture_rules = default_architecture_rules
    
    def _load_configuration(self) -> None:
        """Load configuration from file if it exists"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path) as f:
                    config = json.load(f)
                    
                # Load ownerships
                if 'ownerships' in config:
                    for component, data in config['ownerships'].items():
                        self.ownerships[component] = CodeOwnership(**data)
                
                # Load architecture rules
                if 'architecture_rules' in config:
                    for rule_id, data in config['architecture_rules'].items():
                        self.architecture_rules[rule_id] = ArchitectureRule(**data)
                        
                logger.info(f"Loaded process guardrails configuration from {self.config_path}")
                
            except Exception as e:
                logger.warning(f"Failed to load configuration: {e}")
    
    def save_configuration(self) -> None:
        """Save current configuration to file"""
        try:
            config = {
                'ownerships': {k: asdict(v) for k, v in self.ownerships.items()},
                'architecture_rules': {k: asdict(v) for k, v in self.architecture_rules.items()},
                'last_updated': time.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
                
            logger.info(f"Saved process guardrails configuration to {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
    
    def get_file_owners(self, file_path: str) -> dict[str, Any]:
        """
        🏠 GET FILE OWNERS
        Determine ownership for a specific file
        """
        file_ownership = {
            'primary_owners': [],
            'secondary_owners': [],
            'reviewers': [],
            'component': None,
            'risk_level': ChangeRisk.LOW,
            'approval_requirements': []
        }
        
        for component, ownership in self.ownerships.items():
            for pattern in ownership.files_patterns:
                # Convert glob pattern to regex
                regex_pattern = pattern.replace('*', '.*').replace('?', '.')
                if re.search(regex_pattern, file_path):
                    file_ownership['primary_owners'].extend(ownership.primary_owners)
                    file_ownership['secondary_owners'].extend(ownership.secondary_owners)
                    file_ownership['reviewers'].extend(ownership.reviewers)
                    file_ownership['component'] = component
                    file_ownership['risk_level'] = ownership.risk_level
                    file_ownership['approval_requirements'] = ownership.approval_requirements
                    break
        
        # Remove duplicates
        file_ownership['primary_owners'] = list(set(file_ownership['primary_owners']))
        file_ownership['secondary_owners'] = list(set(file_ownership['secondary_owners']))
        file_ownership['reviewers'] = list(set(file_ownership['reviewers']))
        
        return file_ownership
    
    def validate_architecture_rules(self, directory: str = '.') -> dict[str, Any]:
        """
        🏗️ VALIDATE ARCHITECTURE RULES
        Check codebase against architecture preservation rules
        """
        violations = []
        
        for rule_id, rule in self.architecture_rules.items():
            if rule.enforced_by in ['automated', 'both']:
                rule_violations = self._check_architecture_rule(rule, directory)
                violations.extend(rule_violations)
        
        return {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_violations': len(violations),
            'violations_by_severity': {
                'critical': len([v for v in violations if v['severity'] == 'critical']),
                'high': len([v for v in violations if v['severity'] == 'high']),
                'medium': len([v for v in violations if v['severity'] == 'medium'])
            },
            'violations': violations,
            'rules_checked': len([r for r in self.architecture_rules.values() if r.enforced_by in ['automated', 'both']])
        }
    
    def _check_architecture_rule(self, rule: ArchitectureRule, directory: str) -> list[dict[str, Any]]:
        """Check a single architecture rule against the codebase"""
        violations = []
        
        try:
            for py_file in Path(directory).glob('**/*.py'):
                if self._should_skip_file(py_file):
                    continue
                
                with open(py_file, encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                for i, line in enumerate(lines, 1):
                    if re.search(rule.detection_pattern, line):
                        violations.append({
                            'rule_id': rule.rule_id,
                            'rule_title': rule.title,
                            'file': str(py_file),
                            'line': i,
                            'content': line.strip(),
                            'severity': rule.violation_severity,
                            'remediation': rule.remediation_action
                        })
                        
        except Exception as e:
            logger.warning(f"Error checking rule {rule.rule_id}: {e}")
        
        return violations
    
    def _should_skip_file(self, file_path: Path) -> bool:
        """Determine if file should be skipped during rule checking"""
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
    
    def create_change_review(self, component: str, submitter: str, 
                           files_changed: list[str]) -> str:
        """
        📝 CREATE CHANGE REVIEW
        Initiate a change review process for modifications
        """
        change_id = f"change_{int(time.time())}"
        
        # Determine risk level based on files changed
        risk_level = ChangeRisk.LOW
        ownership = None
        
        for file_path in files_changed:
            file_ownership = self.get_file_owners(file_path)
            if file_ownership['component'] and file_ownership['component'] in self.ownerships:
                component_ownership = self.ownerships[file_ownership['component']]
                if component_ownership.risk_level.value > risk_level.value:
                    risk_level = component_ownership.risk_level
                    ownership = component_ownership
        
        # Determine required reviewers
        reviewers_required = []
        if ownership:
            for requirement in ownership.approval_requirements:
                if requirement == ApprovalRequirement.PRIMARY_OWNER:
                    reviewers_required.extend(ownership.primary_owners)
                elif requirement == ApprovalRequirement.SECONDARY_OWNER:
                    reviewers_required.extend(ownership.secondary_owners)
                elif requirement == ApprovalRequirement.ARCHITECT_REVIEW:
                    reviewers_required.extend(ownership.reviewers)
        
        # Remove duplicates and submitter
        reviewers_required = list(set(reviewers_required))
        if submitter in reviewers_required:
            reviewers_required.remove(submitter)
        
        change_review = ChangeReview(
            change_id=change_id,
            component=component,
            risk_level=risk_level,
            submitter=submitter,
            reviewers_required=reviewers_required,
            reviewers_approved=[],
            status="pending",
            created_at=time.strftime('%Y-%m-%d %H:%M:%S'),
            files_changed=files_changed
        )
        
        self.pending_reviews[change_id] = change_review
        
        logger.info(f"Created change review {change_id} for {component}")
        return change_id
    
    def get_governance_dashboard(self) -> dict[str, Any]:
        """
        📊 GET GOVERNANCE DASHBOARD
        Comprehensive governance and process dashboard
        """
        # Architecture rule violations
        violations_report = self.validate_architecture_rules()
        
        # Code ownership coverage
        ownership_coverage = {
            'total_components': len(self.ownerships),
            'critical_components': len([o for o in self.ownerships.values() if o.risk_level == ChangeRisk.CRITICAL]),
            'components_by_risk': {
                'critical': len([o for o in self.ownerships.values() if o.risk_level == ChangeRisk.CRITICAL]),
                'high': len([o for o in self.ownerships.values() if o.risk_level == ChangeRisk.HIGH]),
                'medium': len([o for o in self.ownerships.values() if o.risk_level == ChangeRisk.MEDIUM]),
                'low': len([o for o in self.ownerships.values() if o.risk_level == ChangeRisk.LOW])
            }
        }
        
        # Pending reviews
        reviews_summary = {
            'total_pending': len(self.pending_reviews),
            'by_risk_level': {
                'critical': len([r for r in self.pending_reviews.values() if r.risk_level == ChangeRisk.CRITICAL]),
                'high': len([r for r in self.pending_reviews.values() if r.risk_level == ChangeRisk.HIGH]),
                'medium': len([r for r in self.pending_reviews.values() if r.risk_level == ChangeRisk.MEDIUM]),
                'low': len([r for r in self.pending_reviews.values() if r.risk_level == ChangeRisk.LOW])
            }
        }
        
        # Team structure analysis
        all_owners = set()
        all_reviewers = set()
        for ownership in self.ownerships.values():
            all_owners.update(ownership.primary_owners)
            all_owners.update(ownership.secondary_owners)
            all_reviewers.update(ownership.reviewers)
        
        team_structure = {
            'total_owners': len(all_owners),
            'total_reviewers': len(all_reviewers),
            'owner_list': list(all_owners),
            'reviewer_list': list(all_reviewers)
        }
        
        return {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'architecture_violations': violations_report,
            'ownership_coverage': ownership_coverage,
            'pending_reviews': reviews_summary,
            'team_structure': team_structure,
            'governance_health': 'HEALTHY' if violations_report['total_violations'] == 0 else 'NEEDS_ATTENTION'
        }
    
    def get_reliability_governance_report(self) -> dict[str, Any]:
        """
        🎯 GET RELIABILITY GOVERNANCE REPORT
        Specialized report for 100% reliability framework governance
        """
        reliability_components = [
            'expense_routing',
            'authentication_system', 
            'reliability_framework'
        ]
        
        reliability_status = {}
        for component in reliability_components:
            if component in self.ownerships:
                ownership = self.ownerships[component]
                reliability_status[component] = {
                    'risk_level': ownership.risk_level.value,
                    'primary_owners': ownership.primary_owners,
                    'approval_requirements': [req.value for req in ownership.approval_requirements],
                    'files_count': len(ownership.files_patterns)
                }
        
        # Check critical architecture rules
        critical_rules = [
            'single_writer_enforcement',
            'allowed_sources_integrity',
            'authentication_requirement'
        ]
        
        critical_violations = []
        for rule_id in critical_rules:
            if rule_id in self.architecture_rules:
                rule = self.architecture_rules[rule_id]
                rule_violations = self._check_architecture_rule(rule, '.')
                critical_violations.extend(rule_violations)
        
        return {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'reliability_components': reliability_status,
            'critical_violations': critical_violations,
            'critical_violations_count': len(critical_violations),
            'reliability_health': 'PROTECTED' if len(critical_violations) == 0 else 'AT_RISK',
            'framework_integrity': '100%' if len(critical_violations) == 0 else f'{max(0, 100 - len(critical_violations) * 10)}%'
        }

# Global process guardrails instance
process_guardrails = ProcessGuardrails()

def get_file_ownership(file_path: str) -> dict[str, Any]:
    """
    🏠 GLOBAL ENTRY POINT
    Get ownership information for a specific file
    """
    return process_guardrails.get_file_owners(file_path)

def validate_architecture() -> dict[str, Any]:
    """
    🏗️ GLOBAL ENTRY POINT
    Validate architecture rules across the codebase
    """
    return process_guardrails.validate_architecture_rules()

def get_governance_summary() -> dict[str, Any]:
    """
    📊 GLOBAL ENTRY POINT
    Get comprehensive governance dashboard
    """
    return process_guardrails.get_governance_dashboard()

def get_reliability_governance() -> dict[str, Any]:
    """
    🎯 GLOBAL ENTRY POINT
    Get reliability-focused governance report
    """
    return process_guardrails.get_reliability_governance_report()