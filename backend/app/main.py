"""
PARWA Backend - FastAPI Application Entry Point.
"""
from fastapi import FastAPI, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.dependencies import get_db
from backend.app.database import check_db_connection
from shared.core_functions.logger import get_logger

logger = get_logger("main")

app = FastAPI(
    title="PARWA Backend",
    description="Multi-LLM Orchestration & Customer Support Automation",
    version="0.1.0",
)

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Verify application and database liveness.
    """
    is_db_up = await check_db_connection()
    
    if not is_db_up:
        logger.error("Health check failed: Database unreachable")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unhealthy", "database": "disconnected"}
        )
        
    return {
        "status": "ok",
        "database": "connected",
        "version": app.version
    }

@app.get("/")
async def root():
    return {"message": "Welcome to PARWA API"}
