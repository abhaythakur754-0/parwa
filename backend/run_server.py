"""
Jarvis API — Entry Point

Start the FastAPI server on port 8100.

Usage:
    cd /home/z/my-project/parwa/backend
    python run_server.py

Or with auto-reload (dev):
    python run_server.py        # reload=True by default
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.api.main:app",
        host="0.0.0.0",
        port=8100,
        reload=True,
        log_level="info",
    )
