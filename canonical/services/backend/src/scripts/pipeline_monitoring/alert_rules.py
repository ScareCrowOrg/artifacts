"""
Alert Rules Engine for Pipeline Monitoring.

Implements configurable alert rules with thresholds, conditions, and actions.
Addresses Sprint 4 requirement for intelligent, configurable alerting.

Technical naming follows Rule 4.3 (English for all technical identifiers).
"""

import json
import logging
import time
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
from dataclasses import dataclass, asdict, field
from pathlib import Path

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class RuleCondition(Enum):
    """Rule condition types"""
    GREATER_THAN = "gt"
    LESS_THAN = "lt"
    EQUALS = "eq"
    NOT_EQUALS = "ne"
    GREATER_EQUAL = "ge"
    LESS_EQUAL = "le"
    CONTAINS = "contains"


class RuleMetric(Enum):
    """Metrics that can trigger alerts"""
    # Component health
    COMPONENT_HEALTH = "component_health"
    PREREQUISITE_STATUS = "prerequisite_status"
    
    # Performance
    LATENCY_P95 = "latency_p95_ms"
    LATENCY_P99 = "latency_p99_ms"
    GENERATION_TIME = "avg_generation_time_ms"
    
    # Resources
    OPFS_QUOTA_PERCENT = "opfs_quota_used_percent"
    MEMORY_USAGE_PERCENT = "memory_usage_percent"
    
    # Operations
    CONSECUTIVE_FAILURES = "consecutive_failures"
    SUCCESS_RATE = "success_rate"
    ACTIVE_GENERATIONS = "active_generations"


@dataclass
class AlertRule:
    """
    Alert rule definition.
    
    Attributes:
        id: Unique rule identifier
        name: Human-readable rule name
        metric: Metric to monitor
        condition: Comparison condition
        threshold: Threshold value
        severity: Alert severity level
        enabled: Whether rule is active
        description: Rule description
        actions: List of action handlers to execute
    """
    id: str
    name: str
    metric: RuleMetric
    condition: RuleCondition
    threshold: Any
    severity: AlertSeverity
    enabled: bool = True
    description: str = ""
    actions: List[str] = field(default_factory=list)  # More idiomatic for dataclasses
    
    def __post_init__(self):
        # Convert enums if they're strings
        if isinstance(self.metric, str):
            self.metric = RuleMetric(self.metric)
        if isinstance(self.condition, str):
            self.condition = RuleCondition(self.condition)
        if isinstance(self.severity, str):
            self.severity = AlertSeverity(self.severity)


@dataclass
class AlertEvent:
    """
    Alert event triggered by a rule.
    
    Attributes:
        rule_id: ID of the rule that triggered
        rule_name: Name of the rule
        severity: Alert severity
        metric: Metric that triggered
        current_value: Current metric value
        threshold: Rule threshold
        message: Alert message
        timestamp: When alert was triggered
    """
    rule_id: str
    rule_name: str
    severity: AlertSeverity
    metric: RuleMetric
    current_value: Any
    threshold: Any
    message: str
    timestamp: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        result = asdict(self)
        result['severity'] = self.severity.value
        result['metric'] = self.metric.value
        return result


class AlertRulesEngine:
    """
    Alert Rules Engine for monitoring system.
    
    Evaluates configured rules against current metrics and triggers alerts.
    Supports rule persistence, dynamic reloading, and action execution.
    """
    
    def __init__(self, rules_file: Optional[str] = None):
        """
        Initialize alert rules engine.
        
        Args:
            rules_file: Path to JSON rules configuration file
        """
        self.rules: Dict[str, AlertRule] = {}
        self.rules_file = rules_file or "/tmp/alert_rules.json"
        self.action_handlers: Dict[str, Callable] = {}
        self._load_rules()
    
    def _load_rules(self) -> None:
        """Load rules from configuration file"""
        try:
            rules_path = Path(self.rules_file)
            if rules_path.exists():
                with open(rules_path, 'r') as f:
                    rules_data = json.load(f)
                    for rule_dict in rules_data.get('rules', []):
                        rule = AlertRule(**rule_dict)
                        self.rules[rule.id] = rule
                logger.info(f"Loaded {len(self.rules)} alert rules from {self.rules_file}")
            else:
                # Initialize with default rules
                self._create_default_rules()
                self._save_rules()
        except Exception as e:
            logger.error(f"Failed to load alert rules: {e}")
            self._create_default_rules()
    
    def _create_default_rules(self) -> None:
        """Create default alert rules"""
        default_rules = [
            AlertRule(
                id="high_latency_p95",
                name="High Latency (P95)",
                metric=RuleMetric.LATENCY_P95,
                condition=RuleCondition.GREATER_THAN,
                threshold=500,
                severity=AlertSeverity.WARNING,
                description="Alert when P95 latency exceeds 500ms",
                actions=["log", "notify"]
            ),
            AlertRule(
                id="critical_latency_p95",
                name="Critical Latency (P95)",
                metric=RuleMetric.LATENCY_P95,
                condition=RuleCondition.GREATER_THAN,
                threshold=1000,
                severity=AlertSeverity.CRITICAL,
                description="Alert when P95 latency exceeds 1000ms",
                actions=["log", "notify", "page"]
            ),
            AlertRule(
                id="opfs_quota_warning",
                name="OPFS Quota Warning",
                metric=RuleMetric.OPFS_QUOTA_PERCENT,
                condition=RuleCondition.GREATER_THAN,
                threshold=75,
                severity=AlertSeverity.WARNING,
                description="Alert when OPFS usage exceeds 75%",
                actions=["log", "notify"]
            ),
            AlertRule(
                id="opfs_quota_critical",
                name="OPFS Quota Critical",
                metric=RuleMetric.OPFS_QUOTA_PERCENT,
                condition=RuleCondition.GREATER_THAN,
                threshold=90,
                severity=AlertSeverity.CRITICAL,
                description="Alert when OPFS usage exceeds 90%",
                actions=["log", "notify", "cleanup"]
            ),
            AlertRule(
                id="low_success_rate",
                name="Low Generation Success Rate",
                metric=RuleMetric.SUCCESS_RATE,
                condition=RuleCondition.LESS_THAN,
                threshold=80,
                severity=AlertSeverity.WARNING,
                description="Alert when generation success rate drops below 80%",
                actions=["log", "notify"]
            ),
            AlertRule(
                id="consecutive_failures",
                name="Multiple Consecutive Failures",
                metric=RuleMetric.CONSECUTIVE_FAILURES,
                condition=RuleCondition.GREATER_EQUAL,
                threshold=3,
                severity=AlertSeverity.CRITICAL,
                description="Alert when 3+ consecutive failures occur",
                actions=["log", "notify", "page"]
            ),
            AlertRule(
                id="component_unhealthy",
                name="Component Unhealthy",
                metric=RuleMetric.COMPONENT_HEALTH,
                condition=RuleCondition.EQUALS,
                threshold="unhealthy",
                severity=AlertSeverity.CRITICAL,
                description="Alert when any component becomes unhealthy",
                actions=["log", "notify"]
            )
        ]
        
        for rule in default_rules:
            self.rules[rule.id] = rule
    
    def _save_rules(self) -> None:
        """Save rules to configuration file"""
        try:
            rules_data = {
                'rules': [
                    {
                        'id': rule.id,
                        'name': rule.name,
                        'metric': rule.metric.value,
                        'condition': rule.condition.value,
                        'threshold': rule.threshold,
                        'severity': rule.severity.value,
                        'enabled': rule.enabled,
                        'description': rule.description,
                        'actions': rule.actions
                    }
                    for rule in self.rules.values()
                ]
            }
            
            rules_path = Path(self.rules_file)
            rules_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(rules_path, 'w') as f:
                json.dump(rules_data, f, indent=2)
            
            logger.info(f"Saved {len(self.rules)} alert rules to {self.rules_file}")
        except Exception as e:
            logger.error(f"Failed to save alert rules: {e}")
    
    def register_action_handler(self, action_name: str, handler: Callable) -> None:
        """
        Register an action handler.
        
        Args:
            action_name: Name of the action
            handler: Callable to execute for this action
        """
        self.action_handlers[action_name] = handler
        logger.debug(f"Registered action handler: {action_name}")
    
    def add_rule(self, rule: AlertRule) -> None:
        """
        Add or update an alert rule.
        
        Args:
            rule: Alert rule to add
        """
        self.rules[rule.id] = rule
        self._save_rules()
        logger.info(f"Added/updated rule: {rule.id}")
    
    def remove_rule(self, rule_id: str) -> bool:
        """
        Remove an alert rule.
        
        Args:
            rule_id: ID of rule to remove
            
        Returns:
            True if removed, False if not found
        """
        if rule_id in self.rules:
            del self.rules[rule_id]
            self._save_rules()
            logger.info(f"Removed rule: {rule_id}")
            return True
        return False
    
    def enable_rule(self, rule_id: str, enabled: bool = True) -> bool:
        """
        Enable or disable a rule.
        
        Args:
            rule_id: ID of rule to modify
            enabled: Whether to enable the rule
            
        Returns:
            True if modified, False if not found
        """
        if rule_id in self.rules:
            self.rules[rule_id].enabled = enabled
            self._save_rules()
            logger.info(f"Rule {rule_id} {'enabled' if enabled else 'disabled'}")
            return True
        return False
    
    def get_rule(self, rule_id: str) -> Optional[AlertRule]:
        """Get a rule by ID"""
        return self.rules.get(rule_id)
    
    def list_rules(self, enabled_only: bool = False) -> List[AlertRule]:
        """
        List all rules.
        
        Args:
            enabled_only: If True, only return enabled rules
            
        Returns:
            List of alert rules
        """
        rules = list(self.rules.values())
        if enabled_only:
            rules = [r for r in rules if r.enabled]
        return rules
    
    def evaluate_rule(self, rule: AlertRule, current_value: Any) -> Optional[AlertEvent]:
        """
        Evaluate a single rule against current value.
        
        Args:
            rule: Rule to evaluate
            current_value: Current metric value
            
        Returns:
            AlertEvent if rule triggered, None otherwise
        """
        if not rule.enabled:
            return None
        
        triggered = False
        
        # Evaluate condition
        if rule.condition == RuleCondition.GREATER_THAN:
            triggered = current_value > rule.threshold
        elif rule.condition == RuleCondition.LESS_THAN:
            triggered = current_value < rule.threshold
        elif rule.condition == RuleCondition.EQUALS:
            triggered = current_value == rule.threshold
        elif rule.condition == RuleCondition.NOT_EQUALS:
            triggered = current_value != rule.threshold
        elif rule.condition == RuleCondition.GREATER_EQUAL:
            triggered = current_value >= rule.threshold
        elif rule.condition == RuleCondition.LESS_EQUAL:
            triggered = current_value <= rule.threshold
        elif rule.condition == RuleCondition.CONTAINS:
            triggered = rule.threshold in str(current_value)
        
        if triggered:
            message = (
                f"{rule.name}: {rule.metric.value} is {current_value} "
                f"(threshold: {rule.threshold})"
            )
            
            event = AlertEvent(
                rule_id=rule.id,
                rule_name=rule.name,
                severity=rule.severity,
                metric=rule.metric,
                current_value=current_value,
                threshold=rule.threshold,
                message=message,
                timestamp=time.time()
            )
            
            # Execute actions
            self._execute_actions(rule, event)
            
            return event
        
        return None
    
    def evaluate_metrics(self, metrics: Dict[str, Any]) -> List[AlertEvent]:
        """
        Evaluate all rules against current metrics.
        
        Args:
            metrics: Dictionary of current metric values
            
        Returns:
            List of triggered alert events
        """
        alerts = []
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            # Get current value for this rule's metric
            current_value = metrics.get(rule.metric.value)
            
            if current_value is not None:
                alert = self.evaluate_rule(rule, current_value)
                if alert:
                    alerts.append(alert)
        
        return alerts
    
    def _execute_actions(self, rule: AlertRule, event: AlertEvent) -> None:
        """
        Execute actions for triggered alert.
        
        Args:
            rule: Rule that triggered
            event: Alert event details
        """
        for action_name in rule.actions:
            handler = self.action_handlers.get(action_name)
            if handler:
                try:
                    handler(event)
                    logger.debug(f"Executed action: {action_name} for rule: {rule.id}")
                except Exception as e:
                    logger.error(f"Failed to execute action {action_name}: {e}")
            else:
                logger.warning(f"No handler registered for action: {action_name}")
    
    def reload_rules(self) -> None:
        """Reload rules from configuration file"""
        self.rules.clear()
        self._load_rules()
        logger.info("Reloaded alert rules")


# Singleton instance
_alert_rules_engine: Optional[AlertRulesEngine] = None


def get_alert_rules_engine(rules_file: Optional[str] = None) -> AlertRulesEngine:
    """
    Get or create the singleton alert rules engine.
    
    Args:
        rules_file: Path to rules configuration file
        
    Returns:
        AlertRulesEngine instance
    """
    global _alert_rules_engine
    
    if _alert_rules_engine is None:
        _alert_rules_engine = AlertRulesEngine(rules_file)
    
    return _alert_rules_engine
