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
# Phase 15: Data Flow & Error Architecture
from app.routes.dataflow_routes import router as dataflow_router
# Phase 16: Missing routes
from app.routes.webhook_routes import router as webhook_router
from app.routes.notification_routes import router as notification_router
from app.routes.kb_routes import router as kb_router
from app.routes.industry_routes import router as industry_router
from app.routes.verification_routes import router as verification_router

app = FastAPI(
    title="PARWA Backend",
    description="AI-powered customer support platform backend",
    version="2.0.0",
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

# Register routers — Phase 9-14
app.include_router(auth_router)
app.include_router(onboarding_router)
app.include_router(integration_router)
app.include_router(api_key_router)
app.include_router(audit_router)
app.include_router(variant_router)
app.include_router(ai_tool_router)

# Phase 15: Data Flow & Error Architecture (GAP 13)
app.include_router(dataflow_router)

# Phase 16: Missing routes (Gaps A, 7, 10, 12, End-to-End Proof)
app.include_router(webhook_router)
app.include_router(notification_router)
app.include_router(kb_router)
app.include_router(industry_router)
app.include_router(verification_router)


@app.on_event("startup")
def startup():
    """Initialize database tables on startup."""
    init_db()
    # Create Phase 16 webhook tables
    from app.routes.webhook_routes import WebhookEvent, WebhookConfig
    from app.database import Base, engine
    Base.metadata.create_all(bind=engine)


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "version": "2.0.0"}


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "service": "PARWA Backend",
        "version": "2.0.0",
        "health": "/health",
        "docs": "/docs",
        "phases": {
            "9": "Audit Trail & Action Logging",
            "10": "Rate Limiting & Error Handling",
            "13": "Global API Key System",
            "14": "AI Tool Selection & Multi-Variant Routing",
            "15": "Data Flow & Error Architecture",
            "16": "End-to-End Proof",
        },
    }
