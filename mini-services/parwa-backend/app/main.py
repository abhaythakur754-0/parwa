"""PARWA FastAPI Application - AI-powered customer support platform backend."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes.auth_routes import router as auth_router
from app.routes.onboarding_routes import router as onboarding_router
from app.routes.integration_routes import router as integration_router
from app.routes.api_key_routes import router as api_key_router
from app.routes.audit_routes import router as audit_router
from app.routes.variant_routes import router as variant_router
from app.routes.ai_tool_routes import router as ai_tool_router

app = FastAPI(
    title="PARWA Backend",
    description="AI-powered customer support platform backend",
    version="1.0.0",
)

# CORS - allow localhost:3000 for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router)
app.include_router(onboarding_router)
app.include_router(integration_router)
app.include_router(api_key_router)
app.include_router(audit_router)
app.include_router(variant_router)
app.include_router(ai_tool_router)


@app.on_event("startup")
def startup():
    """Initialize database tables on startup."""
    init_db()


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "service": "PARWA Backend",
        "version": "1.0.0",
        "health": "/health",
        "docs": "/docs",
    }
