"""
Tests for Alert Rules Engine.

Tests rule evaluation, action execution, persistence, and configuration management.
"""

import json
import pytest
import tempfile
from pathlib import Path
from scripts.pipeline_monitoring.alert_rules import (
    AlertRulesEngine,
    AlertRule,
    AlertEvent,
    AlertSeverity,
    RuleCondition,
    RuleMetric,
    get_alert_rules_engine
)


class TestAlertRule:
    """Tests for AlertRule dataclass"""
    
    def test_alert_rule_creation(self):
        """Test creating an alert rule"""
        rule = AlertRule(
            id="test_rule",
            name="Test Rule",
            metric=RuleMetric.LATENCY_P95,
            condition=RuleCondition.GREATER_THAN,
            threshold=500,
            severity=AlertSeverity.WARNING,
            description="Test description"
        )
        
        assert rule.id == "test_rule"
        assert rule.name == "Test Rule"
        assert rule.metric == RuleMetric.LATENCY_P95
        assert rule.condition == RuleCondition.GREATER_THAN
        assert rule.threshold == 500
        assert rule.severity == AlertSeverity.WARNING
        assert rule.enabled is True
        assert rule.actions == []
    
    def test_alert_rule_with_actions(self):
        """Test creating rule with actions"""
        rule = AlertRule(
            id="test",
            name="Test",
            metric=RuleMetric.OPFS_QUOTA_PERCENT,
            condition=RuleCondition.GREATER_THAN,
            threshold=90,
            severity=AlertSeverity.CRITICAL,
            actions=["log", "notify", "cleanup"]
        )
        
        assert rule.actions == ["log", "notify", "cleanup"]
    
    def test_alert_rule_string_enum_conversion(self):
        """Test that string values are converted to enums"""
        rule = AlertRule(
            id="test",
            name="Test",
            metric="latency_p95_ms",
            condition="gt",
            threshold=500,
            severity="warning"
        )
        
        assert rule.metric == RuleMetric.LATENCY_P95
        assert rule.condition == RuleCondition.GREATER_THAN
        assert rule.severity == AlertSeverity.WARNING


class TestAlertEvent:
    """Tests for AlertEvent dataclass"""
    
    def test_alert_event_creation(self):
        """Test creating an alert event"""
        event = AlertEvent(
            rule_id="test_rule",
            rule_name="Test Rule",
            severity=AlertSeverity.WARNING,
            metric=RuleMetric.LATENCY_P95,
            current_value=600,
            threshold=500,
            message="Latency exceeded threshold",
            timestamp=1234567890.0
        )
        
        assert event.rule_id == "test_rule"
        assert event.severity == AlertSeverity.WARNING
        assert event.current_value == 600
        assert event.threshold == 500
    
    def test_alert_event_to_dict(self):
        """Test converting event to dictionary"""
        event = AlertEvent(
            rule_id="test_rule",
            rule_name="Test Rule",
            severity=AlertSeverity.CRITICAL,
            metric=RuleMetric.OPFS_QUOTA_PERCENT,
            current_value=95,
            threshold=90,
            message="OPFS quota exceeded",
            timestamp=1234567890.0
        )
        
        result = event.to_dict()
        
        assert result['rule_id'] == "test_rule"
        assert result['severity'] == "critical"
        assert result['metric'] == "opfs_quota_used_percent"
        assert result['current_value'] == 95


class TestAlertRulesEngine:
    """Tests for AlertRulesEngine"""
    
    @pytest.fixture
    def temp_rules_file(self):
        """Create a temporary rules file"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            temp_path = f.name
        yield temp_path
        Path(temp_path).unlink(missing_ok=True)
    
    @pytest.fixture
    def engine(self, temp_rules_file):
        """Create engine with temporary rules file"""
        return AlertRulesEngine(rules_file=temp_rules_file)
    
    def test_engine_initialization(self, engine):
        """Test engine initializes with default rules"""
        assert len(engine.rules) > 0
        assert "high_latency_p95" in engine.rules
        assert "opfs_quota_warning" in engine.rules
    
    def test_add_rule(self, engine):
        """Test adding a new rule"""
        rule = AlertRule(
            id="custom_rule",
            name="Custom Rule",
            metric=RuleMetric.SUCCESS_RATE,
            condition=RuleCondition.LESS_THAN,
            threshold=50,
            severity=AlertSeverity.CRITICAL
        )
        
        engine.add_rule(rule)
        
        assert "custom_rule" in engine.rules
        assert engine.get_rule("custom_rule") == rule
    
    def test_remove_rule(self, engine):
        """Test removing a rule"""
        rule_id = list(engine.rules.keys())[0]
        
        result = engine.remove_rule(rule_id)
        
        assert result is True
        assert rule_id not in engine.rules
    
    def test_remove_nonexistent_rule(self, engine):
        """Test removing rule that doesn't exist"""
        result = engine.remove_rule("nonexistent")
        assert result is False
    
    def test_enable_disable_rule(self, engine):
        """Test enabling/disabling rules"""
        rule_id = list(engine.rules.keys())[0]
        
        # Disable
        result = engine.enable_rule(rule_id, False)
        assert result is True
        assert engine.rules[rule_id].enabled is False
        
        # Enable
        result = engine.enable_rule(rule_id, True)
        assert result is True
        assert engine.rules[rule_id].enabled is True
    
    def test_list_rules(self, engine):
        """Test listing all rules"""
        all_rules = engine.list_rules()
        assert len(all_rules) > 0
        
        # Disable one rule
        rule_id = list(engine.rules.keys())[0]
        engine.enable_rule(rule_id, False)
        
        enabled_rules = engine.list_rules(enabled_only=True)
        assert len(enabled_rules) < len(all_rules)
    
    def test_evaluate_rule_greater_than_triggered(self, engine):
        """Test rule evaluation with greater than condition (triggered)"""
        rule = AlertRule(
            id="test",
            name="Test",
            metric=RuleMetric.LATENCY_P95,
            condition=RuleCondition.GREATER_THAN,
            threshold=500,
            severity=AlertSeverity.WARNING
        )
        
        event = engine.evaluate_rule(rule, 600)
        
        assert event is not None
        assert event.rule_id == "test"
        assert event.current_value == 600
        assert event.threshold == 500
    
    def test_evaluate_rule_greater_than_not_triggered(self, engine):
        """Test rule evaluation with greater than condition (not triggered)"""
        rule = AlertRule(
            id="test",
            name="Test",
            metric=RuleMetric.LATENCY_P95,
            condition=RuleCondition.GREATER_THAN,
            threshold=500,
            severity=AlertSeverity.WARNING
        )
        
        event = engine.evaluate_rule(rule, 400)
        
        assert event is None
    
    def test_evaluate_rule_less_than(self, engine):
        """Test rule evaluation with less than condition"""
        rule = AlertRule(
            id="test",
            name="Test",
            metric=RuleMetric.SUCCESS_RATE,
            condition=RuleCondition.LESS_THAN,
            threshold=80,
            severity=AlertSeverity.WARNING
        )
        
        event = engine.evaluate_rule(rule, 70)
        assert event is not None
        
        event = engine.evaluate_rule(rule, 90)
        assert event is None
    
    def test_evaluate_rule_equals(self, engine):
        """Test rule evaluation with equals condition"""
        rule = AlertRule(
            id="test",
            name="Test",
            metric=RuleMetric.COMPONENT_HEALTH,
            condition=RuleCondition.EQUALS,
            threshold="unhealthy",
            severity=AlertSeverity.CRITICAL
        )
        
        event = engine.evaluate_rule(rule, "unhealthy")
        assert event is not None
        
        event = engine.evaluate_rule(rule, "healthy")
        assert event is None
    
    def test_evaluate_rule_disabled(self, engine):
        """Test that disabled rules don't trigger"""
        rule = AlertRule(
            id="test",
            name="Test",
            metric=RuleMetric.LATENCY_P95,
            condition=RuleCondition.GREATER_THAN,
            threshold=500,
            severity=AlertSeverity.WARNING,
            enabled=False
        )
        
        event = engine.evaluate_rule(rule, 600)
        
        assert event is None
    
    def test_evaluate_metrics(self, engine):
        """Test evaluating multiple metrics"""
        metrics = {
            "latency_p95_ms": 600,  # Should trigger
            "opfs_quota_used_percent": 80,  # Should trigger
            "success_rate": 95  # Should not trigger
        }
        
        events = engine.evaluate_metrics(metrics)
        
        assert len(events) > 0
        # Should have at least latency and opfs alerts
        assert any(e.metric == RuleMetric.LATENCY_P95 for e in events)
    
    def test_action_handler_registration(self, engine):
        """Test registering action handlers"""
        called = []
        
        def test_handler(event):
            called.append(event)
        
        engine.register_action_handler("test_action", test_handler)
        
        rule = AlertRule(
            id="test",
            name="Test",
            metric=RuleMetric.LATENCY_P95,
            condition=RuleCondition.GREATER_THAN,
            threshold=500,
            severity=AlertSeverity.WARNING,
            actions=["test_action"]
        )
        
        engine.evaluate_rule(rule, 600)
        
        assert len(called) == 1
        assert called[0].rule_id == "test"
    
    def test_rules_persistence(self, temp_rules_file):
        """Test that rules are saved and loaded correctly"""
        # Create engine and add custom rule
        engine1 = AlertRulesEngine(rules_file=temp_rules_file)
        
        custom_rule = AlertRule(
            id="persistent_rule",
            name="Persistent Rule",
            metric=RuleMetric.MEMORY_USAGE_PERCENT,
            condition=RuleCondition.GREATER_THAN,
            threshold=80,
            severity=AlertSeverity.WARNING
        )
        
        engine1.add_rule(custom_rule)
        
        # Create new engine instance - should load saved rules
        engine2 = AlertRulesEngine(rules_file=temp_rules_file)
        
        assert "persistent_rule" in engine2.rules
        loaded_rule = engine2.get_rule("persistent_rule")
        assert loaded_rule.name == "Persistent Rule"
        assert loaded_rule.threshold == 80
    
    def test_reload_rules(self, engine, temp_rules_file):
        """Test reloading rules from file"""
        # Add a rule
        rule = AlertRule(
            id="reload_test",
            name="Reload Test",
            metric=RuleMetric.LATENCY_P95,
            condition=RuleCondition.GREATER_THAN,
            threshold=1000,
            severity=AlertSeverity.CRITICAL
        )
        engine.add_rule(rule)
        
        # Modify the file directly
        with open(temp_rules_file, 'r') as f:
            data = json.load(f)
        
        data['rules'][0]['threshold'] = 2000
        
        with open(temp_rules_file, 'w') as f:
            json.dump(data, f)
        
        # Reload rules
        engine.reload_rules()
        
        # Check threshold was updated
        reloaded_rule = engine.get_rule(data['rules'][0]['id'])
        assert reloaded_rule.threshold == 2000
    
    def test_get_alert_rules_engine_singleton(self, temp_rules_file):
        """Test that get_alert_rules_engine returns singleton"""
        # Reset singleton
        import scripts.pipeline_monitoring.alert_rules as alert_rules_module
        alert_rules_module._alert_rules_engine = None
        
        engine1 = get_alert_rules_engine(temp_rules_file)
        engine2 = get_alert_rules_engine(temp_rules_file)
        
        assert engine1 is engine2
