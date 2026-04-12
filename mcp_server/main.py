"""
PARWA MCP Server — Production Entry Point

MCP (Model Context Protocol) server for external AI tool integrations.
Provides a standardized interface for connecting external AI models
and tools to the PARWA customer support platform.

Health check endpoint: GET /health
"""

import os
import sys

# Ensure project root is on Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("ENVIRONMENT", "production")

from fastapi import FastAPI

app = FastAPI(title="PARWA MCP Server", version="0.1.0")


@app.get("/health")
async def health_check():
    """Health check endpoint for Docker container monitoring."""
    return {"status": "healthy", "service": "parwa-mcp"}


@app.get("/")
async def root():
    return {"service": "PARWA MCP Server", "version": "0.1.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "mcp_server.main:app",
        host="0.0.0.0",
        port=8080,
        log_level="info",
    )
