import uuid
import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from backend.app.middleware import ContextMiddleware

def create_test_app():
    app = FastAPI()
    app.add_middleware(ContextMiddleware)
    
    @app.get("/test-context")
    async def test_context(request: Request):
        return {
            "correlation_id": getattr(request.state, "correlation_id", None),
            "company_id": getattr(request.state, "company_id", None)
        }
        
    return app

client = TestClient(create_test_app())

class TestContextMiddleware:
    def test_adds_correlation_id(self):
        response = client.get("/test-context")
        assert response.status_code == 200
        assert "X-Correlation-ID" in response.headers
        assert response.json()["correlation_id"] == response.headers["X-Correlation-ID"]

    def test_preserves_existing_correlation_id(self):
        existing_id = str(uuid.uuid4())
        response = client.get("/test-context", headers={"X-Correlation-ID": existing_id})
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == existing_id
        assert response.json()["correlation_id"] == existing_id

    def test_extracts_company_id(self):
        test_company_id = "company_123"
        response = client.get("/test-context", headers={"X-Company-ID": test_company_id})
        assert response.status_code == 200
        assert response.json()["company_id"] == test_company_id

    def test_adds_process_time(self):
        response = client.get("/test-context")
        assert response.status_code == 200
        assert "X-Process-Time" in response.headers
