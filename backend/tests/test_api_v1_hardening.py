"""
Improved API Tests for Agent SaaS Reload - Engine v5.0

This test suite validates:
- Health monitoring endpoints
- Request validation with Pydantic
- Tenant isolation and security
- Cycle lifecycle management
- Error handling and edge cases
"""

import pytest
import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

# Add backend path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from httpx import AsyncClient
from main import app
from core.auth import get_current_user


# ============================================================================
# Fixtures and Setup
# ============================================================================

@pytest.fixture
def mock_user():
    """Standard mock user for testing"""
    return {
        "user_id": "user-123",
        "organization_id": "org-A",
        "tenant_id": "org-A"
    }


@pytest.fixture
def client(mock_user):
    """Test client with mocked authentication"""
    def override_get_current_user():
        return mock_user
    
    app.dependency_overrides[get_current_user] = override_get_current_user
    
    with TestClient(app) as test_client:
        yield test_client
    
    # Cleanup
    app.dependency_overrides.clear()


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator for isolated testing"""
    with patch("main.orchestrator") as mock_orch:
        mock_orch.get_metrics = AsyncMock(return_value={
            "operational": True,
            "p50_latency": 1200,
            "p95_latency": 2400,
            "active_cycles": 5,
            "degraded": False,
            "last_cleanup_timestamp": "2026-02-28T12:00:00Z"
        })
        mock_orch.check_mcp_connection = AsyncMock(return_value=True)
        mock_orch.get_cycle_status = AsyncMock(return_value={
            "state": "running",
            "progress": 45,
            "started_at": "2026-02-28T12:00:00Z",
            "organization_id": "org-A" # Adjusted to match my main.py (organization_id)
        })
        mock_orch.mark_cycle_failed = AsyncMock()
        yield mock_orch


@pytest.fixture
def mock_verify_access():
    """Mock company access verification"""
    with patch("main.verify_company_access", new_callable=AsyncMock) as mock:
        mock.return_value = True
        yield mock


# ============================================================================
# Test Suite: Health Monitoring
# ============================================================================

class TestHealthEndpoint:
    """Tests for /api/v1/agents/health endpoint"""
    
    def test_health_returns_real_metrics(self, client, mock_orchestrator):
        """Health endpoint should return actual metrics, not hardcoded values"""
        response = client.get("/api/v1/agents/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify structure
        assert "status" in data
        assert data["status"] in ["healthy", "degraded", "unhealthy"]
        assert "p50_latency_ms" in data
        assert "p95_latency_ms" in data
        assert "active_cycles" in data
        assert "mcp_connected" in data
        assert "version" in data
        
        # Verify real metrics are returned
        assert data["p50_latency_ms"] == 1200
        assert data["active_cycles"] == 5
        assert data["mcp_connected"] is True
        
        print(f"   ✅ Health metrics OK: {data['status']}, "
              f"p50={data['p50_latency_ms']}ms, cycles={data['active_cycles']}")
    
    def test_health_handles_orchestrator_failure(self, client):
        """Health should degrade gracefully when orchestrator fails"""
        with patch("main.orchestrator.get_metrics", side_effect=Exception("Orchestrator down")):
            response = client.get("/api/v1/agents/health")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] in ["unhealthy", "degraded"]
            assert "error" in data or data.get("degradation_mode") is True
            
            print("   ✅ Health degrades gracefully on orchestrator failure")


# ============================================================================
# Test Suite: Input Validation
# ============================================================================

class TestInputValidation:
    """Tests for Pydantic request validation"""
    
    def test_valid_cycle_request(self, client, mock_verify_access):
        """Valid cycle request should be accepted"""
        response = client.post("/api/v1/agents/cycle", json={
            "company_id": "test-company-123",
            "instruccion": "Analizar el margen de beneficio del Q4",
            "mode": "fast"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "started"
        assert "cycle_id" in data
        assert "poll_url" in data
        
        print(f"   ✅ Valid request accepted: cycle_id={data['cycle_id']}")
    
    def test_instruction_too_short(self, client, mock_verify_access):
        """Instructions under minimum length should be rejected"""
        response = client.post("/api/v1/agents/cycle", json={
            "company_id": "test-co",
            "instruccion": "Hi",  # Only 2 chars, minimum is 10
            "mode": "fast"
        })
        
        assert response.status_code == 422
        error = response.json()
        assert "detail" in error
        
        print("   ✅ Short instruction rejected (validation passed)")
    
    def test_instruction_too_long(self, client, mock_verify_access):
        """Instructions exceeding maximum length should be rejected"""
        long_text = "A" * 5001  # Max is 5000
        response = client.post("/api/v1/agents/cycle", json={
            "company_id": "test-co",
            "instruccion": long_text,
            "mode": "fast"
        })
        
        assert response.status_code == 422
        print("   ✅ Long instruction rejected (validation passed)")
    
    def test_invalid_mode(self, client, mock_verify_access):
        """Invalid mode values should be rejected"""
        response = client.post("/api/v1/agents/cycle", json={
            "company_id": "test-co",
            "instruccion": "Analyze sales data",
            "mode": "super_fast"  # Invalid mode
        })
        
        assert response.status_code == 422
        print("   ✅ Invalid mode rejected")
    
    def test_missing_required_fields(self, client, mock_verify_access):
        """Missing required fields should be rejected"""
        response = client.post("/api/v1/agents/cycle", json={
            "mode": "fast"
            # Missing company_id and instruccion
        })
        
        assert response.status_code == 422
        print("   ✅ Missing required fields rejected")
    
    def test_invalid_company_id_format(self, client, mock_verify_access):
        """Invalid company_id format should be rejected"""
        response = client.post("/api/v1/agents/cycle", json={
            "company_id": "company with spaces!@#",  # Invalid characters
            "instruccion": "Analyze the data",
            "mode": "fast"
        })
        
        assert response.status_code == 422
        print("   ✅ Invalid company_id format rejected")
    
    def test_empty_company_id(self, client, mock_verify_access):
        """Empty company_id should be rejected"""
        response = client.post("/api/v1/agents/cycle", json={
            "company_id": "",
            "instruccion": "Analyze the data",
            "mode": "fast"
        })
        
        assert response.status_code == 422
        print("   ✅ Empty company_id rejected")


# ============================================================================
# Test Suite: Tenant Isolation
# ============================================================================

class TestTenantIsolation:
    """Tests for multi-tenant security and isolation"""
    
    def test_access_denied_to_other_tenant_company(self, client):
        """Users should not access companies from other tenants"""
        with patch("main.verify_company_access", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = False
            
            response = client.post("/api/v1/agents/cycle", json={
                "company_id": "other-tenant-company",
                "instruccion": "Analyze financial data",
                "mode": "fast"
            })
            
            assert response.status_code == 403
            assert "Access denied" in response.json()["detail"]
            
            print("   ✅ Cross-tenant access denied")
    
    def test_access_granted_to_own_tenant_company(self, client):
        """Users should access companies from their own tenant"""
        with patch("main.verify_company_access", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = True
            
            response = client.post("/api/v1/agents/cycle", json={
                "company_id": "own-tenant-company",
                "instruccion": "Analyze financial data",
                "mode": "fast"
            })
            
            assert response.status_code == 200
            print("   ✅ Own-tenant access granted")
    
    def test_cycle_status_requires_tenant_match(self, client, mock_orchestrator):
        """Cycle status should only be accessible to the owning tenant"""
        cycle_id = str(uuid4())
        
        # Setup: Cycle belongs to different tenant
        mock_orchestrator.get_cycle_status.return_value = {
            "state": "running",
            "organization_id": "org-B",  # Different from mock_user's org-A
            "progress": 50
        }
        
        response = client.get(f"/api/v1/agents/cycle/{cycle_id}/status")
        
        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]
        
        print("   ✅ Cross-tenant cycle access denied")
    
    def test_feedback_requires_tenant_match(self, client):
        """Feedback should only be submittable by the owning tenant"""
        with patch("main.supabase") as mock_supabase:
            # Mock Supabase to return an empty result (simulating no match due to tenant filter)
            mock_client = MagicMock()
            mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
            
            response = client.post("/api/v1/agents/feedback", json={
                "cycle_id": str(uuid4()),
                "agent_id": "agent-123",
                "approved": True,
                "comments": "Good work"
            })
            
            # Should verify tenant before allowing feedback
            assert response.status_code in [403, 404]
            
            print("   ✅ Cross-tenant feedback denied")


# ============================================================================
# Test Suite: Cycle Management
# ============================================================================

class TestCycleManagement:
    """Tests for cycle creation and status tracking"""
    
    def test_cycle_creation_returns_uuid(self, client, mock_verify_access):
        """Cycle creation should return a valid UUID"""
        response = client.post("/api/v1/agents/cycle", json={
            "company_id": "test-co",
            "instruccion": "Analyze Q4 performance metrics",
            "mode": "deep"
        })
        
        assert response.status_code == 200
        data = response.json()
        
        cycle_id = data["cycle_id"]
        # Verify it's a valid UUID format
        try:
            from uuid import UUID
            UUID(cycle_id)
            print(f"   ✅ Valid UUID returned: {cycle_id}")
        except ValueError:
            pytest.fail(f"Invalid UUID format: {cycle_id}")
    
    def test_cycle_status_not_found(self, client, mock_orchestrator):
        """Non-existent cycle should return 404"""
        mock_orchestrator.get_cycle_status.return_value = None
        
        fake_cycle_id = str(uuid4())
        response = client.get(f"/api/v1/agents/cycle/{fake_cycle_id}/status")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
        
        print("   ✅ Non-existent cycle returns 404")
    
    def test_cycle_status_includes_progress(self, client, mock_orchestrator):
        """Cycle status should include progress information"""
        cycle_id = str(uuid4())
        
        mock_orchestrator.get_cycle_status.return_value = {
            "state": "running",
            "progress": 65,
            "started_at": "2026-02-28T12:00:00Z",
            "organization_id": "org-A"
        }
        
        response = client.get(f"/api/v1/agents/cycle/{cycle_id}/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["state"] == "running"
        assert data["progress"] == 65
        assert "started_at" in data
        
        print(f"   ✅ Cycle status with progress: {data['progress']}%")
    
    def test_completed_cycle_includes_results(self, client, mock_orchestrator):
        """Completed cycles should include results"""
        cycle_id = str(uuid4())
        
        mock_orchestrator.get_cycle_status.return_value = {
            "state": "completed",
            "progress": 100,
            "started_at": "2026-02-28T12:00:00Z",
            "completed_at": "2026-02-28T12:15:00Z",
            "organization_id": "org-A",
            "results": {
                "insights": ["Revenue up 15%", "Cost down 8%"],
                "recommendations": ["Expand to new market"]
            }
        }
        
        response = client.get(f"/api/v1/agents/cycle/{cycle_id}/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["state"] == "completed"
        assert "results" in data
        assert data["results"] is not None
        
        print("   ✅ Completed cycle includes results")
    
    def test_failed_cycle_includes_error(self, client, mock_orchestrator):
        """Failed cycles should include error information"""
        cycle_id = str(uuid4())
        
        mock_orchestrator.get_cycle_status.return_value = {
            "state": "failed",
            "progress": 30,
            "started_at": "2026-02-28T12:00:00Z",
            "completed_at": "2026-02-28T12:05:00Z",
            "organization_id": "org-A",
            "error": "Database connection timeout"
        }
        
        response = client.get(f"/api/v1/agents/cycle/{cycle_id}/status")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["state"] == "failed"
        assert "error" in data
        assert data["error"] is not None
        
        print(f"   ✅ Failed cycle includes error: {data['error']}")


# ============================================================================
# Test Suite: Feedback System
# ============================================================================

class TestFeedbackSystem:
    """Tests for RLHF feedback endpoint"""
    
    def test_valid_feedback_submission(self, client):
        """Valid feedback should be accepted"""
        with patch("main.supabase") as mock_supabase:
            mock_update = mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute
            mock_update.return_value.data = [{"id": 1}]
            
            response = client.post("/api/v1/agents/feedback", json={
                "cycle_id": str(uuid4()),
                "agent_id": "agent-financial-analyst",
                "approved": True,
                "comments": "Excellent analysis of Q4 data"
            })
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            
            print("   ✅ Valid feedback accepted")
    
    def test_feedback_with_long_comments(self, client):
        """Feedback with excessively long comments should be rejected"""
        long_comment = "A" * 1001  # Max is 1000
        
        response = client.post("/api/v1/agents/feedback", json={
            "cycle_id": str(uuid4()),
            "agent_id": "agent-123",
            "approved": False,
            "comments": long_comment
        })
        
        assert response.status_code == 422
        print("   ✅ Long comments rejected")
    
    def test_feedback_for_nonexistent_decision(self, client):
        """Feedback for non-existent decision should return 404"""
        with patch("main.supabase") as mock_supabase:
             mock_update = mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute
             mock_update.return_value.data = []
            
             response = client.post("/api/v1/agents/feedback", json={
                "cycle_id": str(uuid4()),
                "agent_id": "nonexistent-agent",
                "approved": True
             })
            
             assert response.status_code == 404
             print("   ✅ Nonexistent decision returns 404")
    
    def test_feedback_without_comments(self, client):
        """Feedback without comments should be accepted"""
        with patch("main.supabase") as mock_supabase:
            mock_update = mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute
            mock_update.return_value.data = [{"id": 1}]
            
            response = client.post("/api/v1/agents/feedback", json={
                "cycle_id": str(uuid4()),
                "agent_id": "agent-123",
                "approved": False
                # No comments field
            })
            
            assert response.status_code == 200
            print("   ✅ Feedback without comments accepted")


# ============================================================================
# Test Suite: Error Handling
# ============================================================================

class TestErrorHandling:
    """Tests for error handling and edge cases"""
    
    def test_invalid_json_payload(self, client):
        """Invalid JSON should return 422"""
        response = client.post(
            "/api/v1/agents/cycle",
            content="this is not json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422
        print("   ✅ Invalid JSON rejected")
    
    def test_invalid_uuid_format_in_status(self, client):
        """Invalid UUID format should return 422"""
        response = client.get("/api/v1/agents/cycle/not-a-uuid/status")
        
        assert response.status_code == 422
        print("   ✅ Invalid UUID format rejected")
    
    def test_database_error_handling(self, client):
        """Database errors should return 500 with appropriate message"""
        with patch("main.supabase.table", side_effect=Exception("DB connection failed")):
            response = client.post("/api/v1/agents/feedback", json={
                "cycle_id": str(uuid4()),
                "agent_id": "agent-123",
                "approved": True
            })
            
            assert response.status_code == 500
            assert "error" in response.json()["detail"].lower()
            
            print("   ✅ Database errors handled gracefully")


# ============================================================================
# Test Suite: API Versioning
# ============================================================================

class TestAPIVersioning:
    """Tests for API versioning and routing"""
    
    def test_root_endpoint_returns_version_info(self, client):
        """Root endpoint should return API version information"""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "v1" in data
        print("   ✅ Root endpoint returns version info")
    
    def test_v1_prefix_routes_correctly(self, client, mock_verify_access):
        """API v1 routes should be accessible with /api/v1 prefix"""
        response = client.post("/api/v1/agents/cycle", json={
            "company_id": "test-co",
            "instruccion": "Test instruction for routing",
            "mode": "fast"
        })
        
        assert response.status_code == 200
        print("   ✅ V1 prefix routes correctly")


# ============================================================================
# Integration Test
# ============================================================================

class TestIntegration:
    """End-to-end integration tests"""
    
    def test_complete_cycle_workflow(self, client, mock_orchestrator, mock_verify_access):
        """Test complete workflow: create → poll → feedback"""
        # Step 1: Create cycle
        create_response = client.post("/api/v1/agents/cycle", json={
            "company_id": "integration-test-co",
            "instruccion": "Complete integration test workflow",
            "mode": "fast"
        })
        
        assert create_response.status_code == 200
        cycle_id = create_response.json()["cycle_id"]
        
        # Step 2: Poll status (running)
        mock_orchestrator.get_cycle_status.return_value = {
            "state": "running",
            "progress": 50,
            "started_at": "2026-02-28T12:00:00Z",
            "organization_id": "org-A"
        }
        
        status_response = client.get(f"/api/v1/agents/cycle/{cycle_id}/status")
        assert status_response.status_code == 200
        assert status_response.json()["state"] == "running"
        
        # Step 3: Poll status (completed)
        mock_orchestrator.get_cycle_status.return_value = {
            "state": "completed",
            "progress": 100,
            "started_at": "2026-02-28T12:00:00Z",
            "completed_at": "2026-02-28T12:10:00Z",
            "organization_id": "org-A",
            "results": {"insights": ["Test insight"]}
        }
        
        final_status = client.get(f"/api/v1/agents/cycle/{cycle_id}/status")
        assert final_status.status_code == 200
        assert final_status.json()["state"] == "completed"
        
        # Step 4: Submit feedback
        with patch("main.supabase") as mock_supabase:
            mock_update = mock_supabase.table.return_value.update.return_value.eq.return_value.eq.return_value.eq.return_value.execute
            mock_update.return_value.data = [{"id": 1}]
            
            feedback_response = client.post("/api/v1/agents/feedback", json={
                "cycle_id": cycle_id,
                "agent_id": "agent-integration",
                "approved": True,
                "comments": "Integration test successful"
            })
            
            assert feedback_response.status_code == 200
        
        print("   ✅ Complete workflow executed successfully")


# ============================================================================
# Main Test Runner (for standalone execution)
# ============================================================================

if __name__ == "__main__":
    print("\n" + "="*70)
    print("🧪 Running API Hardening Tests - Engine v5.0")
    print("="*70 + "\n")
    
    # Run with pytest
    pytest.main([
        __file__,
        "-v",  # Verbose
        "--tb=short",  # Short traceback format
        "-s",  # Show print statements
        "--color=yes"  # Colored output
    ])
