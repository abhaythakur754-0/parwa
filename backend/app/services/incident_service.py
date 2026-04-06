"""
Incident Service - PS10: Incident mode management (Day 32)

Handles:
- Incident creation and management
- System-wide incident banners
- Auto-tagging tickets linked to incidents
- Mass notifications to affected customers
- Master ticket linking
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import and_, desc, or_
from sqlalchemy.orm import Session

from backend.app.exceptions import NotFoundError, ValidationError
from database.models.tickets import Ticket, TicketStatus
from database.models.core import User


class Incident:
    """
    Incident model representation.
    
    In production, this would be a proper SQLAlchemy model.
    For now, stored in a dedicated table or as company metadata.
    """
    
    STATUS_ACTIVE = "active"
    STATUS_INVESTIGATING = "investigating"
    STATUS_IDENTIFIED = "identified"
    STATUS_MONITORING = "monitoring"
    STATUS_RESOLVED = "resolved"
    
    SEVERITY_LOW = "low"
    SEVERITY_MEDIUM = "medium"
    SEVERITY_HIGH = "high"
    SEVERITY_CRITICAL = "critical"


class IncidentService:
    """
    PS10: Incident mode management.
    
    Features:
    - Create and manage incidents
    - System-wide incident banners
    - Auto-tag related tickets
    - Mass notifications to affected customers
    - Master ticket linking
    - Incident timeline/status updates
    """
    
    # Incident status flow
    STATUS_FLOW = [
        Incident.STATUS_ACTIVE,
        Incident.STATUS_INVESTIGATING,
        Incident.STATUS_IDENTIFIED,
        Incident.STATUS_MONITORING,
        Incident.STATUS_RESOLVED,
    ]
    
    # Auto-tag prefix for incident-related tickets
    INCIDENT_TAG_PREFIX = "incident:"
    
    def __init__(self, db: Session, company_id: str):
        self.db = db
        self.company_id = company_id
    
    def create_incident(
        self,
        title: str,
        description: str,
        severity: str = Incident.SEVERITY_MEDIUM,
        affected_services: Optional[List[str]] = None,
        master_ticket_id: Optional[str] = None,
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new incident.
        
        Args:
            title: Incident title
            description: Incident description
            severity: Severity level (low, medium, high, critical)
            affected_services: List of affected services
            master_ticket_id: Primary ticket linked to this incident
            created_by: User ID who created the incident
            
        Returns:
            Created incident
        """
        if severity not in [
            Incident.SEVERITY_LOW,
            Incident.SEVERITY_MEDIUM,
            Incident.SEVERITY_HIGH,
            Incident.SEVERITY_CRITICAL,
        ]:
            raise ValidationError(f"Invalid severity: {severity}")
        
        incident_id = str(uuid4())
        
        incident = {
            "id": incident_id,
            "company_id": self.company_id,
            "title": title,
            "description": description,
            "severity": severity,
            "status": Incident.STATUS_ACTIVE,
            "affected_services": affected_services or [],
            "master_ticket_id": master_ticket_id,
            "linked_ticket_ids": [master_ticket_id] if master_ticket_id else [],
            "affected_customer_ids": [],
            "status_updates": [
                {
                    "status": Incident.STATUS_ACTIVE,
                    "message": "Incident created",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
            "created_by": created_by,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "resolved_at": None,
        }
        
        # Store incident (in production, save to incidents table)
        self._store_incident(incident)
        
        # Auto-tag master ticket if provided
        if master_ticket_id:
            self._tag_ticket(master_ticket_id, incident_id)
        
        # Send initial notification
        self._send_incident_notification(incident, "created")
        
        return incident
    
    def update_incident_status(
        self,
        incident_id: str,
        new_status: str,
        message: Optional[str] = None,
        updated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Update incident status.
        
        Args:
            incident_id: Incident ID
            new_status: New status
            message: Status update message
            updated_by: User ID who updated
            
        Returns:
            Updated incident
        """
        incident = self._get_incident(incident_id)
        
        if new_status not in self.STATUS_FLOW:
            raise ValidationError(f"Invalid status: {new_status}")
        
        old_status = incident["status"]
        
        # Update status
        incident["status"] = new_status
        incident["updated_at"] = datetime.utcnow().isoformat()
        
        # Add status update
        status_update = {
            "status": new_status,
            "message": message or f"Status changed from {old_status} to {new_status}",
            "timestamp": datetime.utcnow().isoformat(),
            "updated_by": updated_by,
        }
        incident["status_updates"].append(status_update)
        
        # Handle resolution
        if new_status == Incident.STATUS_RESOLVED:
            incident["resolved_at"] = datetime.utcnow().isoformat()
        
        # Store updated incident
        self._store_incident(incident)
        
        # Send notification
        self._send_incident_notification(incident, "updated", message)
        
        return incident
    
    def resolve_incident(
        self,
        incident_id: str,
        resolution_summary: str,
        resolved_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolve an incident.
        
        Args:
            incident_id: Incident ID
            resolution_summary: Resolution summary
            resolved_by: User ID who resolved
            
        Returns:
            Resolved incident
        """
        return self.update_incident_status(
            incident_id=incident_id,
            new_status=Incident.STATUS_RESOLVED,
            message=resolution_summary,
            updated_by=resolved_by,
        )
    
    def link_ticket(
        self,
        incident_id: str,
        ticket_id: str,
    ) -> Dict[str, Any]:
        """
        Link a ticket to an incident.
        
        Args:
            incident_id: Incident ID
            ticket_id: Ticket ID to link
            
        Returns:
            Updated incident
        """
        incident = self._get_incident(incident_id)
        
        if ticket_id not in incident["linked_ticket_ids"]:
            incident["linked_ticket_ids"].append(ticket_id)
            incident["updated_at"] = datetime.utcnow().isoformat()
            
            self._store_incident(incident)
            
            # Auto-tag the ticket
            self._tag_ticket(ticket_id, incident_id)
        
        return incident
    
    def unlink_ticket(
        self,
        incident_id: str,
        ticket_id: str,
    ) -> Dict[str, Any]:
        """
        Unlink a ticket from an incident.
        
        Args:
            incident_id: Incident ID
            ticket_id: Ticket ID to unlink
            
        Returns:
            Updated incident
        """
        incident = self._get_incident(incident_id)
        
        if ticket_id in incident["linked_ticket_ids"]:
            incident["linked_ticket_ids"].remove(ticket_id)
            incident["updated_at"] = datetime.utcnow().isoformat()
            
            self._store_incident(incident)
            
            # Remove incident tag from ticket
            self._untag_ticket(ticket_id, incident_id)
        
        return incident
    
    def add_affected_customers(
        self,
        incident_id: str,
        customer_ids: List[str],
    ) -> Dict[str, Any]:
        """
        Add affected customers to an incident.
        
        Args:
            incident_id: Incident ID
            customer_ids: List of customer IDs
            
        Returns:
            Updated incident
        """
        incident = self._get_incident(incident_id)
        
        for customer_id in customer_ids:
            if customer_id not in incident["affected_customer_ids"]:
                incident["affected_customer_ids"].append(customer_id)
        
        incident["updated_at"] = datetime.utcnow().isoformat()
        
        self._store_incident(incident)
        
        return incident
    
    def notify_affected_customers(
        self,
        incident_id: str,
        message: str,
    ) -> Dict[str, Any]:
        """
        PS10: Mass-notify all affected customers.
        
        Args:
            incident_id: Incident ID
            message: Notification message
            
        Returns:
            Notification result
        """
        incident = self._get_incident(incident_id)
        
        if not incident["affected_customer_ids"]:
            return {
                "success": True,
                "notified_count": 0,
                "message": "No affected customers to notify",
            }
        
        # Import notification service
        from backend.app.services.notification_service import NotificationService
        
        notification_service = NotificationService(self.db, self.company_id)
        
        result = notification_service.notify_incident_subscribers(
            incident_id=incident_id,
            incident_title=incident["title"],
            status_update=message,
            affected_customer_ids=incident["affected_customer_ids"],
        )
        
        return result
    
    def get_active_incidents(
        self,
        include_resolved: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get all active incidents for the company.
        
        Args:
            include_resolved: Include resolved incidents
            
        Returns:
            List of incidents
        """
        incidents = self._get_company_incidents()
        
        if not include_resolved:
            incidents = [
                i for i in incidents
                if i["status"] != Incident.STATUS_RESOLVED
            ]
        
        return sorted(incidents, key=lambda x: x["created_at"], reverse=True)
    
    def get_incident(
        self,
        incident_id: str,
    ) -> Dict[str, Any]:
        """Get incident by ID."""
        return self._get_incident(incident_id)
    
    def get_incident_banner(
        self,
    ) -> Optional[Dict[str, Any]]:
        """
        Get incident banner data for UI display.
        
        Returns active critical/high severity incidents for banner display.
        """
        active_incidents = self.get_active_incidents()
        
        # Filter for banner-worthy incidents
        banner_incidents = [
            i for i in active_incidents
            if i["severity"] in [Incident.SEVERITY_CRITICAL, Incident.SEVERITY_HIGH]
        ]
        
        if not banner_incidents:
            return None
        
        return {
            "has_incident": True,
            "incidents": [
                {
                    "id": i["id"],
                    "title": i["title"],
                    "severity": i["severity"],
                    "status": i["status"],
                }
                for i in banner_incidents
            ],
        }
    
    def get_linked_tickets(
        self,
        incident_id: str,
    ) -> List[Ticket]:
        """
        Get all tickets linked to an incident.
        
        Args:
            incident_id: Incident ID
            
        Returns:
            List of linked tickets
        """
        incident = self._get_incident(incident_id)
        
        if not incident["linked_ticket_ids"]:
            return []
        
        tickets = self.db.query(Ticket).filter(
            Ticket.id.in_(incident["linked_ticket_ids"]),
            Ticket.company_id == self.company_id,
        ).all()
        
        return list(tickets)
    
    def get_incident_statistics(
        self,
    ) -> Dict[str, Any]:
        """Get incident statistics for the company."""
        incidents = self._get_company_incidents()
        
        active = [i for i in incidents if i["status"] != Incident.STATUS_RESOLVED]
        resolved = [i for i in incidents if i["status"] == Incident.STATUS_RESOLVED]
        
        by_severity = {
            Incident.SEVERITY_CRITICAL: 0,
            Incident.SEVERITY_HIGH: 0,
            Incident.SEVERITY_MEDIUM: 0,
            Incident.SEVERITY_LOW: 0,
        }
        
        for incident in active:
            by_severity[incident["severity"]] += 1
        
        # Calculate average resolution time
        resolution_times = []
        for incident in resolved:
            if incident.get("resolved_at") and incident.get("created_at"):
                created = datetime.fromisoformat(incident["created_at"])
                resolved_at = datetime.fromisoformat(incident["resolved_at"])
                resolution_times.append((resolved_at - created).total_seconds() / 3600)
        
        avg_resolution_time = (
            sum(resolution_times) / len(resolution_times)
            if resolution_times else 0
        )
        
        return {
            "total_incidents": len(incidents),
            "active_incidents": len(active),
            "resolved_incidents": len(resolved),
            "by_severity": by_severity,
            "average_resolution_hours": round(avg_resolution_time, 2),
        }
    
    def _store_incident(
        self,
        incident: Dict[str, Any],
    ) -> None:
        """Store incident (placeholder for actual DB storage)."""
        # In production, this would save to an incidents table
        # For now, we'll use a simple file-based or Redis storage
        import redis
        import os
        
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            r = redis.from_url(redis_url)
            key = f"parwa:incidents:{self.company_id}:{incident['id']}"
            r.set(key, json.dumps(incident))
            # Add to company's incident index
            r.sadd(f"parwa:incidents:{self.company_id}:index", incident['id'])
        except Exception:
            pass  # Graceful degradation if Redis unavailable
    
    def _get_incident(
        self,
        incident_id: str,
    ) -> Dict[str, Any]:
        """Get incident from storage."""
        import redis
        import os
        
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            r = redis.from_url(redis_url)
            key = f"parwa:incidents:{self.company_id}:{incident_id}"
            data = r.get(key)
            if data:
                return json.loads(data)
        except Exception:
            pass
        
        raise NotFoundError(f"Incident {incident_id} not found")
    
    def _get_company_incidents(
        self,
    ) -> List[Dict[str, Any]]:
        """Get all incidents for the company."""
        import redis
        import os
        
        incidents = []
        
        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            r = redis.from_url(redis_url)
            index_key = f"parwa:incidents:{self.company_id}:index"
            incident_ids = r.smembers(index_key)
            
            for incident_id in incident_ids:
                try:
                    incident_id_str = incident_id.decode() if isinstance(incident_id, bytes) else incident_id
                    incident = self._get_incident(incident_id_str)
                    incidents.append(incident)
                except Exception:
                    continue
        except Exception:
            pass
        
        return incidents
    
    def _tag_ticket(
        self,
        ticket_id: str,
        incident_id: str,
    ) -> None:
        """Add incident tag to ticket."""
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == self.company_id,
        ).first()
        
        if ticket:
            try:
                tags = json.loads(ticket.tags) if ticket.tags else []
            except (json.JSONDecodeError, TypeError):
                tags = []
            
            incident_tag = f"{self.INCIDENT_TAG_PREFIX}{incident_id}"
            if incident_tag not in tags:
                tags.append(incident_tag)
                ticket.tags = json.dumps(tags)
                self.db.commit()
    
    def _untag_ticket(
        self,
        ticket_id: str,
        incident_id: str,
    ) -> None:
        """Remove incident tag from ticket."""
        ticket = self.db.query(Ticket).filter(
            Ticket.id == ticket_id,
            Ticket.company_id == self.company_id,
        ).first()
        
        if ticket:
            try:
                tags = json.loads(ticket.tags) if ticket.tags else []
            except (json.JSONDecodeError, TypeError):
                tags = []
            
            incident_tag = f"{self.INCIDENT_TAG_PREFIX}{incident_id}"
            if incident_tag in tags:
                tags.remove(incident_tag)
                ticket.tags = json.dumps(tags)
                self.db.commit()
    
    def _send_incident_notification(
        self,
        incident: Dict[str, Any],
        event_type: str,
        message: Optional[str] = None,
    ) -> None:
        """Send incident notification to admins."""
        from backend.app.services.notification_service import NotificationService
        
        notification_service = NotificationService(self.db, self.company_id)
        
        # Get admins to notify
        admins = self.db.query(User).filter(
            User.company_id == self.company_id,
            User.role.in_(["admin", "manager"]),
        ).all()
        
        if not admins:
            return
        
        notification_service.send_notification(
            event_type="incident_created" if event_type == "created" else "incident_resolved",
            recipient_ids=[a.id for a in admins],
            data={
                "incident_id": incident["id"],
                "incident_title": incident["title"],
                "status_update": message or incident["status"],
                "severity": incident["severity"],
            },
            channels=["email", "in_app"],
            priority="urgent" if incident["severity"] == Incident.SEVERITY_CRITICAL else "high",
        )
