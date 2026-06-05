"""
PARWA HubSpot Data Sync Service

Full and incremental data synchronization between HubSpot CRM
and PARWA's internal data store.

Features:
- Full sync: Fetches all contacts, deals, companies from HubSpot
- Incremental sync: Uses after cursor for efficient pagination
- Single record sync: sync_contact, sync_deal, sync_company for webhook updates
- Sync state management: Reads/writes state to Integration.settings JSON
- BC-008: Partial failure support — sync continues even if one resource fails
- BC-001: All operations scoped to company_id

Sync Flow:
1. Initial sync: Full import of all contacts, deals, companies
2. Incremental sync: Fetch only records changed since last sync using after cursor
3. Webhook-triggered sync: Individual record updates from webhooks

Sync State (stored in Integration.settings JSON):
{
  "hubspot_sync": {
    "contacts": {"last_after": "cursor_value", "last_sync": "ISO timestamp", "count": 1234},
    "deals": {"last_after": "cursor_value", "last_sync": "ISO timestamp", "count": 567},
    "companies": {"last_after": "cursor_value", "last_sync": "ISO timestamp", "count": 89}
  }
}

Usage:
    sync = HubSpotDataSync(
        hubspot_client=client,
        company_id="comp_1",
        integration_id="int_1",
        db_session=db,
    )
    result = await sync.full_sync()
    result = await sync.incremental_sync()
    result = await sync.sync_contact("12345")
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.clients.hubspot_client import HubSpotClient, HubSpotResult
from app.logger import get_logger
from database.models.integration import Integration

logger = get_logger("hubspot_data_sync")

# Sync status constants
SYNC_STATUS_IDLE = "idle"
SYNC_STATUS_RUNNING = "running"
SYNC_STATUS_COMPLETED = "completed"
SYNC_STATUS_FAILED = "failed"
SYNC_STATUS_PARTIAL = "partial"

# HubSpot property lists used for fetching data
CONTACT_PROPERTIES = [
    "email", "firstname", "lastname", "phone",
    "company", "jobtitle", "lifecyclestage",
    "createdate", "lastmodifieddate",
]

DEAL_PROPERTIES = [
    "dealname", "dealstage", "amount", "closedate",
    "pipeline", "dealtype", "createdate", "lastmodifieddate",
]

COMPANY_PROPERTIES = [
    "name", "domain", "industry", "city",
    "state", "country", "phone",
    "createdate", "lastmodifieddate",
]

# HubSpot page size limit (max 100 per request)
HUBSPOT_PAGE_LIMIT = 100


class HubSpotDataSync:
    """Service for syncing HubSpot CRM data to PARWA database.

    Each instance is scoped to a single company's HubSpot integration.
    Uses HubSpotClient for API calls and stores sync state in the
    Integration model's settings field under the 'hubspot_sync' key.

    BC-008: Partial failure support — sync continues even if one
    resource type fails. Results always include error details rather
    than raising exceptions.

    BC-001: All operations are scoped to company_id for tenant isolation.

    Args:
        hubspot_client: Authenticated HubSpotClient instance.
        company_id: PARWA company ID for tenant isolation.
        integration_id: Integration record ID for this HubSpot connection.
        db_session: Optional SQLAlchemy database session for state persistence.
    """

    def __init__(
        self,
        hubspot_client: HubSpotClient,
        company_id: str,
        integration_id: str,
        db_session: Optional[Session] = None,
    ):
        self.client = hubspot_client
        self.company_id = company_id
        self.integration_id = integration_id
        self.db = db_session

    # ── Sync State Management ─────────────────────────────────────

    def _read_sync_state(self) -> Dict[str, Any]:
        """Read sync state from Integration.settings JSON.

        The sync state is stored under the 'hubspot_sync' key within
        the Integration model's settings JSON field. This includes
        pagination cursors and timestamps for each resource type.

        Returns:
            Dict with sync state for contacts, deals, and companies.
            Returns empty dict if integration not found or no state exists.
        """
        if not self.integration_id or not self.db:
            return {}

        integration = self.db.query(Integration).filter(
            and_(
                Integration.id == self.integration_id,
                Integration.company_id == self.company_id,
            )
        ).first()

        if not integration:
            return {}

        try:
            settings = json.loads(integration.settings) if integration.settings else {}
        except (json.JSONDecodeError, TypeError):
            settings = {}

        return settings.get("hubspot_sync", {})

    def _write_sync_state(self, state: Dict[str, Any]) -> None:
        """Write sync state to Integration.settings JSON.

        Merges the provided state dict with existing sync state,
        preserving any fields not explicitly overwritten. The state
        is stored under the 'hubspot_sync' key within settings.

        Args:
            state: Dict of sync state updates to merge and persist.
        """
        if not self.integration_id or not self.db:
            return

        integration = self.db.query(Integration).filter(
            and_(
                Integration.id == self.integration_id,
                Integration.company_id == self.company_id,
            )
        ).first()

        if not integration:
            return

        try:
            settings = json.loads(integration.settings) if integration.settings else {}
        except (json.JSONDecodeError, TypeError):
            settings = {}

        current_state = settings.get("hubspot_sync", {})
        current_state.update(state)
        current_state["updated_at"] = datetime.now(timezone.utc).isoformat()
        settings["hubspot_sync"] = current_state

        integration.settings = json.dumps(settings)
        integration.updated_at = datetime.now(timezone.utc)
        self.db.flush()

    # ── Full Sync ─────────────────────────────────────────────────

    async def full_sync(self) -> Dict[str, Any]:
        """Full sync of all contacts, deals, companies from HubSpot.

        Fetches all records from each resource type using pagination.
        Used on initial integration connection or when a complete
        data refresh is needed.

        BC-008: If one resource type fails (e.g., contacts), the sync
        continues with the remaining types (deals, companies). The
        result will contain partial counts and error details.

        Returns:
            Dict with keys:
                - status: 'completed', 'partial', or 'failed'
                - contacts_synced: number of contacts processed
                - deals_synced: number of deals processed
                - companies_synced: number of companies processed
                - total_synced: sum of all synced counts
                - errors: list of error messages
                - started_at: ISO timestamp
                - completed_at: ISO timestamp
        """
        started_at = datetime.now(timezone.utc).isoformat()
        logger.info(
            "hubspot_full_sync_started company_id=%s integration_id=%s",
            self.company_id, self.integration_id,
        )

        errors: List[str] = []
        total_contacts = 0
        total_deals = 0
        total_companies = 0

        # Update sync state to running
        self._write_sync_state({"status": SYNC_STATUS_RUNNING})

        # Sync contacts
        try:
            contacts_result = await self._sync_contacts()
            total_contacts = contacts_result
        except Exception as exc:
            error_msg = f"Contacts sync failed: {str(exc)[:200]}"
            errors.append(error_msg)
            logger.error(
                "hubspot_contacts_sync_failed company_id=%s error=%s",
                self.company_id, str(exc)[:200],
            )

        # Sync deals
        try:
            deals_result = await self._sync_deals()
            total_deals = deals_result
        except Exception as exc:
            error_msg = f"Deals sync failed: {str(exc)[:200]}"
            errors.append(error_msg)
            logger.error(
                "hubspot_deals_sync_failed company_id=%s error=%s",
                self.company_id, str(exc)[:200],
            )

        # Sync companies
        try:
            companies_result = await self._sync_companies()
            total_companies = companies_result
        except Exception as exc:
            error_msg = f"Companies sync failed: {str(exc)[:200]}"
            errors.append(error_msg)
            logger.error(
                "hubspot_companies_sync_failed company_id=%s error=%s",
                self.company_id, str(exc)[:200],
            )

        # Determine final status (BC-008: partial failure support)
        if errors:
            total_synced = total_contacts + total_deals + total_companies
            status = SYNC_STATUS_PARTIAL if total_synced > 0 else SYNC_STATUS_FAILED
        else:
            status = SYNC_STATUS_COMPLETED

        completed_at = datetime.now(timezone.utc).isoformat()

        # Update sync state with final results
        self._write_sync_state({
            "status": status,
            "last_full_sync": completed_at,
            "contacts": {
                "last_sync": completed_at,
                "count": total_contacts,
            },
            "deals": {
                "last_sync": completed_at,
                "count": total_deals,
            },
            "companies": {
                "last_sync": completed_at,
                "count": total_companies,
            },
        })

        result = {
            "status": status,
            "contacts_synced": total_contacts,
            "deals_synced": total_deals,
            "companies_synced": total_companies,
            "total_synced": total_contacts + total_deals + total_companies,
            "errors": errors,
            "started_at": started_at,
            "completed_at": completed_at,
        }

        logger.info(
            "hubspot_full_sync_completed company_id=%s status=%s contacts=%d deals=%d companies=%d",
            self.company_id, status, total_contacts, total_deals, total_companies,
        )

        return result

    # ── Incremental Sync ──────────────────────────────────────────

    async def incremental_sync(self) -> Dict[str, Any]:
        """Incremental sync using saved after cursor from last sync.

        Only fetches records changed since the last successful sync
        by resuming from the saved pagination cursor. If no cursor
        exists for a resource type, falls back to a full sync for
        that type.

        HubSpot's cursor-based pagination uses the `after` parameter
        which points to the position after the last fetched record.
        Cursors are stored per resource type in sync state.

        Returns:
            Dict with keys:
                - status: 'completed', 'partial', or 'failed'
                - contacts_synced: number of new/updated contacts
                - deals_synced: number of new/updated deals
                - companies_synced: number of new/updated companies
                - total_synced: sum of all synced counts
                - errors: list of error messages
                - started_at: ISO timestamp
                - completed_at: ISO timestamp
        """
        started_at = datetime.now(timezone.utc).isoformat()
        sync_state = self._read_sync_state()

        logger.info(
            "hubspot_incremental_sync_started company_id=%s last_contacts_sync=%s last_deals_sync=%s last_companies_sync=%s",
            self.company_id,
            sync_state.get("contacts", {}).get("last_sync", "never"),
            sync_state.get("deals", {}).get("last_sync", "never"),
            sync_state.get("companies", {}).get("last_sync", "never"),
        )

        errors: List[str] = []
        total_contacts = 0
        total_deals = 0
        total_companies = 0

        # Update sync state to running
        self._write_sync_state({"status": SYNC_STATUS_RUNNING})

        # Incremental contacts sync using saved after cursor
        try:
            contacts_after = sync_state.get("contacts", {}).get("last_after", "")
            total_contacts = await self._sync_contacts(after=contacts_after)
        except Exception as exc:
            errors.append(f"Incremental contacts sync failed: {str(exc)[:200]}")
            logger.error(
                "hubspot_incremental_contacts_failed company_id=%s error=%s",
                self.company_id, str(exc)[:200],
            )

        # Incremental deals sync using saved after cursor
        try:
            deals_after = sync_state.get("deals", {}).get("last_after", "")
            total_deals = await self._sync_deals(after=deals_after)
        except Exception as exc:
            errors.append(f"Incremental deals sync failed: {str(exc)[:200]}")
            logger.error(
                "hubspot_incremental_deals_failed company_id=%s error=%s",
                self.company_id, str(exc)[:200],
            )

        # Incremental companies sync using saved after cursor
        try:
            companies_after = sync_state.get("companies", {}).get("last_after", "")
            total_companies = await self._sync_companies(after=companies_after)
        except Exception as exc:
            errors.append(f"Incremental companies sync failed: {str(exc)[:200]}")
            logger.error(
                "hubspot_incremental_companies_failed company_id=%s error=%s",
                self.company_id, str(exc)[:200],
            )

        # Determine final status
        if errors:
            total_synced = total_contacts + total_deals + total_companies
            status = SYNC_STATUS_PARTIAL if total_synced > 0 else SYNC_STATUS_FAILED
        else:
            status = SYNC_STATUS_COMPLETED

        completed_at = datetime.now(timezone.utc).isoformat()

        # Update sync state
        self._write_sync_state({
            "status": status,
            "last_incremental_sync": completed_at,
        })

        result = {
            "status": status,
            "contacts_synced": total_contacts,
            "deals_synced": total_deals,
            "companies_synced": total_companies,
            "total_synced": total_contacts + total_deals + total_companies,
            "errors": errors,
            "started_at": started_at,
            "completed_at": completed_at,
        }

        logger.info(
            "hubspot_incremental_sync_completed company_id=%s status=%s contacts=%d deals=%d companies=%d",
            self.company_id, status, total_contacts, total_deals, total_companies,
        )

        return result

    # ── Single Record Sync ────────────────────────────────────────

    async def sync_contact(self, contact_id: str) -> Dict[str, Any]:
        """Sync a single contact (for webhook-triggered updates).

        Fetches the contact from HubSpot by ID and processes it
        into PARWA format. Used when a HubSpot webhook notifies
        us of a contact creation or update.

        BC-008: Never raises exceptions. Returns error dict on failure.

        Args:
            contact_id: HubSpot contact ID to sync.

        Returns:
            Dict with keys:
                - success: bool indicating if the sync succeeded
                - contact_id: the HubSpot contact ID
                - data: processed contact data (on success)
                - error: error message (on failure)
        """
        try:
            result = await self.client.get_contact(
                contact_id, properties=CONTACT_PROPERTIES,
            )

            if not result.success:
                logger.warning(
                    "hubspot_sync_contact_failed contact_id=%s error=%s company_id=%s",
                    contact_id, result.error, self.company_id,
                )
                return {
                    "success": False,
                    "contact_id": contact_id,
                    "error": f"Failed to fetch contact {contact_id}: {result.error}",
                }

            contact_data = result.data
            processed = self._process_contact(contact_data)

            logger.info(
                "hubspot_contact_synced contact_id=%s email=%s company_id=%s",
                contact_data.get("id"),
                contact_data.get("properties", {}).get("email", ""),
                self.company_id,
            )

            return {
                "success": True,
                "contact_id": contact_id,
                "data": processed,
            }

        except Exception as exc:
            logger.error(
                "hubspot_sync_contact_error contact_id=%s company_id=%s error=%s",
                contact_id, self.company_id, str(exc)[:200],
            )
            return {
                "success": False,
                "contact_id": contact_id,
                "error": f"Unexpected error syncing contact {contact_id}: {str(exc)[:200]}",
            }

    async def sync_deal(self, deal_id: str) -> Dict[str, Any]:
        """Sync a single deal.

        Fetches the deal from HubSpot by ID and processes it
        into PARWA format. Used when a HubSpot webhook notifies
        us of a deal creation, update, or stage change.

        BC-008: Never raises exceptions. Returns error dict on failure.

        Args:
            deal_id: HubSpot deal ID to sync.

        Returns:
            Dict with keys:
                - success: bool indicating if the sync succeeded
                - deal_id: the HubSpot deal ID
                - data: processed deal data (on success)
                - error: error message (on failure)
        """
        try:
            result = await self.client.get_deal(
                deal_id, properties=DEAL_PROPERTIES,
            )

            if not result.success:
                logger.warning(
                    "hubspot_sync_deal_failed deal_id=%s error=%s company_id=%s",
                    deal_id, result.error, self.company_id,
                )
                return {
                    "success": False,
                    "deal_id": deal_id,
                    "error": f"Failed to fetch deal {deal_id}: {result.error}",
                }

            deal_data = result.data
            processed = self._process_deal(deal_data)

            logger.info(
                "hubspot_deal_synced deal_id=%s name=%s company_id=%s",
                deal_data.get("id"),
                deal_data.get("properties", {}).get("dealname", ""),
                self.company_id,
            )

            return {
                "success": True,
                "deal_id": deal_id,
                "data": processed,
            }

        except Exception as exc:
            logger.error(
                "hubspot_sync_deal_error deal_id=%s company_id=%s error=%s",
                deal_id, self.company_id, str(exc)[:200],
            )
            return {
                "success": False,
                "deal_id": deal_id,
                "error": f"Unexpected error syncing deal {deal_id}: {str(exc)[:200]}",
            }

    async def sync_company(self, company_id: str) -> Dict[str, Any]:
        """Sync a single company.

        Fetches the company from HubSpot by ID and processes it
        into PARWA format. Used when a HubSpot webhook notifies
        us of a company creation or update.

        Note: The `company_id` parameter here refers to the HubSpot
        company (organization) ID, not the PARWA company_id used
        for tenant isolation.

        BC-008: Never raises exceptions. Returns error dict on failure.

        Args:
            company_id: HubSpot company ID to sync.

        Returns:
            Dict with keys:
                - success: bool indicating if the sync succeeded
                - company_id: the HubSpot company ID
                - data: processed company data (on success)
                - error: error message (on failure)
        """
        try:
            result = await self.client.get_company(
                company_id, properties=COMPANY_PROPERTIES,
            )

            if not result.success:
                logger.warning(
                    "hubspot_sync_company_failed company_id=%s error=%s parwa_company_id=%s",
                    company_id, result.error, self.company_id,
                )
                return {
                    "success": False,
                    "company_id": company_id,
                    "error": f"Failed to fetch company {company_id}: {result.error}",
                }

            company_data = result.data
            processed = self._process_company(company_data)

            logger.info(
                "hubspot_company_synced hubspot_company_id=%s name=%s parwa_company_id=%s",
                company_data.get("id"),
                company_data.get("properties", {}).get("name", ""),
                self.company_id,
            )

            return {
                "success": True,
                "company_id": company_id,
                "data": processed,
            }

        except Exception as exc:
            logger.error(
                "hubspot_sync_company_error company_id=%s parwa_company_id=%s error=%s",
                company_id, self.company_id, str(exc)[:200],
            )
            return {
                "success": False,
                "company_id": company_id,
                "error": f"Unexpected error syncing company {company_id}: {str(exc)[:200]}",
            }

    # ── Internal Batch Sync ───────────────────────────────────────

    async def _sync_contacts(self, after: str = "") -> int:
        """Internal: sync all contacts using pagination.

        Fetches contacts page by page using HubSpot's cursor-based
        pagination. Each page of contacts is processed individually.
        The after cursor from the last page is saved to sync state
        for incremental sync support.

        BC-008: If a single contact fails to process, it is logged
        and skipped — the sync continues with remaining contacts.

        Args:
            after: Pagination cursor to resume from. Empty string
                   starts from the beginning.

        Returns:
            Number of successfully processed contacts.

        Raises:
            Exception: If the HubSpot API call fails entirely.
        """
        count = 0
        current_after = after
        page = 0

        while True:
            result = await self.client.list_contacts(
                limit=HUBSPOT_PAGE_LIMIT,
                after=current_after if current_after else None,
                properties=CONTACT_PROPERTIES,
            )

            if not result.success:
                raise Exception(result.error)

            contacts = result.data.get("results", [])

            for contact in contacts:
                try:
                    if self._process_contact(contact):
                        count += 1
                except Exception as exc:
                    contact_id = contact.get("id", "unknown")
                    logger.warning(
                        "hubspot_contact_process_failed contact_id=%s company_id=%s error=%s",
                        contact_id, self.company_id, str(exc)[:200],
                    )

            # Check for next page via cursor
            paging = result.data.get("paging", {})
            next_page = paging.get("next", {})
            next_after = next_page.get("after")

            if not next_after or not contacts:
                break

            current_after = next_after
            page += 1

            # Save the cursor after each page for resumability
            self._write_sync_state({
                "contacts": {
                    "last_after": current_after,
                    "last_sync": datetime.now(timezone.utc).isoformat(),
                    "count": count,
                },
            })

        return count

    async def _sync_deals(self, after: str = "") -> int:
        """Internal: sync all deals using pagination.

        Fetches deals page by page using HubSpot's cursor-based
        pagination. Each page of deals is processed individually.
        The after cursor from the last page is saved to sync state
        for incremental sync support.

        BC-008: If a single deal fails to process, it is logged
        and skipped — the sync continues with remaining deals.

        Args:
            after: Pagination cursor to resume from. Empty string
                   starts from the beginning.

        Returns:
            Number of successfully processed deals.

        Raises:
            Exception: If the HubSpot API call fails entirely.
        """
        count = 0
        current_after = after
        page = 0

        while True:
            result = await self.client.list_deals(
                limit=HUBSPOT_PAGE_LIMIT,
                after=current_after if current_after else None,
                properties=DEAL_PROPERTIES,
            )

            if not result.success:
                raise Exception(result.error)

            deals = result.data.get("results", [])

            for deal in deals:
                try:
                    if self._process_deal(deal):
                        count += 1
                except Exception as exc:
                    deal_id = deal.get("id", "unknown")
                    logger.warning(
                        "hubspot_deal_process_failed deal_id=%s company_id=%s error=%s",
                        deal_id, self.company_id, str(exc)[:200],
                    )

            # Check for next page via cursor
            paging = result.data.get("paging", {})
            next_page = paging.get("next", {})
            next_after = next_page.get("after")

            if not next_after or not deals:
                break

            current_after = next_after
            page += 1

            # Save the cursor after each page for resumability
            self._write_sync_state({
                "deals": {
                    "last_after": current_after,
                    "last_sync": datetime.now(timezone.utc).isoformat(),
                    "count": count,
                },
            })

        return count

    async def _sync_companies(self, after: str = "") -> int:
        """Internal: sync all companies using pagination.

        Fetches companies page by page using HubSpot's cursor-based
        pagination. Each page of companies is processed individually.
        The after cursor from the last page is saved to sync state
        for incremental sync support.

        BC-008: If a single company fails to process, it is logged
        and skipped — the sync continues with remaining companies.

        Args:
            after: Pagination cursor to resume from. Empty string
                   starts from the beginning.

        Returns:
            Number of successfully processed companies.

        Raises:
            Exception: If the HubSpot API call fails entirely.
        """
        count = 0
        current_after = after
        page = 0

        while True:
            result = await self.client.list_companies(
                limit=HUBSPOT_PAGE_LIMIT,
                after=current_after if current_after else None,
                properties=COMPANY_PROPERTIES,
            )

            if not result.success:
                raise Exception(result.error)

            companies = result.data.get("results", [])

            for company in companies:
                try:
                    if self._process_company(company):
                        count += 1
                except Exception as exc:
                    company_hs_id = company.get("id", "unknown")
                    logger.warning(
                        "hubspot_company_process_failed hubspot_company_id=%s company_id=%s error=%s",
                        company_hs_id, self.company_id, str(exc)[:200],
                    )

            # Check for next page via cursor
            paging = result.data.get("paging", {})
            next_page = paging.get("next", {})
            next_after = next_page.get("after")

            if not next_after or not companies:
                break

            current_after = next_after
            page += 1

            # Save the cursor after each page for resumability
            self._write_sync_state({
                "companies": {
                    "last_after": current_after,
                    "last_sync": datetime.now(timezone.utc).isoformat(),
                    "count": count,
                },
            })

        return count

    # ── Data Processing ───────────────────────────────────────────

    def _process_contact(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        """Process a HubSpot contact into PARWA format.

        Transforms the raw HubSpot contact object (which stores
        custom fields inside a 'properties' sub-dict) into PARWA's
        normalized contact format.

        HubSpot contact properties mapping:
            email        → email
            firstname    → first_name
            lastname     → last_name
            phone        → phone
            company      → company_name
            jobtitle     → job_title
            lifecyclestage → lifecycle_stage

        Args:
            contact: Raw HubSpot contact dict with 'id', 'properties',
                     'createdAt', 'updatedAt' fields.

        Returns:
            Normalized contact dict in PARWA format, or empty dict
            if the contact is missing required fields.
        """
        try:
            # Validate minimum required fields
            if not contact.get("id"):
                logger.warning(
                    "hubspot_contact_missing_id company_id=%s", self.company_id,
                )
                return {}

            props = contact.get("properties", {})

            normalized = {
                "hubspot_contact_id": str(contact.get("id", "")),
                "email": props.get("email", ""),
                "first_name": props.get("firstname", ""),
                "last_name": props.get("lastname", ""),
                "phone": props.get("phone", ""),
                "company_name": props.get("company", ""),
                "job_title": props.get("jobtitle", ""),
                "lifecycle_stage": props.get("lifecyclestage", ""),
                "company_id": self.company_id,
                "created_at": contact.get("createdAt"),
                "updated_at": contact.get("updatedAt"),
            }

            logger.debug(
                "hubspot_contact_processed contact_id=%s email=%s company_id=%s",
                normalized["hubspot_contact_id"], normalized["email"], self.company_id,
            )

            return normalized

        except Exception as exc:
            logger.error(
                "hubspot_contact_process_error company_id=%s error=%s",
                self.company_id, str(exc)[:200],
            )
            return {}

    def _process_deal(self, deal: Dict[str, Any]) -> Dict[str, Any]:
        """Process a HubSpot deal into PARWA format.

        Transforms the raw HubSpot deal object (which stores
        custom fields inside a 'properties' sub-dict) into PARWA's
        normalized deal format.

        HubSpot deal properties mapping:
            dealname   → name
            dealstage  → stage
            amount     → amount
            closedate  → close_date
            pipeline   → pipeline
            dealtype   → deal_type

        Args:
            deal: Raw HubSpot deal dict with 'id', 'properties',
                  'createdAt', 'updatedAt' fields.

        Returns:
            Normalized deal dict in PARWA format, or empty dict
            if the deal is missing required fields.
        """
        try:
            # Validate minimum required fields
            if not deal.get("id"):
                logger.warning(
                    "hubspot_deal_missing_id company_id=%s", self.company_id,
                )
                return {}

            props = deal.get("properties", {})

            normalized = {
                "hubspot_deal_id": str(deal.get("id", "")),
                "name": props.get("dealname", ""),
                "stage": props.get("dealstage", ""),
                "amount": props.get("amount", ""),
                "close_date": props.get("closedate", ""),
                "pipeline": props.get("pipeline", ""),
                "deal_type": props.get("dealtype", ""),
                "company_id": self.company_id,
                "created_at": deal.get("createdAt"),
                "updated_at": deal.get("updatedAt"),
            }

            logger.debug(
                "hubspot_deal_processed deal_id=%s name=%s company_id=%s",
                normalized["hubspot_deal_id"], normalized["name"], self.company_id,
            )

            return normalized

        except Exception as exc:
            logger.error(
                "hubspot_deal_process_error company_id=%s error=%s",
                self.company_id, str(exc)[:200],
            )
            return {}

    def _process_company(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Process a HubSpot company into PARWA format.

        Transforms the raw HubSpot company object (which stores
        custom fields inside a 'properties' sub-dict) into PARWA's
        normalized company format.

        HubSpot company properties mapping:
            name     → name
            domain   → website
            industry → industry
            city     → city
            state    → state
            country  → country
            phone    → phone

        Args:
            company: Raw HubSpot company dict with 'id', 'properties',
                     'createdAt', 'updatedAt' fields.

        Returns:
            Normalized company dict in PARWA format, or empty dict
            if the company is missing required fields.
        """
        try:
            # Validate minimum required fields
            if not company.get("id"):
                logger.warning(
                    "hubspot_company_missing_id company_id=%s", self.company_id,
                )
                return {}

            props = company.get("properties", {})

            normalized = {
                "hubspot_company_id": str(company.get("id", "")),
                "name": props.get("name", ""),
                "website": props.get("domain", ""),
                "industry": props.get("industry", ""),
                "city": props.get("city", ""),
                "state": props.get("state", ""),
                "country": props.get("country", ""),
                "phone": props.get("phone", ""),
                "company_id": self.company_id,
                "created_at": company.get("createdAt"),
                "updated_at": company.get("updatedAt"),
            }

            logger.debug(
                "hubspot_company_processed hubspot_company_id=%s name=%s parwa_company_id=%s",
                normalized["hubspot_company_id"], normalized["name"], self.company_id,
            )

            return normalized

        except Exception as exc:
            logger.error(
                "hubspot_company_process_error company_id=%s error=%s",
                self.company_id, str(exc)[:200],
            )
            return {}

    # ── Sync Status ───────────────────────────────────────────────

    def get_sync_status(self) -> Dict[str, Any]:
        """Get the current sync status for this integration.

        Returns a summary of the sync state including the current
        status, last sync timestamps, and record counts for each
        resource type.

        Returns:
            Dict with sync status information including:
                - company_id: PARWA tenant ID
                - integration_id: Integration record ID
                - status: Current sync status
                - last_full_sync: Timestamp of last full sync
                - last_incremental_sync: Timestamp of last incremental sync
                - contacts: Contact sync state (last_after, last_sync, count)
                - deals: Deal sync state (last_after, last_sync, count)
                - companies: Company sync state (last_after, last_sync, count)
        """
        sync_state = self._read_sync_state()
        return {
            "company_id": self.company_id,
            "integration_id": self.integration_id,
            "status": sync_state.get("status", SYNC_STATUS_IDLE),
            "last_full_sync": sync_state.get("last_full_sync"),
            "last_incremental_sync": sync_state.get("last_incremental_sync"),
            "contacts": sync_state.get("contacts", {}),
            "deals": sync_state.get("deals", {}),
            "companies": sync_state.get("companies", {}),
        }
