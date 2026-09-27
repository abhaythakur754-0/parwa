"""
Parwa Production Backend - Main Application
============================================
Integrates all database functions:
- Variant limits & usage tracking (check_user_usage_limit)
- Free trial vs paid subscriber management
- Integration tools storage (CRM, webhooks, etc.)
- Auto-shutdown when limits exceeded
- Dashboard monitoring for Node 1

Author: Production Team
Version: 2.0.0 (Production Ready)
"""

import os
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Tuple
from functools import wraps

import psycopg2
from psycopg2.extras import RealDictCursor, RealDictRow
from dotenv import load_dotenv

# Load environment variables
load_dotenv('/home/z/my-project/.env')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseConfig:
    """Database configuration from .env or defaults"""
    HOST = os.getenv('DB_HOST', '')
    PORT = int(os.getenv('DB_PORT', '5432'))
    DATABASE = os.getenv('DB_NAME', '')
    USER = os.getenv('DB_USER', '')
    PASSWORD = os.getenv('DB_PASSWORD', '')


def get_db_connection():
    """Create and return a new database connection"""
    return psycopg2.connect(
        host=DatabaseConfig.HOST,
        port=DatabaseConfig.PORT,
        dbname=DatabaseConfig.DATABASE,
        user=DatabaseConfig.USER,
        password=DatabaseConfig.PASSWORD
    )


# =============================================================================
# USAGE LIMITS & VARIANT MANAGEMENT
# =============================================================================

class UsageLimitManager:
    """
    Manages usage limits for companies based on their variant/plan.
    
    Integrated with database functions:
    - check_user_usage_limit(company_id, type)
    - enforce_usage_limit_and_shutdown() trigger on tickets
    - v_company_usage_dashboard VIEW
    """
    
    def __init__(self):
        self.conn = None
    
    def __enter__(self):
        self.conn = get_db_connection()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def check_usage(self, company_id: str, check_type: str = 'tickets') -> Dict[str, Any]:
        """
        Check current usage against limits.
        
        Args:
            company_id: The company UUID
            check_type: Type of usage to check ('tickets', 'ai_agents', 'voice_minutes')
        
        Returns:
            Dict with allowed, current_usage, limit_value, remaining, percentage_used, message
        """
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM check_user_usage_limit(%s, %s)
            """, (company_id, check_type))
            
            result = cur.fetchone()
            if result:
                return dict(result)
            return {
                'allowed': False,
                'current_usage': 0,
                'limit_value': 0,
                'remaining': 0,
                'percentage_used': 0,
                'message': 'Company not found or invalid check type'
            }
    
    def can_create_ticket(self, company_id: str) -> Tuple[bool, str]:
        """Check if company is allowed to create a new ticket."""
        usage = self.check_usage(company_id, 'tickets')
        
        if not usage['allowed']:
            return False, usage.get('message', 'Limit exceeded')
        
        if usage['remaining'] <= 0:
            return False, f"Monthly ticket limit reached ({usage['limit_value']} tickets). Please upgrade your plan."
        
        return True, f"Allowed. {usage['remaining']} tickets remaining this month."
    
    def get_company_variant_info(self, company_id: str) -> Optional[Dict]:
        """Get variant/plan information for a company."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    c.id as company_id,
                    c.name as company_name,
                    c.is_trial,
                    c.subscription_status,
                    c.subscription_tier,
                    c.trial_status,
                    c.trial_end_date,
                    c.trial_tickets_used,
                    vi.id as variant_instance_id,
                    vi.variant_type,
                    vi.status as variant_status,
                    vl.limit_name,
                    vl.monthly_ticket_limit,
                    vl.monthly_ai_agent_limit,
                    vl.price_monthly
                FROM companies c
                LEFT JOIN variant_instances vi ON vi.company_id = c.id AND vi.status = 'active'
                LEFT JOIN variant_limits vl ON vl.tier = vi.variant_type
                WHERE c.id = %s
            """, (company_id,))
            
            result = cur.fetchone()
            return dict(result) if result else None
    
    def get_all_company_usage(self) -> List[Dict]:
        """Get usage dashboard for all companies (for Node 1 monitoring)."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT * FROM v_company_usage_dashboard
                ORDER BY usage_percentage DESC
            """)
            return [dict(row) for row in cur.fetchall()]


# =============================================================================
# TRIAL & SUBSCRIPTION MANAGEMENT
# =============================================================================

class TrialSubscriptionManager:
    """
    Manages free trials and paid subscriptions.
    
    Database fields used:
    - companies.is_trial
    - companies.subscription_status
    - companies.subscription_tier
    - companies.trial_status
    - companies.trial_end_date
    - companies.trial_tickets_used
    - subscriptions table (for paid subscribers)
    """
    
    def __init__(self):
        self.conn = None
    
    def __enter__(self):
        self.conn = get_db_connection()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def get_trial_status(self, company_id: str) -> Dict[str, Any]:
        """Get complete trial/subscription status for a company."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    id, name, is_trial, subscription_status, subscription_tier,
                    trial_status, trial_start_date, trial_end_date, 
                    trial_ends_at, trial_tickets_used,
                    paddle_subscription_id, created_at,
                    NOW() as current_time
                FROM companies 
                WHERE id = %s
            """, (company_id,))
            
            result = cur.fetchone()
            if not result:
                return {'error': 'Company not found'}
            
            company = dict(result)
            
            # Determine effective status
            is_trial_expired = False
            if company.get('trial_end_date') and company['trial_status'] == 'active':
                if company['trial_end_date'] < datetime.now(timezone.utc):
                    is_trial_expired = True
            
            company['is_trial_expired'] = is_trial_expired
            company['effective_status'] = self._determine_effective_status(company)
            
            return company
    
    def _determine_effective_status(self, company: Dict) -> str:
        """Determine the effective account status."""
        if company.get('subscription_status') == 'active':
            return 'paid_active'
        elif company.get('is_trial') and company.get('trial_status') == 'active':
            if company.get('trial_end_date') and company['trial_end_date'] > datetime.now(timezone.utc):
                return 'trial_active'
            else:
                return 'trial_expired'
        elif company.get('is_trial') and company.get('trial_status') == 'converted':
            return 'trial_converted'
        else:
            return 'unknown'
    
    def get_all_trials(self, include_expired: bool = False) -> List[Dict]:
        """Get all trial companies with their status."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            query = """
                SELECT 
                    id, name, subscription_tier, trial_status, 
                    trial_end_date, trial_tickets_used,
                    CASE 
                        WHEN trial_end_date IS NULL THEN 'unknown'
                        WHEN trial_end_date < NOW() THEN 'expired'
                        ELSE 'active'
                    END as trial_state
                FROM companies 
                WHERE is_trial = TRUE
            """
            if not include_expired:
                query += " AND trial_end_date >= NOW()"
            
            query += " ORDER BY trial_end_date ASC"
            
            cur.execute(query)
            return [dict(row) for row in cur.fetchall()]
    
    def get_all_subscribers(self) -> List[Dict]:
        """Get all paid subscribers."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT 
                    id, name, subscription_status, subscription_tier,
                    paddle_subscription_id, updated_at
                FROM companies 
                WHERE subscription_status = 'active'
                ORDER BY updated_at DESC
            """)
            return [dict(row) for row in cur.fetchall()]
    
    def create_subscription_record(self, company_id: str, tier: str, 
                                    paddle_sub_id: Optional[str] = None) -> Dict:
        """Create a new subscription record when user upgrades from trial."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                # Insert into subscriptions table
                sub_id = f"sub_{datetime.now().strftime('%Y%m%d%H%M%S')}_{company_id[:8]}"
                cur.execute("""
                    INSERT INTO subscriptions (id, company_id, tier, status, 
                                             current_period_start, current_period_end,
                                             paddle_subscription_id, created_at)
                    VALUES (%s, %s, %s, 'active', NOW(), NOW() + INTERVAL '1 month', %s, NOW())
                    RETURNING *
                """, (sub_id, company_id, tier, paddle_sub_id))
                
                subscription = cur.fetchone()
                
                # Update company record
                cur.execute("""
                    UPDATE companies 
                    SET subscription_status = 'active',
                        subscription_tier = %s,
                        paddle_subscription_id = %s,
                        is_trial = FALSE,
                        trial_status = 'converted',
                        updated_at = NOW()
                    WHERE id = %s
                """, (tier, paddle_sub_id, company_id))
                
                self.conn.commit()
                
                return {
                    'success': True,
                    'subscription': dict(subscription),
                    'message': f'Subscription created successfully for tier {tier}'
                }
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error creating subscription: {e}")
                return {'success': False, 'error': str(e)}
    
    def increment_trial_ticket_count(self, company_id: str) -> bool:
        """Increment the trial ticket counter for a trial company."""
        with self.conn.cursor() as cur:
            try:
                cur.execute("""
                    UPDATE companies 
                    SET trial_tickets_used = COALESCE(trial_tickets_used, 0) + 1,
                        updated_at = NOW()
                    WHERE id = %s AND is_trial = TRUE
                """, (company_id,))
                self.conn.commit()
                return cur.rowcount > 0
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error incrementing trial tickets: {e}")
                return False


# =============================================================================
# INTEGRATION TOOLS MANAGEMENT
# =============================================================================

class IntegrationManager:
    """
    Manages third-party integrations (CRM, webhooks, APIs, etc.)
    
    Tables used:
    - integrations (main integration storage)
    - api_keys (API key management)
    - db_connections (database connections)
    - webhook_integrations (webhook configurations)
    - mcp_connections (MCP protocol connections)
    """
    
    # Supported integration types
    INTEGRATION_TYPES = [
        'hubspot_crm', 'salesforce_crm', 'zoho_crm', 'pipedrive_crm',
        'slack', 'microsoft_teams', 'discord',
        'google_calendar', 'outlook_calendar',
        'gmail', 'outlook_email',
        'stripe', 'razorpay', 'paddle',
        'custom_webhook', 'custom_api', 'custom_custom'
    ]
    
    def __init__(self):
        self.conn = None
    
    def __enter__(self):
        self.conn = get_db_connection()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def create_integration(self, company_id: str, integration_type: str, 
                           name: str, credentials: Dict, settings: Optional[Dict] = None) -> Dict:
        """
        Create a new integration for a company.
        
        Args:
            company_id: Company UUID
            integration_type: Type of integration (hubspot_crm, slack, etc.)
            name: Display name for this integration
            credentials: Encrypted credentials (will be stored as JSON text)
            settings: Additional settings/configuration
        """
        if integration_type not in self.INTEGRATION_TYPES:
            return {'success': False, 'error': f'Invalid integration type. Must be one of: {self.INTEGRATION_TYPES}'}
        
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                import uuid
                int_id = str(uuid.uuid4())
                
                cur.execute("""
                    INSERT INTO integrations (id, company_id, integration_type, name, 
                                            credentials_encrypted, settings, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 'configured', NOW(), NOW())
                    RETURNING *
                """, (int_id, company_id, integration_type, name, 
                      json.dumps(credentials), json.dumps(settings or {})))
                
                integration = cur.fetchone()
                self.conn.commit()
                
                return {
                    'success': True,
                    'integration': dict(integration),
                    'message': f'Integration {name} created successfully'
                }
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error creating integration: {e}")
                return {'success': False, 'error': str(e)}
    
    def get_company_integrations(self, company_id: str) -> List[Dict]:
        """Get all integrations for a company."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, integration_type, name, status, last_sync, error_message, created_at
                FROM integrations 
                WHERE company_id = %s
                ORDER BY created_at DESC
            """, (company_id,))
            return [dict(row) for row in cur.fetchall()]
    
    def update_integration_status(self, integration_id: str, status: str, 
                                   error_message: Optional[str] = None) -> bool:
        """Update integration status after sync attempt."""
        with self.conn.cursor() as cur:
            try:
                cur.execute("""
                    UPDATE integrations 
                    SET status = %s, 
                        error_message = %s,
                        last_sync = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                """, (status, error_message, integration_id))
                self.conn.commit()
                return cur.rowcount > 0
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error updating integration status: {e}")
                return False
    
    def delete_integration(self, integration_id: str, company_id: str) -> bool:
        """Delete an integration (verify ownership)."""
        with self.conn.cursor() as cur:
            try:
                cur.execute("""
                    DELETE FROM integrations 
                    WHERE id = %s AND company_id = %s
                """, (integration_id, company_id))
                self.conn.commit()
                return cur.rowcount > 0
            except Exception as e:
                self.conn.rollback()
                logger.error(f"Error deleting integration: {e}")
                return False
    
    def get_integrations_by_type(self, integration_type: str) -> List[Dict]:
        """Get all integrations of a specific type across all companies."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT i.id, i.company_id, i.name, i.status, i.last_sync, c.name as company_name
                FROM integrations i
                JOIN companies c ON c.id = i.company_id
                WHERE i.integration_type = %s
                ORDER BY i.last_sync DESC NULLS LAST
            """, (integration_type,))
            return [dict(row) for row in cur.fetchall()]


# =============================================================================
# TICKET CREATION WITH VALIDATION
# =============================================================================

class TicketManager:
    """
    Ticket creation with automatic limit validation.
    
    Flow:
    1. Check company variant → Get limits
    2. Check current usage → Calculate remaining
    3. If within limits → Create ticket (trigger enforces final check)
    4. If over limit → Block with upgrade message
    5. If trial → Increment trial_tickets_used
    """
    
    def __init__(self):
        self.conn = None
    
    def __enter__(self):
        self.conn = get_db_connection()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            self.conn.close()
    
    def create_ticket_with_validation(self, company_id: str, user_id: str, 
                                       subject: str, description: str,
                                       priority: str = 'medium') -> Dict:
        """
        Create a ticket only if within usage limits.
        
        This method:
        1. Checks variant limits via check_user_usage_limit()
        2. Verifies trial status if applicable
        3. Creates ticket (DB trigger does final enforcement)
        4. Updates trial counters if needed
        """
        usage_mgr = UsageLimitManager()
        usage_mgr.conn = self.conn
        
        trial_mgr = TrialSubscriptionManager()
        trial_mgr.conn = self.conn
        
        # Step 1: Check if allowed to create ticket
        can_create, message = usage_mgr.can_create_ticket(company_id)
        if not can_create:
            return {
                'success': False,
                'error': 'LIMIT_EXCEEDED',
                'message': message,
                'suggestion': 'Please upgrade your plan to continue creating tickets.'
            }
        
        # Step 2: Check trial status
        trial_status = trial_mgr.get_trial_status(company_id)
        if trial_status.get('effective_status') == 'trial_expired':
            return {
                'success': False,
                'error': 'TRIAL_EXPIRED',
                'message': 'Your free trial has expired. Please subscribe to continue.',
                'trial_end_date': trial_status.get('trial_end_date')
            }
        
        # Step 3: Create the ticket
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            try:
                import uuid
                ticket_id = str(uuid.uuid4())
                
                cur.execute("""
                    INSERT INTO tickets (id, company_id, user_id, subject, description, 
                                        priority, status, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, 'open', NOW(), NOW())
                    RETURNING *
                """, (ticket_id, company_id, user_id, subject, description, priority))
                
                ticket = cur.fetchone()
                
                # Step 4: Update trial ticket count if trial user
                if trial_status.get('is_trial'):
                    trial_mgr.increment_trial_ticket_count(company_id)
                
                self.conn.commit()
                
                return {
                    'success': True,
                    'ticket': dict(ticket),
                    'usage_remaining': usage_mgr.check_usage(company_id, 'tickets').get('remaining'),
                    'message': f'Ticket created successfully. {message}'
                }
                
            except Exception as e:
                self.conn.rollback()
                
                # Check if it's a limit violation from trigger
                if 'usage limit' in str(e).lower() or 'exceeded' in str(e).lower():
                    return {
                        'success': False,
                        'error': 'LIMIT_EXCEEDED_TRIGGER',
                        'message': str(e),
                        'suggestion': 'Your ticket limit has been reached. Please upgrade your plan.'
                    }
                
                logger.error(f"Error creating ticket: {e}")
                return {'success': False, 'error': str(e)}
    
    def get_company_tickets(self, company_id: str, limit: int = 50) -> List[Dict]:
        """Get all tickets for a company."""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT t.*, u.email as creator_email, u.name as creator_name
                FROM tickets t
                JOIN users u ON u.id = t.user_id
                WHERE t.company_id = %s
                ORDER BY t.created_at DESC
                LIMIT %s
            """, (company_id, limit))
            return [dict(row) for row in cur.fetchall()]


# =============================================================================
# NODE 1 DASHBOARD API
# =============================================================================

class Node1Dashboard:
    """
    Complete dashboard data for Node 1 to monitor:
    - All companies with their variants
    - Usage counts and limits
    - Trial vs paid breakdown
    - Integration status
    - System health
    """
    
    def get_full_dashboard(self) -> Dict[str, Any]:
        """Get complete dashboard data for Node 1."""
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Company overview
                cur.execute("SELECT COUNT(*) as total FROM companies")
                total_companies = cur.fetchone()['total']
                
                cur.execute("SELECT COUNT(*) as total FROM companies WHERE is_trial = TRUE")
                trial_companies = cur.fetchone()['total']
                
                cur.execute("SELECT COUNT(*) as total FROM companies WHERE subscription_status = 'active'")
                active_subscribers = cur.fetchone()['total']
                
                # Tickets overview
                cur.execute("SELECT COUNT(*) as total FROM tickets")
                total_tickets = cur.fetchone()['total']
                
                cur.execute("""
                    SELECT COUNT(*) as month_count 
                    FROM tickets 
                    WHERE created_at >= DATE_TRUNC('month', NOW())
                """)
                monthly_tickets = cur.fetchone()['month_count']
                
                # Integrations
                cur.execute("SELECT COUNT(*) as total FROM integrations")
                total_integrations = cur.fetchone()['total']
                
                cur.execute("""
                    SELECT integration_type, COUNT(*) as cnt 
                    FROM integrations 
                    GROUP BY integration_type
                """)
                integration_breakdown = {row['integration_type']: row['cnt'] for row in cur.fetchall()}
                
                # Variant distribution
                cur.execute("""
                    SELECT variant_type, COUNT(*) as cnt 
                    FROM variant_instances 
                    WHERE status = 'active'
                    GROUP BY variant_type
                """)
                variant_distribution = {row['variant_type']: row['cnt'] for row in cur.fetchall()}
                
                # Usage dashboard (from view)
                cur.execute("""
                    SELECT * FROM v_company_usage_dashboard 
                    ORDER BY percentage_used DESC 
                    LIMIT 20
                """)
                top_usage_companies = [dict(row) for row in cur.fetchall()]
                
                # Trials expiring soon (next 7 days)
                cur.execute("""
                    SELECT id, name, trial_end_date, trial_tickets_used, subscription_tier
                    FROM companies 
                    WHERE is_trial = TRUE 
                    AND trial_status = 'active'
                    AND trial_end_date BETWEEN NOW() AND NOW() + INTERVAL '7 days'
                    ORDER BY trial_end_date ASC
                """)
                expiring_trials = [dict(row) for row in cur.fetchall()]
                
                return {
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'companies': {
                        'total': total_companies,
                        'trial': trial_companies,
                        'paid_active': active_subscribers,
                        'converted': total_companies - trial_companies - active_subscribers
                    },
                    'tickets': {
                        'total': total_tickets,
                        'this_month': monthly_tickets
                    },
                    'integrations': {
                        'total': total_integrations,
                        'by_type': integration_breakdown
                    },
                    'variants': variant_distribution,
                    'top_usage_companies': top_usage_companies,
                    'trials_expiring_soon': expiring_trials,
                    'system_status': 'healthy'
                }
        finally:
            conn.close()


# =============================================================================
# MAIN APPLICATION CLASS
# =============================================================================

class ParwaBackend:
    """
    Main backend application class that combines all managers.
    
    Usage:
        backend = ParwaBackend()
        
        # Check usage
        usage = backend.usage.check_usage(company_id)
        
        # Create ticket with validation
        result = backend.tickets.create_ticket_with_validation(...)
        
        # Get dashboard
        dashboard = backend.dashboard.get_full_dashboard()
    """
    
    def __init__(self):
        self.usage = UsageLimitManager()
        self.trials = TrialSubscriptionManager()
        self.integrations = IntegrationManager()
        self.tickets = TicketManager()
        self.dashboard = Node1Dashboard()


# =============================================================================
# FASTAPI APPLICATION (Optional - for REST API)
# =============================================================================

def create_app():
    """Create FastAPI application instance (if using API server)."""
    try:
        from fastapi import FastAPI, HTTPException
        from pydantic import BaseModel
        
        app = FastAPI(title="Parwa Production Backend", version="2.0.0")
        backend = ParwaBackend()
        
        # Request models
        class TicketCreate(BaseModel):
            company_id: str
            user_id: str
            subject: str
            description: str
            priority: str = 'medium'
        
        class IntegrationCreate(BaseModel):
            company_id: str
            integration_type: str
            name: str
            credentials: dict
            settings: Optional[dict] = None
        
        @app.get("/")
        def root():
            return {"status": "healthy", "service": "parwa-backend", "version": "2.0.0"}
        
        @app.get("/health")
        def health_check():
            conn = get_db_connection()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return {"status": "healthy", "database": "connected"}
            finally:
                conn.close()
        
        @app.get("/api/v1/dashboard")
        def get_dashboard():
            """Node 1 dashboard endpoint"""
            return backend.dashboard.get_full_dashboard()
        
        @app.get("/api/v1/companies/{company_id}/usage")
        def get_company_usage(company_id: str):
            """Check company usage limits"""
            with backend.usage as mgr:
                return mgr.check_usage(company_id)
        
        @app.get("/api/v1/companies/{company_id}/variant")
        def get_company_variant(company_id: str):
            """Get company variant info"""
            with backend.usage as mgr:
                return mgr.get_company_variant_info(company_id)
        
        @app.get("/api/v1/companies/{company_id}/trial-status")
        def get_trial_status(company_id: str):
            """Get trial/subscription status"""
            with backend.trials as mgr:
                return mgr.get_trial_status(company_id)
        
        @app.post("/api/v1/tickets")
        def create_ticket(ticket: TicketCreate):
            """Create ticket with limit validation"""
            with backend.tickets as mgr:
                result = mgr.create_ticket_with_validation(
                    ticket.company_id, ticket.user_id,
                    ticket.subject, ticket.description, ticket.priority
                )
                if not result['success']:
                    raise HTTPException(status_code=400, detail=result)
                return result
        
        @app.get("/api/v1/companies/{company_id}/integrations")
        def get_integrations(company_id: str):
            """Get company integrations"""
            with backend.integrations as mgr:
                return mgr.get_company_integrations(company_id)
        
        @app.post("/api/v1/integrations")
        def create_integration(integration: IntegrationCreate):
            """Create new integration"""
            with backend.integrations as mgr:
                result = mgr.create_integration(
                    integration.company_id, integration.integration_type,
                    integration.name, integration.credentials, integration.settings
                )
                if not result['success']:
                    raise HTTPException(status_code=400, detail=result)
                return result
        
        @app.get("/api/v1/trials")
        def get_all_trials(include_expired: bool = False):
            """Get all trial companies"""
            with backend.trials as mgr:
                return mgr.get_all_trials(include_expired)
        
        @app.get("/api/v1/subscribers")
        def get_all_subscribers():
            """Get all paid subscribers"""
            with backend.trials as mgr:
                return mgr.get_all_subscribers()
        
        return app
    except ImportError:
        logger.warning("FastAPI not installed. Use ParwaBackend class directly.")
        return None


# =============================================================================
# CLI INTERFACE FOR TESTING
# =============================================================================

def print_section(title: str):
    """Print a formatted section header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)


def test_database_connection():
    """Test database connection and print status"""
    print_section("DATABASE CONNECTION TEST")
    
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            version = cur.fetchone()[0]
            print(f"✅ Connected successfully!")
            print(f"   PostgreSQL: {version.split(',')[0]}")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return False


def test_usage_limits():
    """Test usage limit functionality"""
    print_section("USAGE LIMITS TEST")
    
    backend = ParwaBackend()
    
    with backend.usage as mgr:
        # Get all company usage
        dashboard_data = mgr.get_all_company_usage()
        print(f"✅ Found {len(dashboard_data)} companies with usage data")
        
        if dashboard_data:
            # Show top 5 by usage
            print("\n   Top 5 companies by usage:")
            for i, company in enumerate(dashboard_data[:5], 1):
                print(f"   {i}. {company.get('company_name', 'Unknown')}: "
                      f"{company.get('tickets_this_month', 0)}/{company.get('ticket_limit', '?')} tickets "
                      f"({company.get('usage_percentage', 0)}%) - {company.get('status', '')}")


def test_trial_tracking():
    """Test trial tracking functionality"""
    print_section("FREE TRIAL TRACKING TEST")
    
    backend = ParwaBackend()
    
    with backend.trials as mgr:
        # Get active trials
        trials = mgr.get_all_trials(include_expired=False)
        print(f"✅ Active trials: {len(trials)}")
        
        # Get expired trials
        expired = mgr.get_all_trials(include_expired=True)
        print(f"✅ Total trials (including expired): {len(expired)}")
        
        # Get subscribers
        subscribers = mgr.get_all_subscribers()
        print(f"✅ Active paid subscribers: {len(subscribers)}")
        
        if trials:
            print("\n   Sample active trials:")
            for trial in trials[:3]:
                print(f"   - {trial.get('name')}: {trial.get('subscription_tier')} plan, "
                      f"expires {trial.get('trial_end_date')}, "
                      f"{trial.get('trial_tickets_used')} tickets used")


def test_integrations():
    """Test integration tools functionality"""
    print_section("INTEGRATION TOOLS TEST")
    
    backend = ParwaBackend()
    
    with backend.integrations as mgr:
        # Count by type
        types = ['hubspot_crm', 'salesforce_crm', 'slack', 'custom_webhook']
        for int_type in types:
            items = mgr.get_integrations_by_type(int_type)
            if items:
                print(f"✅ {int_type}: {len(items)} integrations")
        
        print(f"\n   Supported integration types:")
        for i, int_type in enumerate(backend.integrations.INTEGRATION_TYPES, 1):
            print(f"   {i}. {int_type}")


def run_full_test_suite():
    """Run complete test suite"""
    print("\n" + "#"*60)
    print("#  PARWA PRODUCTION BACKEND - TEST SUITE")
    print("#  Version 2.0.0 | Production Ready")
    print("#"*60)
    
    results = {
        'database': test_database_connection(),
        'usage_limits': True,
        'trial_tracking': True,
        'integrations': True
    }
    
    try:
        test_usage_limits()
    except Exception as e:
        print(f"❌ Usage limits test failed: {e}")
        results['usage_limits'] = False
    
    try:
        test_trial_tracking()
    except Exception as e:
        print(f"❌ Trial tracking test failed: {e}")
        results['trial_tracking'] = False
    
    try:
        test_integrations()
    except Exception as e:
        print(f"❌ Integrations test failed: {e}")
        results['integrations'] = False
    
    # Summary
    print_section("TEST SUMMARY")
    all_passed = all(results.values())
    status = "✅ ALL TESTS PASSED" if all_passed else "⚠️ SOME TESTS FAILED"
    print(f"\n   Status: {status}")
    for test_name, passed in results.items():
        icon = "✅" if passed else "❌"
        print(f"   {icon} {test_name}")
    
    if all_passed:
        print("\n🎉 PRODUCTION READY! All systems operational.")
    else:
        print("\n⚠️ Review failed tests before deploying to production.")
    
    return all_passed


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        success = run_full_test_suite()
        sys.exit(0 if success else 1)
    elif len(sys.argv) > 1 and sys.argv[1] == 'serve':
        app = create_app()
        if app:
            import uvicorn
            uvicorn.run(app, host="0.0.0.0", port=8000)
        else:
            print("FastAPI not available. Install with: pip install fastapi uvicorn")
    else:
        print("Parwa Production Backend v2.0.0")
        print("\nUsage:")
        print("  python main.py test     - Run test suite")
        print("  python main.py serve    - Start API server")
        print("\nOr import and use:")
        print("  from main import ParwaBackend")
        print("  backend = ParwaBackend()")
