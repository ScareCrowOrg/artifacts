"""
Unit tests for pipeline validator (backend scope only)

Tests validate the backend-only PipelineValidator which checks 10
backend-validatable prerequisites. Frontend/Extension/WASM prerequisites
are validated client-side via useFrontendHealthChecks composable.

Path to scripts is configured in tests/unit/scripts/conftest.py
"""

import pytest
import asyncio

from pipeline_monitoring.validator import (
    PipelineValidator,
    PrerequisiteStatus,
    Criticality,
    PrerequisiteResult
)


class TestPipelineValidator:
    """Test suite for PipelineValidator (backend scope only)"""
    
    @pytest.fixture
    def validator(self):
        """Create a validator instance"""
        return PipelineValidator()
    
    def test_validator_initialization(self, validator):
        """Test validator initializes with backend prerequisites only"""
        assert validator is not None
        assert len(validator.prerequisites) == 10, \
            "Backend validator should have 10 prerequisites (was 25 before refactor)"
    
    def test_prerequisites_structure(self, validator):
        """Test all prerequisites have required fields"""
        for prereq in validator.prerequisites:
            assert "id" in prereq
            assert "name" in prereq
            assert "category" in prereq
            assert "criticality" in prereq
            assert "validator" in prereq
            assert callable(prereq["validator"])
    
    def test_prerequisites_categories(self, validator):
        """Test prerequisites are properly categorized (backend categories only)"""
        categories = {
            "backend": 5,
            "infrastructure": 2,
            "configuration": 2,
            "runtime": 1  # Server-side system resources only
        }
        
        for category, expected_count in categories.items():
            prereqs = [p for p in validator.prerequisites if p["category"] == category]
            assert len(prereqs) == expected_count, \
                f"Expected {expected_count} {category} prerequisites, got {len(prereqs)}"
        
        # Verify frontend/extension/wasm categories removed
        frontend_categories = ["frontend", "extension", "wasm"]
        for category in frontend_categories:
            prereqs = [p for p in validator.prerequisites if p["category"] == category]
            assert len(prereqs) == 0, \
                f"Frontend category '{category}' should not be in backend validator"
    
    def test_prerequisites_criticality(self, validator):
        """Test prerequisites have correct criticality distribution (backend only)"""
        # Updated counts for backend-only prerequisites
        criticality_counts = {
            Criticality.CRITICAL: 4,  # cell_generation, llm, mongodb, env_vars
            Criticality.HIGH: 2,      # event_bus, redis
            Criticality.MEDIUM: 3,    # complexity, discovery, system_resources
            Criticality.LOW: 1        # feature_flags
        }
        
        for criticality, expected_count in criticality_counts.items():
            prereqs = [p for p in validator.prerequisites if p["criticality"] == criticality]
            assert len(prereqs) == expected_count, \
                f"Expected {expected_count} {criticality.value} prerequisites, got {len(prereqs)}"
    
    @pytest.mark.asyncio
    async def test_validate_all(self, validator):
        """Test validate_all returns results for all backend prerequisites"""
        results = await validator.validate_all()
        
        assert len(results) == 10, "Should return 10 backend prerequisites"
        assert all(isinstance(r, PrerequisiteResult) for r in results)
        
        # Verify no frontend/extension/wasm results
        categories = [r.category for r in results]
        assert "frontend" not in categories
        assert "extension" not in categories
        assert "wasm" not in categories
    
    @pytest.mark.asyncio
    async def test_validate_by_category_backend(self, validator):
        """Test validate_by_category for backend"""
        results = await validator.validate_by_category("backend")
        
        assert len(results) == 5
        assert all(r.category == "backend" for r in results)
    
    @pytest.mark.asyncio
    async def test_validate_by_category_infrastructure(self, validator):
        """Test validate_by_category for infrastructure (backend scope)"""
        results = await validator.validate_by_category("infrastructure")
        
        assert len(results) == 2, "Should have MongoDB and Redis only"
        assert all(r.category == "infrastructure" for r in results)
        
        # Verify specific infrastructure checks
        ids = [r.id for r in results]
        assert "infra.mongodb" in ids
        assert "infra.redis" in ids
        # Vault and auth_token removed (browser-side)
        assert "infra.vault" not in ids
        assert "infra.auth_token" not in ids
    
    @pytest.mark.asyncio
    async def test_validate_by_category_frontend_returns_empty(self, validator):
        """Test validate_by_category returns empty for frontend (moved to client-side)"""
        results = await validator.validate_by_category("frontend")
        
        assert len(results) == 0, "Frontend checks should be empty (moved to useFrontendHealthChecks)"
    
    @pytest.mark.asyncio
    async def test_validate_critical_only(self, validator):
        """Test validate_critical_only returns only critical prerequisites"""
        results = await validator.validate_critical_only()
        
        assert len(results) == 4, "Should have 4 critical backend prerequisites"
        assert all(r.criticality == Criticality.CRITICAL for r in results)
    
    @pytest.mark.asyncio
    async def test_prerequisite_result_structure(self, validator):
        """Test PrerequisiteResult has correct structure"""
        results = await validator.validate_all()
        
        for result in results:
            assert hasattr(result, "id")
            assert hasattr(result, "name")
            assert hasattr(result, "category")
            assert hasattr(result, "status")
            assert hasattr(result, "criticality")
            assert hasattr(result, "validation_method")
            assert hasattr(result, "monitoring_available")
            assert hasattr(result, "details")
            assert hasattr(result, "timestamp")
            assert isinstance(result.status, PrerequisiteStatus)
            assert isinstance(result.criticality, Criticality)
    
    @pytest.mark.asyncio
    async def test_prerequisite_result_to_dict(self, validator):
        """Test PrerequisiteResult can be converted to dict"""
        results = await validator.validate_all()
        
        for result in results:
            result_dict = result.to_dict()
            assert isinstance(result_dict, dict)
            assert "id" in result_dict
            assert "name" in result_dict
            assert "category" in result_dict
            assert "status" in result_dict
            assert "criticality" in result_dict
            assert isinstance(result_dict["status"], str)
            assert isinstance(result_dict["criticality"], str)
    
    @pytest.mark.asyncio
    async def test_check_environment_vars(self, validator, monkeypatch):
        """Test environment variables check"""
        # Set required environment variables
        monkeypatch.setenv("MONGODB_URI", "mongodb://localhost:27017")
        monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
        monkeypatch.setenv("JWT_SECRET", "test-secret")
        
        result = await validator._check_environment_vars()
        
        # With all required vars but no optional vars, should be DEGRADED
        assert result["status"] in [PrerequisiteStatus.HEALTHY, PrerequisiteStatus.DEGRADED]
        assert result["method"] == "env_check"
        assert result["details"]["configured"] is True
        
        # If DEGRADED, should have missing_optional_vars
        if result["status"] == PrerequisiteStatus.DEGRADED:
            assert "missing_optional_vars" in result["details"]
    
    @pytest.mark.asyncio
    async def test_check_environment_vars_missing(self, validator, monkeypatch):
        """Test environment variables check with missing vars"""
        # Clear environment variables
        monkeypatch.delenv("MONGODB_URI", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)
        monkeypatch.delenv("JWT_SECRET", raising=False)
        
        result = await validator._check_environment_vars()
        
        assert result["status"] == PrerequisiteStatus.UNHEALTHY
        assert result["method"] == "env_check"
        assert result["details"]["configured"] is False
        assert len(result["details"]["missing_required_vars"]) > 0
    
    @pytest.mark.asyncio
    async def test_check_system_resources(self, validator):
        """Test system resources check"""
        result = await validator._check_system_resources()
        
        assert "status" in result
        assert "method" in result
        assert result["method"] == "psutil"
        
        if result["status"] != PrerequisiteStatus.UNKNOWN:
            assert "details" in result
            assert "memory_available_mb" in result["details"]
            assert "disk_free_gb" in result["details"]
    
    @pytest.mark.asyncio
    async def test_backend_validators_dont_fail(self, validator):
        """Test backend validators don't raise exceptions"""
        backend_validators = [
            validator._check_cell_generation_service,
            validator._check_complexity_evaluation,
            validator._check_llm_integration,
            validator._check_discovery_system,
            validator._check_event_bus
        ]
        
        for check_func in backend_validators:
            result = await check_func()
            assert "status" in result
            assert "method" in result
            assert "details" in result
    
    @pytest.mark.asyncio
    async def test_validator_error_handling(self, validator):
        """Test validator handles errors gracefully"""
        # Create a validator that will fail
        async def failing_validator():
            raise ValueError("Test error")
        
        prereq = {
            "id": "test.failing",
            "name": "Test Failing",
            "category": "test",
            "criticality": Criticality.LOW,
            "validator": failing_validator
        }
        
        result = await validator._validate_prerequisite(prereq)
        
        assert result.status == PrerequisiteStatus.UNKNOWN
        assert result.validation_method == "error"
        assert "error" in result.details
    
    def test_prerequisite_status_enum(self):
        """Test PrerequisiteStatus enum values"""
        assert PrerequisiteStatus.HEALTHY.value == "healthy"
        assert PrerequisiteStatus.DEGRADED.value == "degraded"
        assert PrerequisiteStatus.UNHEALTHY.value == "unhealthy"
        assert PrerequisiteStatus.UNKNOWN.value == "unknown"
    
    def test_criticality_enum(self):
        """Test Criticality enum values"""
        assert Criticality.CRITICAL.value == "critical"
        assert Criticality.HIGH.value == "high"
        assert Criticality.MEDIUM.value == "medium"
        assert Criticality.LOW.value == "low"
    
    @pytest.mark.asyncio
    async def test_validate_all_parallel_execution(self, validator):
        """Test validate_all executes checks in parallel"""
        import time
        start_time = time.time()
        
        results = await validator.validate_all()
        
        elapsed_time = time.time() - start_time
        
        # If executed serially, would take much longer
        # Parallel execution should be relatively fast
        assert elapsed_time < 5.0  # Should complete in less than 5 seconds
        assert len(results) == 10, "Should return 10 backend prerequisites"
