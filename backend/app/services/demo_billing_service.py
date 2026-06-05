"""
PARWA Demo Billing Service

Per-ticket cost breakdown, ROI calculations, and monthly estimates
for the $1 Demo Pack.
"""

from typing import Any, Dict, List, Optional


# Plan pricing
PLAN_PRICES = {
    'starter': 999,
    'growth': 2499,
    'high': 3999,
}

# Agents per plan
AGENTS_PER_PLAN = {
    'starter': 3,
    'growth': 8,
    'high': 15,
}

# Average human agent cost per month (US market)
HUMAN_AGENT_COST = 4500

# Overage rate per ticket
OVERAGE_RATE = 0.10

# Tax rate
TAX_RATE = 0.08

# Annual discount
ANNUAL_DISCOUNT = 0.15


class DemoBillingService:
    """Service for demo billing calculations."""
    
    def calculate_bill(
        self,
        tier: str,
        industry: str,
        ticket_volume: int = 1000,
    ) -> Dict[str, Any]:
        """
        Calculate a detailed bill summary for a given tier and volume.
        
        Args:
            tier: 'starter', 'growth', or 'high'
            industry: Target industry
            ticket_volume: Monthly ticket volume
        
        Returns:
            Bill summary dict with items, totals, ROI
        """
        plan_price = PLAN_PRICES.get(tier, 999)
        agents_count = AGENTS_PER_PLAN.get(tier, 3)
        human_cost = HUMAN_AGENT_COST * agents_count
        
        # Ticket limits per plan
        ticket_limits = {'starter': 1000, 'growth': 5000, 'high': 15000}
        ticket_limit = ticket_limits.get(tier, 1000)
        
        # Build line items
        items = [
            {
                'name': f'PARWA {tier.capitalize()} Plan',
                'type': 'plan',
                'unit_price': plan_price,
                'quantity': 1,
                'total': plan_price,
                'description': f'{agents_count} AI agents, {ticket_limit:,} tickets/month',
            }
        ]
        
        # Calculate overages
        overage_tickets = max(0, ticket_volume - ticket_limit)
        overage_cost = round(overage_tickets * OVERAGE_RATE, 2)
        
        if overage_cost > 0:
            items.append({
                'name': 'Ticket Overage',
                'type': 'overage',
                'unit_price': OVERAGE_RATE,
                'quantity': overage_tickets,
                'total': overage_cost,
                'description': f'{overage_tickets:,} tickets over plan limit',
            })
        
        # Calculate totals
        subtotal = sum(item['total'] for item in items)
        tax = round(subtotal * TAX_RATE, 2)
        total = round(subtotal + tax, 2)
        
        # ROI calculations
        savings_vs_human = round(human_cost - total, 2)
        savings_percentage = round((savings_vs_human / human_cost) * 100) if human_cost > 0 else 0
        roi_months = round(total / savings_vs_human, 1) if savings_vs_human > 0 else float('inf')
        
        # Annual estimate with discount
        annual_estimate = round(total * 12 * (1 - ANNUAL_DISCOUNT), 2)
        
        return {
            'items': items,
            'subtotal': subtotal,
            'tax': tax,
            'total': total,
            'currency': 'USD',
            'billing_cycle': 'monthly',
            'savings_vs_human': savings_vs_human,
            'savings_percentage': savings_percentage,
            'roi_months': roi_months,
            'monthly_estimate': total,
            'annual_estimate': annual_estimate,
        }
    
    def get_per_ticket_cost(
        self,
        tier: str,
        ticket_volume: int = 1000,
    ) -> Dict[str, Any]:
        """
        Calculate per-ticket cost breakdown.
        """
        bill = self.calculate_bill(tier, 'general', ticket_volume)
        total = bill['total']
        per_ticket = round(total / ticket_volume, 4) if ticket_volume > 0 else 0
        
        # Human agent per-ticket cost
        agents = AGENTS_PER_PLAN.get(tier, 3)
        human_monthly = HUMAN_AGENT_COST * agents
        human_per_ticket = round(human_monthly / ticket_volume, 4) if ticket_volume > 0 else 0
        
        return {
            'tier': tier,
            'ticket_volume': ticket_volume,
            'parwa_per_ticket': per_ticket,
            'human_per_ticket': human_per_ticket,
            'savings_per_ticket': round(human_per_ticket - per_ticket, 4),
            'savings_percentage': round(((human_per_ticket - per_ticket) / human_per_ticket) * 100, 1) if human_per_ticket > 0 else 0,
        }
    
    def get_roi_projection(
        self,
        tier: str,
        industry: str,
        current_monthly_cost: float,
        ticket_volume: int = 1000,
    ) -> Dict[str, Any]:
        """
        Project ROI based on current costs.
        """
        bill = self.calculate_bill(tier, industry, ticket_volume)
        monthly_savings = round(current_monthly_cost - bill['total'], 2)
        annual_savings = round(monthly_savings * 12, 2)
        payback_months = round(bill['total'] / monthly_savings, 1) if monthly_savings > 0 else float('inf')
        
        return {
            'current_monthly_cost': current_monthly_cost,
            'parwa_monthly_cost': bill['total'],
            'monthly_savings': monthly_savings,
            'annual_savings': annual_savings,
            'payback_months': payback_months,
            'three_year_savings': round(annual_savings * 3, 2),
            'bill_summary': bill,
        }


# Singleton instance
demo_billing_service = DemoBillingService()
