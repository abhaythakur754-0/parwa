"""
PARWA Universal Payment Service

Abstracts payment providers (Paddle/Stripe/Razorpay) for the $1 Demo Pack.
Supports multiple providers with a unified interface.
"""

import uuid
from typing import Any, Dict, Optional
from datetime import datetime


class PaymentProvider:
    """Base class for payment providers."""
    
    def __init__(self, name: str, api_key: Optional[str] = None):
        self.name = name
        self.api_key = api_key
    
    async def create_checkout(
        self,
        amount: float,
        currency: str,
        product_name: str,
        return_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a checkout session."""
        raise NotImplementedError
    
    async def verify_payment(self, transaction_id: str) -> Dict[str, Any]:
        """Verify a payment status."""
        raise NotImplementedError


class PaddleProvider(PaymentProvider):
    """Paddle payment provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__('paddle', api_key)
    
    async def create_checkout(
        self,
        amount: float,
        currency: str,
        product_name: str,
        return_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        transaction_id = f"paddle_{uuid.uuid4().hex[:8]}"
        
        # In production, this would call the Paddle API
        # For demo, return a simulated checkout URL
        return {
            'checkout_url': f'https://buy.paddle.com/checkout/{transaction_id}',
            'transaction_id': transaction_id,
            'provider': 'paddle',
            'status': 'pending',
            'amount': str(amount),
            'currency': currency,
        }
    
    async def verify_payment(self, transaction_id: str) -> Dict[str, Any]:
        # In production, verify with Paddle API
        return {
            'transaction_id': transaction_id,
            'status': 'completed',
            'provider': 'paddle',
        }


class StripeProvider(PaymentProvider):
    """Stripe payment provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__('stripe', api_key)
    
    async def create_checkout(
        self,
        amount: float,
        currency: str,
        product_name: str,
        return_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        transaction_id = f"stripe_{uuid.uuid4().hex[:8]}"
        
        return {
            'checkout_url': f'https://checkout.stripe.com/pay/{transaction_id}',
            'transaction_id': transaction_id,
            'provider': 'stripe',
            'status': 'pending',
            'amount': str(amount),
            'currency': currency,
        }
    
    async def verify_payment(self, transaction_id: str) -> Dict[str, Any]:
        return {
            'transaction_id': transaction_id,
            'status': 'completed',
            'provider': 'stripe',
        }


class RazorpayProvider(PaymentProvider):
    """Razorpay payment provider."""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__('razorpay', api_key)
    
    async def create_checkout(
        self,
        amount: float,
        currency: str,
        product_name: str,
        return_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        transaction_id = f"rzp_{uuid.uuid4().hex[:8]}"
        
        return {
            'checkout_url': f'https://checkout.razorpay.com/v1/checkout/{transaction_id}',
            'transaction_id': transaction_id,
            'provider': 'razorpay',
            'status': 'pending',
            'amount': str(amount),
            'currency': currency,
        }
    
    async def verify_payment(self, transaction_id: str) -> Dict[str, Any]:
        return {
            'transaction_id': transaction_id,
            'status': 'completed',
            'provider': 'razorpay',
        }


class UniversalPaymentService:
    """
    Universal payment service that abstracts multiple providers.
    Routes to the appropriate provider based on configuration.
    """
    
    PROVIDERS = {
        'paddle': PaddleProvider,
        'stripe': StripeProvider,
        'razorpay': RazorpayProvider,
    }
    
    def __init__(self, default_provider: str = 'paddle'):
        self.default_provider = default_provider
        self._providers: Dict[str, PaymentProvider] = {}
    
    def get_provider(self, provider_name: Optional[str] = None) -> PaymentProvider:
        """Get a payment provider instance."""
        name = provider_name or self.default_provider
        
        if name not in self._providers:
            provider_class = self.PROVIDERS.get(name)
            if not provider_class:
                raise ValueError(f"Unknown payment provider: {name}")
            self._providers[name] = provider_class()
        
        return self._providers[name]
    
    async def create_demo_pack_payment(
        self,
        provider: Optional[str] = None,
        variant_id: Optional[str] = None,
        industry: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a $1 Demo Pack payment checkout.
        
        Args:
            provider: Payment provider name
            variant_id: Variant ID for metadata
            industry: Industry for metadata
        
        Returns:
            Payment checkout response
        """
        p = self.get_provider(provider)
        
        return await p.create_checkout(
            amount=1.00,
            currency='USD',
            product_name='PARWA $1 Demo Pack',
            metadata={
                'variant_id': variant_id or 'demo',
                'industry': industry or 'general',
                'pack_type': 'demo',
            },
        )
    
    async def verify_payment(
        self,
        transaction_id: str,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Verify a payment status."""
        p = self.get_provider(provider)
        return await p.verify_payment(transaction_id)


# Singleton instance
payment_service = UniversalPaymentService()
