"""
PARWA CRM Analyzer Service

Analyzes connected CRM/integration data to recommend which additional 
integrations the company needs. Uses NVIDIA GLM 5.2 LLM for intelligent analysis.

Business Value:
- Reduces user confusion about which integrations to connect
- Increases activation rate (more integrations = more value)
- Personalized recommendations based on actual data patterns

BC-001: All operations scoped to company_id.
LLM: Groq llama-3.1-8b-instant (user-validated best model, ~1s/call)
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.integration_catalog import (
    CATALOG,
    IntegrationCategory,
    get_integration_by_key,
)
from app.services.integration_service import IntegrationService
from database.models.crm_analysis import CRMAnalysisResult

logger = logging.getLogger("crm_analyzer")


class CRMAnalyzerService:
    """Analyzes CRM data and recommends missing integrations."""

    def __init__(self, db: Session):
        self.db = db
        self.integration_service = IntegrationService(db)

    async def analyze_company_crm(
        self,
        company_id: str,
    ) -> Dict[str, Any]:
        """Main entry point: Analyze company's CRM and return recommendations.

        Steps:
        1. Get all connected integrations for this company
        2. Fetch sample data from each connected integration
        3. Analyze data patterns to detect business type and gaps
        4. Use LLM to generate personalized recommendations
        
        Returns:
            Dict with:
            - connected_integrations: list of currently connected
            - data_profile: summary of what data was found
            - recommendations: list of recommended integrations with reasons
            - analysis_summary: plain text explanation
        """
        logger.info("Starting CRM analysis for company %s", company_id)

        # Step 1: Get connected integrations
        connected = await self._get_connected_integrations(company_id)
        
        # Step 2: Gather data from each integration
        data_profile = await self._gather_data_from_integrations(company_id, connected)
        
        # Step 3: Detect patterns and gaps
        detected_gaps = await self._detect_gaps(data_profile, connected)
        
        # Step 4: Generate LLM-powered recommendations
        recommendations = await self._generate_recommendations(
            company_id=company_id,
            data_profile=data_profile,
            connected=connected,
            gaps=detected_gaps,
        )

        result = {
            "company_id": company_id,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
            "connected_integrations": connected,
            "data_profile": data_profile,
            "detected_gaps": detected_gaps,
            "recommendations": recommendations,
            "analysis_summary": self._build_summary(data_profile, recommendations),
        }

        # Save to database for persistence (onboarding → dashboard transition)
        saved_result = self._save_analysis_result(result)
        if saved_result:
            result["analysis_id"] = str(saved_result.id)
            result["is_saved"] = True
        else:
            result["is_saved"] = False

        logger.info("CRM analysis complete for company %s: %d recommendations (saved=%s)", 
                    company_id, len(recommendations), result["is_saved"])
        return result

    async def _get_connected_integrations(
        self, company_id: str
    ) -> List[Dict[str, Any]]:
        """Get list of active integrations for a company."""
        from database.models.integration import Integration

        rows = (
            self.db.query(Integration)
            .filter(
                Integration.company_id == company_id,
                Integration.status == "active",
            )
            .all()
        )

        connected = []
        for row in rows:
            catalog_entry = get_integration_by_key(row.integration_type)
            connected.append({
                "id": str(row.id),
                "type": row.integration_type,
                "name": row.name,
                "category": catalog_entry.category.value if catalog_entry else "unknown",
                "connected_at": row.created_at.isoformat() if row.created_at else None,
            })

        return connected

    async def _gather_data_from_integrations(
        self,
        company_id: str,
        connected: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Gather sample data from each connected integration."""
        profile = {
            "total_contacts": 0,
            "total_orders": 0,
            "total_deals": 0,
            "has_products": False,
            "has_shipping_addresses": False,
            "has_payment_data": False,
            "has_email_campaigns": False,
            "has_ticket_data": False,
            "industries_detected": [],
            "data_points": [],
        }

        for integration in connected:
            int_type = integration["type"]
            
            try:
                if int_type in ("hubspot", "salesforce", "pipedrive"):
                    crm_data = await self._fetch_crm_data(company_id, int_type)
                    profile["total_contacts"] += crm_data.get("contact_count", 0)
                    profile["total_deals"] += crm_data.get("deal_count", 0)
                    profile["has_products"] = profile["has_products"] or crm_data.get("has_products", False)
                    
                elif int_type in ("shopify", "woocommerce", "bigcommerce"):
                    ecommerce_data = await self._fetch_ecommerce_data(company_id, int_type)
                    profile["total_orders"] += ecommerce_data.get("order_count", 0)
                    profile["has_shipping_addresses"] = ecommerce_data.get("has_shipping_addresses", False)
                    profile["has_payment_data"] = profile.has_payment_data or ecommerce_data.get("has_payment_data", False)
                    profile["has_products"] = profile["has_products"] or ecommerce_data.get("has_products", False)
                    if ecommerce_data.get("industry"):
                        profile["industries_detected"].append("ecommerce")
                        
                elif int_type in ("stripe", "paddle", "paypal"):
                    payment_data = await self._fetch_payment_data(company_id, int_type)
                    profile["has_payment_data"] = True
                    profile["data_points"].append({
                        "source": int_type,
                        "type": "payment",
                        "count": payment_data.get("transaction_count", 0),
                    })
                    
                elif int_type in ("mailchimp", "klaviyo", "brevo"):
                    marketing_data = await self._fetch_marketing_data(company_id, int_type)
                    profile["has_email_campaigns"] = True
                    profile["data_points"].append({
                        "source": int_type,
                        "type": "marketing",
                        "subscriber_count": marketing_data.get("subscriber_count", 0),
                    })
                    
                elif int_type in ("zendesk", "freshdesk", "intercom", "gorgias"):
                    profile["has_ticket_data"] = True
                    
                elif int_type in ("shipstation", "aftership", "easypost", "fedex", "ups", "dhl"):
                    profile["has_shipping_addresses"] = True

            except Exception as e:
                logger.warning("Failed to gather data from %s: %s", int_type, str(e)[:100])
                profile["data_points"].append({
                    "source": int_type,
                    "error": str(e)[:200],
                })

        # Deduplicate industries
        profile["industries_detected"] = list(set(profile["industries_detected"]))
        return profile

    async def _fetch_crm_data(
        self, company_id: str, crm_type: str
    ) -> Dict[str, Any]:
        """Fetch data summary from CRM integrations."""
        import httpx

        creds = self.integration_service.get_credential_config(company_id, crm_type)
        if not creds:
            return {"contact_count": 0, "deal_count": 0, "has_products": False}

        try:
            if crm_type == "hubspot":
                base_url = "https://api.hubapi.com"
                headers = {"Authorization": f"Bearer {creds.get('api_key', '')}"}
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Get contacts count
                    contacts_resp = await client.get(
                        f"{base_url}/crm/v3/objects/contacts",
                        params={"limit": 1},
                        headers=headers,
                    )
                    contact_count = contacts_resp.json().get("total", 0) if contacts_resp.status_code == 200 else 0
                    
                    # Get deals count
                    deals_resp = await client.get(
                        f"{base_url}/crm/v3/objects/deals",
                        params={"limit": 1},
                        headers=headers,
                    )
                    deal_count = deals_resp.json().get("total", 0) if deals_resp.status_code == 200 else 0
                    
                    # Check for products
                    products_resp = await client.get(
                        f"{base_url}/crm/v3/objects/products",
                        params={"limit": 1},
                        headers=headers,
                    )
                    has_products = products_resp.status_code == 200 and products_resp.json().get("total", 0) > 0

                return {
                    "contact_count": contact_count,
                    "deal_count": deal_count,
                    "has_products": has_products,
                }

            elif crm_type == "shopify":
                return await self._fetch_shopify_summary(creds)

        except Exception as e:
            logger.warning("CRM data fetch failed for %s: %s", crm_type, e)

        return {"contact_count": 0, "deal_count": 0, "has_products": False}

    async def _fetch_ecommerce_data(
        self, company_id: str, eco_type: str
    ) -> Dict[str, Any]:
        """Fetch data summary from e-commerce integrations."""
        import httpx

        creds = self.integration_service.get_credential_config(company_id, eco_type)
        if not creds:
            return {"order_count": 0, "has_shipping_addresses": False, "has_payment_data": False, "has_products": False}

        try:
            if eco_type == "shopify":
                shopify_data = await self._fetch_shopify_summary(creds)
                return {
                    "order_count": shopify_data.get("order_count", 0),
                    "has_shipping_addresses": shopify_data.get("has_shipping_addresses", False),
                    "has_payment_data": True,  # Shopify always has payments
                    "has_products": shopify_data.get("has_products", False),
                    "industry": "ecommerce",
                }

        except Exception as e:
            logger.warning("E-commerce data fetch failed for %s: %s", eco_type, e)

        return {"order_count": 0, "has_shipping_addresses": False, "has_payment_data": False, "has_products": False}

    async def _fetch_shopify_summary(self, creds: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch summary data from Shopify store."""
        import httpx

        store_url = creds.get("store_url", "").rstrip("/")
        token = creds.get("access_token", "")
        
        if not store_url or not token:
            return {"order_count": 0, "has_shipping_addresses": False, "has_products": False}

        headers = {"X-Shopify-Access-Token": token}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get order count
            orders_resp = await client.get(
                f"{store_url}/admin/api/2024-01/orders/count.json",
                headers=headers,
            )
            order_count = orders_resp.json().get("count", 0) if orders_resp.status_code == 200 else 0
            
            # Get product count
            products_resp = await client.get(
                f"{store_url}/admin/api/2024-01/products/count.json",
                headers=headers,
            )
            has_products = products_resp.json().get("count", 0) > 0 if products_resp.status_code == 200 else False
            
            # Check recent orders for shipping addresses
            shipping_check = await client.get(
                f"{store_url}/admin/api/2024-01/orders.json?limit=5&status=any",
                headers=headers,
            )
            has_shipping = False
            if shipping_check.status_code == 200:
                orders = shipping_check.json().get("orders", [])
                has_shipping = any(o.get("shipping_address") for o in orders)

        return {
            "order_count": order_count,
            "has_shipping_addresses": has_shipping,
            "has_products": has_products,
        }

    async def _fetch_payment_data(
        self, company_id: str, payment_type: str
    ) -> Dict[str, Any]:
        """Fetch data summary from payment integrations."""
        import httpx

        creds = self.integration_service.get_credential_config(company_id, payment_type)
        if not creds:
            return {"transaction_count": 0}

        try:
            if payment_type == "stripe":
                api_key = creds.get("api_key", "")
                headers = {"Authorization": f"Bearer {api_key}"}
                
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Get charge count (simplified)
                    resp = await client.get(
                        "https://api.stripe.com/v1/charges?limit=1",
                        headers=headers,
                    )
                    # Stripe returns array, we just need to know there's data
                    has_data = resp.status_code == 200

                return {"transaction_count": 100 if has_data else 0}  # Simplified

        except Exception as e:
            logger.warning("Payment data fetch failed for %s: %s", payment_type, e)

        return {"transaction_count": 0}

    async def _fetch_marketing_data(
        self, company_id: str, marketing_type: str
    ) -> Dict[str, Any]:
        """Fetch data summary from marketing integrations."""
        import httpx

        creds = self.integration_service.get_credential_config(company_id, marketing_type)
        if not creds:
            return {"subscriber_count": 0}

        try:
            if marketing_type == "mailchimp":
                api_key = creds.get("api_key", "")
                # Extract DC from API key (xxx-us123)
                dc = ""
                if "-" in api_key:
                    parts = api_key.rsplit("-", 1)
                    if len(parts) == 2:
                        dc = parts[-1]
                
                if dc:
                    headers = {"Authorization": f"Bearer {api_key}"}
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        resp = await client.get(
                            f"https://{dc}.api.mailchimp.com/3.0/lists",
                            headers=headers,
                        )
                        if resp.status_code == 200:
                            lists = resp.json().get("lists", [])
                            total_subs = sum(l.get("stats", {}).get("member_count", 0) for l in lists)
                            return {"subscriber_count": total_subs}

        except Exception as e:
            logger.warning("Marketing data fetch failed for %s: %s", marketing_type, e)

        return {"subscriber_count": 0}

    async def _detect_gaps(
        self,
        data_profile: Dict[str, Any],
        connected: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Detect gaps between current setup and potential needs."""
        connected_types = {c["type"] for c in connected}
        gaps = []

        # Gap detection rules
        gap_rules = [
            {
                "id": "shipping_missing",
                "condition": data_profile.get("total_orders", 0) > 0 and not data_profile.get("has_shipping_addresses"),
                "category": "shipping",
                "severity": "high",
                "message": "You have orders but no shipping integration for tracking",
                "recommended": ["shipstation", "aftership", "easypost"],
            },
            {
                "id": "payment_missing",
                "condition": data_profile.get("has_products") and not data_profile.get("has_payment_data"),
                "category": "payments",
                "severity": "high",
                "message": "You sell products but no payment processor is connected",
                "recommended": ["stripe", "paddle"],
            },
            {
                "id": "marketing_missing",
                "condition": data_profile.get("total_contacts", 0) > 100 and not data_profile.get("has_email_campaigns"),
                "category": "marketing",
                "severity": "medium",
                "message": f"You have {data_profile.get('total_contacts', 0)} contacts but no email marketing tool",
                "recommended": ["mailchimp", "klaviyo", "brevo"],
            },
            {
                "id": "helpdesk_missing",
                "condition": data_profile.get("total_contacts", 0) > 50 and not data_profile.get("has_ticket_data"),
                "category": "helpdesk",
                "severity": "medium",
                "message": "Growing customer base but no dedicated helpdesk system",
                "recommended": ["zendesk", "freshdesk", "intercom", "gorgias"],
            },
            {
                "id": "analytics_missing",
                "condition": data_profile.get("total_orders", 0) > 10 or data_profile.get("total_contacts", 0) > 100,
                "category": "analytics",
                "severity": "low",
                "message": "Significant activity but no analytics integration for insights",
                "recommended": ["mixpanel", "amplitude", "google_analytics"],
            },
            {
                "id": "communication_missing",
                "condition": data_profile.get("total_contacts", 0) > 20,
                "category": "communication",
                "severity": "low",
                "message": "Team communication could be improved with Slack integration",
                "recommended": ["slack"],
            },
        ]

        for rule in gap_rules:
            if rule["condition"]:
                # Filter out already-connected recommendations
                available_recs = [r for r in rule["recommended"] if r not in connected_types]
                if available_recs:
                    gaps.append({
                        **rule,
                        "recommended": available_recs,
                    })

        return gaps

    async def _call_nvidia_glm(self, prompt: str, max_tokens: int = 800, temperature: float = 0.3) -> str:
        """Call Groq llama-3.1-8b-instant for CRM analysis.

        Previously called NVIDIA GLM-5.2 but that took ~58s/call (vs Groq's ~1s).
        User validation (2026-08-12): llama-3.1-8b gives best results for ALL
        pipeline tasks, including CRM analysis.

        Method name kept as _call_nvidia_glm for backward compat (callers
        unchanged). Only the underlying provider changed.
        """
        import httpx

        api_key = os.environ.get("GROQ_API_KEY", "")
        if not api_key:
            logger.warning("GROQ_API_KEY not set for CRM analysis")
            return ""

        messages = [
            {
                "role": "system",
                "content": "You are Parwa's intelligent integration advisor. You analyze business data and recommend specific third-party integrations that would improve their workflow. Always respond in valid JSON format."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]

        payload = {
            "model": "llama-3.1-8b-instant",  # Groq — user-validated best model
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )

            if r.status_code == 200:
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                usage = data.get("usage", {})
                logger.info(
                    "Groq CRM analysis complete: tokens=%s (prompt=%s, completion=%s)",
                    usage.get("total_tokens", "?"),
                    usage.get("prompt_tokens", "?"),
                    usage.get("completion_tokens", "?"),
                )
                return content.strip()
            else:
                logger.error("Groq API error %d: %s", r.status_code, r.text[:200])
                return ""

        except Exception as e:
            logger.error("Groq call failed: %s", str(e)[:200])
            return ""

    async def _generate_recommendations(
        self,
        company_id: str,
        data_profile: Dict[str, Any],
        connected: List[Dict[str, Any]],
        gaps: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Use Groq llama-3.1-8b to generate personalized integration recommendations."""

        # Build context for LLM
        connected_names = [c["name"] for c in connected]
        connected_types = [c["type"] for c in connected]

        prompt = f"""You are Parwa's integration advisor. Analyze this company's data and recommend specific integrations they need.

COMPANY DATA PROFILE:
- Total Contacts: {data_profile.get('total_contacts', 0)}
- Total Orders: {data_profile.get('total_orders', 0)}
- Total Deals: {data_profile.get('total_deals', 0)}
- Has Products: {data_profile.get('has_products', False)}
- Has Shipping Data: {data_profile.get('has_shipping_addresses', False)}
- Has Payment Data: {data_profile.get('has_payment_data', False)}
- Has Email Marketing: {data_profile.get('has_email_campaigns', False)}
- Has Helpdesk: {data_profile.get('has_ticket_data', False)}
- Detected Industries: {data_profile.get('industries_detected', ['unknown'])}
- Data Points: {json.dumps(data_profile.get('data_points', [])[:3], indent=2)}

CURRENTLY CONNECTED ({len(connected)}): {', '.join(connected_names) if connected_names else 'None'}

DETECTED GAPS ({len(gaps)}):
{chr(10).join(f'- {g["message"]} (severity: {g["severity"]})' for g in gaps)}

AVAILABLE INTEGRATIONS TO RECOMMEND FROM:
- Shipping: shipstation, aftership, easypost, fedex, ups, dhl
- Payments: stripe, paddle, paypal
- Marketing: mailchimp, klaviyo, brevo
- Helpdesk: zendesk, freshdesk, intercom, gorgias
- Analytics: mixpanel, amplitude, google_analytics
- Communication: slack, gmail
- Dev Tools: github, jira, linear, notion

Respond in EXACTLY this JSON format (no markdown, no extra text):
{{
  "recommendations": [
    {{
      "integration_key": "stripe",
      "name": "Stripe",
      "category": "payments",
      "priority": "high|medium|low",
      "reason": "One sentence why they specifically need this",
      "business_impact": "What business outcome this enables"
    }}
  ],
  "overall_assessment": "2-3 sentences about their integration health"
}}"""

        try:
            # Use NVIDIA GLM 5.2 directly (user's preferred LLM)
            response = await self._call_nvidia_glm(
                prompt=prompt,
                max_tokens=800,
                temperature=0.3,
            )

            # Parse LLM response
            # Try to extract JSON from response
            json_str = response.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            parsed = json.loads(json_str)
            recommendations = parsed.get("recommendations", [])

            # Enrich with catalog data
            enriched = []
            seen_keys = set()
            for rec in recommendations:
                key = rec.get("integration_key", "")
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                catalog_entry = get_integration_by_key(key)
                enriched.append({
                    "integration_key": key,
                    "name": rec.get("name", catalog_entry.name if catalog_entry else key),
                    "category": rec.get("category", catalog_entry.category.value if catalog_entry else "unknown"),
                    "priority": rec.get("priority", "medium"),
                    "reason": rec.get("reason", ""),
                    "business_impact": rec.get("business_impact", ""),
                    "icon_id": catalog_entry.icon_id if catalog_entry else "",
                    "color_gradient": catalog_entry.color_gradient if catalog_entry else "",
                    "already_connected": key in connected_types,
                })

            # Add any high-severity gaps that LLM might have missed
            for gap in gaps:
                if gap["severity"] == "high":
                    for rec_key in gap["recommended"]:
                        if rec_key not in seen_keys:
                            catalog_entry = get_integration_by_key(rec_key)
                            enriched.append({
                                "integration_key": rec_key,
                                "name": catalog_entry.name if catalog_entry else rec_key,
                                "category": gap.get("category", "unknown"),
                                "priority": "high",
                                "reason": gap.get("message", ""),
                                "business_impact": "Critical gap detected in your workflow",
                                "icon_id": catalog_entry.icon_id if catalog_entry else "",
                                "color_gradient": catalog_entry.color_gradient if catalog_entry else "",
                                "already_connected": rec_key in connected_types,
                            })
                            seen_keys.add(rec_key)

            return enriched[:8]  # Max 8 recommendations to avoid overwhelm

        except Exception as e:
            logger.error("LLM recommendation generation failed: %s", e)
            # Fallback: return gap-based recommendations without LLM
            return self._generate_fallback_recommendations(gaps, connected_types)

    def _generate_fallback_recommendations(
        self,
        gaps: List[Dict[str, Any]],
        connected_types: List[str],
    ) -> List[Dict[str, Any]]:
        """Generate basic recommendations when LLM fails."""
        fallback = []
        seen = set()

        for gap in gaps[:5]:  # Top 5 gaps only
            for key in gap.get("recommended", [])[:1]:  # Top rec per gap
                if key not in seen:
                    catalog_entry = get_integration_by_key(key)
                    fallback.append({
                        "integration_key": key,
                        "name": catalog_entry.name if catalog_entry else key,
                        "category": gap.get("category", "unknown"),
                        "priority": gap.get("severity", "medium"),
                        "reason": gap.get("message", ""),
                        "business_impact": "Recommended based on your data patterns",
                        "icon_id": catalog_entry.icon_id if catalog_entry else "",
                        "color_gradient": catalog_entry.color_gradient if catalog_entry else "",
                        "already_connected": key in connected_types,
                    })
                    seen.add(key)

        return fallback

    def _save_analysis_result(self, result: Dict[str, Any]) -> Optional[CRMAnalysisResult]:
        """Save analysis result to database for persistence."""
        try:
            # Check if recent analysis exists (avoid duplicates within 1 hour)
            from datetime import timedelta
            recent_cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
            
            existing = (
                self.db.query(CRMAnalysisResult)
                .filter(
                    CRMAnalysisResult.company_id == result["company_id"],
                    CRMAnalysisResult.analyzed_at >= recent_cutoff,
                )
                .first()
            )
            
            if existing:
                # Update existing record instead of creating duplicate
                existing.data_profile = result.get("data_profile", {})
                existing.connected_integrations = result.get("connected_integrations", [])
                existing.detected_gaps = result.get("detected_gaps", [])
                existing.recommendations = result.get("recommendations", [])
                existing.analysis_summary = result.get("analysis_summary", "")
                existing.updated_at = datetime.now(timezone.utc)
                self.db.commit()
                logger.info("Updated existing CRM analysis %s for company %s", 
                           existing.id[:8], result["company_id"])
                return existing
            
            # Create new record
            db_result = CRMAnalysisResult(
                company_id=result["company_id"],
                data_profile=result.get("data_profile", {}),
                connected_integrations=result.get("connected_integrations", []),
                detected_gaps=result.get("detected_gaps", []),
                recommendations=result.get("recommendations", []),
                analysis_summary=result.get("analysis_summary", ""),
                llm_model_used="llama-3.1-8b-instant",
            )
            
            self.db.add(db_result)
            self.db.commit()
            self.db.refresh(db_result)
            
            logger.info("Saved CRM analysis %s for company %s (%d recs)", 
                       db_result.id[:8], result["company_id"], 
                       len(result.get("recommendations", [])))
            return db_result
            
        except Exception as e:
            logger.error("Failed to save CRM analysis result: %s", e)
            self.db.rollback()
            return None

    def get_stored_analysis(
        self,
        company_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Retrieve most recent stored analysis for a company.
        
        Used by Dashboard to show onboarding-time recommendations.
        """
        try:
            result = (
                self.db.query(CRMAnalysisResult)
                .filter(CRMAnalysisResult.company_id == company_id)
                .order_by(CRMAnalysisResult.analyzed_at.desc())
                .first()
            )
            
            if not result:
                return None
            
            return {
                "analysis_id": str(result.id),
                "company_id": result.company_id,
                "analyzed_at": result.analyzed_at.isoformat() if result.analyzed_at else None,
                "connected_integrations": result.connected_integrations or [],
                "data_profile": result.data_profile or {},
                "detected_gaps": result.detected_gaps or [],
                "recommendations": result.recommendations or [],
                "analysis_summary": result.analysis_summary or "",
                "is_actioned": result.is_actioned,
                "actioned_at": result.actioned_at.isoformat() if result.actioned_at else None,
                "llm_model_used": result.llm_model_used or "",
                "llm_tokens_used": result.llm_tokens_used or 0,
                "is_stored": True,
            }
            
        except Exception as e:
            logger.error("Failed to retrieve stored CRM analysis: %s", e)
            return None

    def mark_recommendations_actioned(
        self,
        company_id: str,
        accepted_integration_keys: List[str],
    ) -> bool:
        """Mark that user acted on specific recommendations.
        
        Called when user connects an integration that was recommended.
        """
        try:
            result = (
                self.db.query(CRMAnalysisResult)
                .filter(CRMAnalysisResult.company_id == company_id)
                .order_by(CRMAnalysisResult.analyzed_at.desc())
                .first()
            )
            
            if not result:
                return False
            
            result.is_actioned = True
            result.actioned_at = datetime.now(timezone.utc)
            result.recommendations_accepted = accepted_integration_keys
            self.db.commit()
            
            logger.info("Marked CRM analysis %s as actioned with %d integrations", 
                       result.id[:8], len(accepted_integration_keys))
            return True
            
        except Exception as e:
            logger.error("Failed to mark CRM analysis as actioned: %s", e)
            self.db.rollback()
            return False

    def _build_summary(
        self,
        data_profile: Dict[str, Any],
        recommendations: List[Dict[str, Any]],
    ) -> str:
        """Build human-readable summary of the analysis."""
        high_priority = [r for r in recommendations if r.get("priority") == "high"]
        medium_priority = [r for r in recommendations if r.get("priority") == "medium"]

        parts = [
            f"Based on your data ({data_profile.get('total_contacts', 0)} contacts, "
            f"{data_profile.get('total_orders', 0)} orders), ",
        ]

        if high_priority:
            parts.append(f"we found {len(high_priority)} urgent integration(s) you should add: ")
            parts.append(", ".join(r["name"] for r in high_priority[:3]))
            if len(high_priority) > 3:
                parts.append(f", and {len(high_priority) - 3} more")
            parts.append(". ")

        if medium_priority:
            parts.append(f"We also suggest {len(medium_priority)} optional improvement(s).")

        if not high_priority and not medium_priority:
            parts.append("your integration setup looks good! No critical gaps detected.")

        return "".join(parts)
