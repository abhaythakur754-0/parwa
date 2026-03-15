import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from backend.app.main import app
from backend.app.dependencies import get_db

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to PARWA API"}

@patch("backend.app.main.check_db_connection", new_callable=AsyncMock)
def test_health_check_success(mock_check):
    mock_check.return_value = True
    # We override the dependency to avoid real DB calls during this unit test
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["database"] == "connected"
    
    app.dependency_overrides.clear()

@patch("backend.app.main.check_db_connection", new_callable=AsyncMock)
def test_health_check_unhealthy(mock_check):
    mock_check.return_value = False
    app.dependency_overrides[get_db] = lambda: AsyncMock()
    
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "unhealthy"
    
    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_get_db_dependency():
    from backend.app.dependencies import get_db
    from unittest.mock import MagicMock
    
    # Mocking AsyncSessionLocal
    with patch("backend.app.dependencies.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_session.__aenter__.return_value = mock_session
        mock_session_factory.return_value = mock_session
        
        generator = get_db()
        # Iterate over the async generator
        async for session in generator:
            assert session == mock_session
            
        # Ensure commit and close were called
        assert mock_session.commit.called
        assert mock_session.close.called
