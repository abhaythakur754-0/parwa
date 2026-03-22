import pytest
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from shared.utils.error_handlers import (
    setup_error_handlers,
    NotFoundError,
    ValidationError,
    AuthError,
    RateLimitError,
    ParwaError
)

app = FastAPI()
setup_error_handlers(app)
router = APIRouter()

class SampleModel(BaseModel):
    name: str

@router.get("/not-found")
async def trigger_not_found():
    raise NotFoundError(message="User not found", details={"user_id": 123})

@router.get("/auth-error")
async def trigger_auth_error():
    raise AuthError()

@router.get("/rate-limit")
async def trigger_rate_limit():
    raise RateLimitError(details={"retry_after": 60})

@router.get("/http-error")
async def trigger_http_error():
    raise HTTPException(status_code=403, detail="Forbidden act")

@router.get("/unhandled-error")
async def trigger_unhandled():
    raise RuntimeError("Something exploded fundamentally")

@router.post("/validation-error")
async def trigger_validation(data: SampleModel):
    return data

app.include_router(router)

client = TestClient(app, raise_server_exceptions=False)

def test_not_found_error():
    response = client.get("/not-found")
    assert response.status_code == 404
    data = response.json()
    assert data["detail"] == "User not found"
    assert data["error_type"] == "NotFoundError"
    assert data["extra"] == {"user_id": 123}

def test_auth_error():
    response = client.get("/auth-error")
    assert response.status_code == 401
    data = response.json()
    assert data["detail"] == "Authentication failed"
    assert data["error_type"] == "AuthError"
    
def test_rate_limit_error():
    response = client.get("/rate-limit")
    assert response.status_code == 429
    data = response.json()
    assert data["detail"] == "Rate limit exceeded"
    assert data["error_type"] == "RateLimitError"
    assert data["extra"] == {"retry_after": 60}

def test_http_exception():
    response = client.get("/http-error")
    assert response.status_code == 403
    data = response.json()
    assert data["detail"] == "Forbidden act"
    assert data["error_type"] == "HTTPException"

def test_unhandled_exception():
    response = client.get("/unhandled-error")
    assert response.status_code == 500
    data = response.json()
    assert data["detail"] == "Internal server error"
    assert data["error_type"] == "InternalServerError"

def test_validation_error():
    response = client.post("/validation-error", json={"wrong_key": "value"})
    assert response.status_code == 422
    data = response.json()
    assert data["detail"] == "Input validation failed"
    assert "errors" in data
    assert data["error_type"] == "RequestValidationError"
