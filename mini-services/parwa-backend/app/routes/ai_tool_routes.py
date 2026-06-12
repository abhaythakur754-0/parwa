"""AI tool selection routes for PARWA backend (PHASE 14 - GAP 14)."""
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, IntegrationCredential, FAQEntry, KBDocument
from app.auth import get_current_user
from app.services.tool_selector import select_tools, build_system_prompt

router = APIRouter(prefix="/api/v1/ai-tools", tags=["ai-tools"])


# --- Pydantic Models ---

class SelectToolRequest(BaseModel):
    ticket_intent: str


# --- Routes ---

@router.get("/available")
def get_available_tools(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get available tools for tenant from connected integrations + KB + FAQ."""
    tools = []

    # Tools from connected integrations
    creds = (
        db.query(IntegrationCredential)
        .filter(
            IntegrationCredential.tenant_id == current_user.tenant_id,
            IntegrationCredential.status == "active",
        )
        .all()
    )

    for cred in creds:
        tools.append({
            "id": f"integration_{cred.integration_id}",
            "name": cred.integration_name,
            "type": "external_integration",
            "integration_id": cred.integration_id,
            "description": f"Access {cred.integration_name} via API",
            "auth_type": cred.auth_type,
        })

    # Tools from FAQ
    faq_count = (
        db.query(FAQEntry)
        .filter(FAQEntry.tenant_id == current_user.tenant_id)
        .count()
    )
    if faq_count > 0:
        tools.append({
            "id": "faq_search",
            "name": "FAQ Search",
            "type": "faq",
            "description": f"Search through {faq_count} FAQ entries to find answers",
        })

    # Tools from Knowledge Base
    kb_docs = (
        db.query(KBDocument)
        .filter(
            KBDocument.tenant_id == current_user.tenant_id,
            KBDocument.status == "ready",
        )
        .all()
    )
    if kb_docs:
        total_chunks = sum(d.chunk_count for d in kb_docs)
        tools.append({
            "id": "kb_search",
            "name": "Knowledge Base Search",
            "type": "kb",
            "description": f"Search through {len(kb_docs)} documents ({total_chunks} chunks)",
        })

    # RAG tool always available if KB exists
    if kb_docs:
        tools.append({
            "id": "rag_response",
            "name": "RAG Response Generator",
            "type": "rag",
            "description": "Generate AI responses using retrieved knowledge base context",
        })

    return {
        "tools": tools,
        "total": len(tools),
    }


@router.post("/select")
def select_tool_for_intent(
    req: SelectToolRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Select the best tool for a given ticket intent."""
    tools = select_tools(
        tenant_id=current_user.tenant_id,
        ticket_intent=req.ticket_intent,
        db=db,
    )

    return {
        "ticket_intent": req.ticket_intent,
        "selected_tools": tools,
        "tool_count": len(tools),
    }


@router.get("/prompt")
def get_system_prompt(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get generated system prompt for tenant with dynamic tool injection."""
    prompt = build_system_prompt(
        tenant_id=current_user.tenant_id,
        db=db,
    )

    return {
        "system_prompt": prompt,
        "generated_at": __import__("datetime").datetime.utcnow().isoformat(),
    }
