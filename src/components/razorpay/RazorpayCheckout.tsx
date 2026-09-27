'use client';

import React, { useState } from 'react';
import { Loader2, CreditCard, Zap } from 'lucide-react';
import { toast } from 'sonner';

interface RazorpayCheckoutProps {
  amount: number; // in dollars (e.g., 999 for $999 USD)
  currency?: string;
  name?: string;
  description?: string;
  onSuccess?: (paymentId: string, orderId: string) => void;
  buttonText?: string;
  disabled?: boolean;
  
  // ── FlexPay Props ──
  /** Enable FlexPay mode (tokenization for recurring charges) */
  isFlexPayMode?: boolean;
  /** Company ID for FlexPay */
  companyId?: string;
  /** Subscription tier for FlexPay */
  tier?: 'parwa' | 'high';
  /** Total subscription amount for FlexPay plan */
  totalAmount?: number;
  /** Plan ID if already created */
  planId?: string;
  /** Customer email for tokenization */
  customerEmail?: string;
  /** Customer name for tokenization */
  customerName?: string;
  /** Callback after successful tokenization */
  onTokenizationComplete?: (tokenData: {
    token: string;
    last4: string;
    cardNetwork: string;
  }) => void;
}

// Razorpay checkout types
declare global {
  interface Window {
    Razorpay?: any;
  }
}

export function RazorpayCheckout({
  amount,
  currency = 'USD',
  name = 'PARWA',
  description = 'Subscription Payment',
  onSuccess,
  buttonText = 'Pay Now',
  disabled = false,
  
  // FlexPay props
  isFlexPayMode = false,
  companyId,
  tier = 'high',
  totalAmount,
  planId,
  customerEmail,
  customerName,
  onTokenizationComplete,
}: RazorpayCheckoutProps) {
  const [loading, setLoading] = useState(false);

  const handlePayment = async () => {
    // Try to get key from env first, then fallback to API
    let keyId = process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;
    
    setLoading(true);

    try {
      // ── FLEXPAY MODE: Tokenization Flow ──
      if (isFlexPayMode && companyId && totalAmount) {
        // For FlexPay, get the key from the create-order endpoint
        // (which already returns key_id alongside the order)
        if (!keyId) {
          // Create an order first (this also returns key_id)
          const orderRes = await fetch('/api/razorpay/create-order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
              amount: Math.round(amount * 100), // $100 → 10000 cents
              currency,
              receipt: `flexpay_${Date.now()}`,
              plan_id: planId,
              plan_name: `${name} — FlexPay Day 1`,
            }),
          });
          if (orderRes.ok) {
            const orderData = await orderRes.json();
            keyId = orderData.key_id;
            if (!keyId) throw new Error('Razorpay key not returned by server');
            // Open checkout with the created order
            await loadRazorpayScript();
            const options = {
              key: keyId,
              amount: orderData.amount,
              currency: orderData.currency,
              order_id: orderData.id,
              name,
              description,
              method: {
                card: true,        // Credit/Debit cards only
                upi: false,        // No UPI (US customers)
                wallet: false,     // No wallets
                netbanking: false,  // No netbanking
                bank_transfer: false,
              },
              prefill: {
                email: customerEmail,
                name: customerName,
              },
              theme: { color: '#10b981' },
              handler: async (response: any) => {
                // Verify the payment
                const verifyRes = await fetch('/api/razorpay/verify-payment', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  credentials: 'include',
                  body: JSON.stringify({
                    razorpay_order_id: response.razorpay_order_id,
                    razorpay_payment_id: response.razorpay_payment_id,
                    razorpay_signature: response.razorpay_signature,
                    plan_id: planId,
                    plan_name: name,
                    amount: orderData.amount,
                  }),
                });
                if (verifyRes.ok) {
                  toast.success('Payment successful! FlexPay activated.');
                  onSuccess?.();
                } else {
                  toast.error('Payment verification failed');
                }
              },
              modal: {
                ondismiss: () => {
                  setLoading(false);
                },
              },
            };
            const rzp = new window.Razorpay(options);
            rzp.open();
            return;
          } else {
            throw new Error('Failed to create order for FlexPay');
          }
        }
        if (!keyId) throw new Error('Razorpay not configured');
        await handleFlexPayTokenization(keyId);
        return;
      }

      // ── STANDARD MODE: Regular Payment Flow ──
      await handleStandardPayment();

    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Payment failed');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Handle standard one-time payment flow.
   */
  const handleStandardPayment = async () => {
    // Step 1: Create order via backend (API returns key_id)
    const orderRes = await fetch('/api/razorpay/create-order', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        amount: Math.round(amount * 100), // Convert to cents (for USD)
        currency,
        receipt: `parwa_${Date.now()}`,
      }),
    });

    if (!orderRes.ok) {
      const err = await orderRes.json().catch(() => ({}));
      throw new Error(err.detail || err.message || `Failed to create order (${orderRes.status})`);
    }

    const order = await orderRes.json();
    
    // Use key from API response or fallback to env
    const keyId = order.key_id || process.env.NEXT_PUBLIC_RAZORPAY_KEY_ID;
    if (!keyId) {
      throw new Error('Razorpay key not available');
    }

    // Step 2: Load Razorpay checkout script
    await loadRazorpayScript();

    // Step 3: Open checkout
    const options = {
      key: keyId,
      amount: order.amount,
      currency: order.currency,
      order_id: order.order_id,
      name,
      description,
      method: {
        card: true,        // Credit/Debit cards only
        upi: false,        // No UPI (US customers)
        wallet: false,     // No wallets
        netbanking: false,  // No netbanking
        bank_transfer: false,
      },
      handler: async function (response: any) {
        // Step 4: Verify payment signature
        try {
          const verifyRes = await fetch('/api/razorpay/verify-payment', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            }),
          });

          if (verifyRes.ok) {
            toast.success('Payment successful!');
            if (onSuccess) {
              onSuccess(response.razorpay_payment_id, response.razorpay_order_id);
            }
          } else {
            const err = await verifyRes.json().catch(() => ({}));
            toast.error(`Payment verification failed: ${err.detail || 'Unknown error'}`);
          }
        } catch (err) {
          toast.error('Payment verification failed');
        }
      },
      modal: {
        ondismiss: function () {
          toast('Payment cancelled', { icon: 'ℹ️' });
        },
      },
      theme: {
        color: '#f97316',
      },
    };

    const rzp = new window.Razorpay(options);
    rzp.on('payment.failed', function (response: any) {
      toast.error(`Payment failed: ${response.error?.description || 'Unknown error'}`);
    });
    rzp.open();
  };

  /**
   * Handle FlexPay tokenization flow for recurring charges.
   */
  const handleFlexPayTokenization = async (keyId: string) => {
    if (!customerEmail || !customerName) {
      throw new Error('Customer email and name required for FlexPay mode');
    }

    // Step 1: Initiate tokenization via backend
    const tokenizeRes = await fetch('/api/flexpay/tokenize', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        companyId,
        email: customerEmail,
        name: customerName,
        tier,
        totalAmount: totalAmount || amount,
        planId: planId || '',
      }),
    });

    if (!tokenizeRes.ok) {
      const err = await tokenizeRes.json().catch(() => ({}));
      throw new Error(err.error || `Failed to initiate tokenization (${tokenizeRes.status})`);
    }

    const tokenizeData = await tokenizeRes.json();

    if (!tokenizeData.needsCheckout || !tokenizeData.checkoutOptions) {
      throw new Error('Invalid tokenization response from server');
    }

    // Step 2: Load Razorpay checkout script
    await loadRazorpayScript();

    // Step 3: Open checkout with tokenization options
    const options = {
      key: keyId,
      amount: tokenizeData.checkoutOptions.amount, // $100 in INR paise
      currency: tokenizeData.checkoutOptions.currency,
      name: tokenizeData.checkoutOptions.name,
      description: tokenizeData.checkoutOptions.description,
      notes: tokenizeData.checkoutOptions.notes,
      theme: tokenizeData.checkoutOptions.theme,
      
      // CRITICAL: Configure for international cards and tokenization
      config: {
        display: {
          blocks: {
            utop: {
              // Hide UPI - international customers use credit cards
              name: '',
              instruments: [],
            },
          },
          sequence: ['block.card'],
          preferences: {
            show_default_blocks: true,
          },
        },
      },
      
      // Modal settings
      modal: {
        confirm_close: true,
        ondismiss: function () {
          toast('Payment cancelled. Your card was not saved.', { icon: 'ℹ️' });
        },
      },
      
      // Handler for successful payment + tokenization
      handler: async function (response: any) {
        try {
          // Send token data back to server to save
          const saveRes = await fetch('/api/flexpay/tokenize', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
              companyId,
              email: customerEmail,
              name: customerName,
              tier,
              totalAmount: totalAmount || amount,
              planId: planId || '',
              razorpayPaymentId: response.razorpay_payment_id,
              razorpayOrderId: response.razorpay_order_id,
              razorpaySignature: response.razorpay_signature,
            }),
          });

          if (!saveRes.ok) {
            const err = await saveRes.json().catch(() => ({}));
            throw new Error(err.error || 'Failed to save payment method');
          }

          const saveData = await saveRes.json();

          if (saveData.success && saveData.tokenizationResult) {
            toast.success('Card saved! Your FlexPay plan is now active.');
            
            if (onSuccess) {
              onSuccess(response.razorpay_payment_id, response.razorpay_order_id);
            }
            
            if (onTokenizationComplete) {
              onTokenizationComplete(saveData.tokenizationResult);
            }
          } else {
            throw new Error(saveData.error || 'Failed to complete tokenization');
          }
        } catch (err) {
          toast.error(err instanceof Error ? err.message : 'Tokenization failed');
        }
      },
    };

    const rzp = new window.Razorpay(options);
    
    rzp.on('payment.failed', function (response: any) {
      const errorMsg = response.error?.description || 'Payment failed';
      toast.error(`${errorMsg}. Please try again.`);
    });
    
    rzp.open();
  };

  /**
   * Load Razorpay checkout script dynamically.
   */
  const loadRazorpayScript = (): Promise<void> => {
    return new Promise((resolve, reject) => {
      if (window.Razorpay) {
        resolve();
        return;
      }

      const script = document.createElement('script');
      script.src = 'https://checkout.razorpay.com/v1/checkout.js';
      script.async = true;
      
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Failed to load Razorpay checkout'));
      
      document.body.appendChild(script);
    });
  };

  return (
    <button
      onClick={handlePayment}
      disabled={disabled || loading}
      className={`flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-bold shadow-lg hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
        isFlexPayMode 
          ? 'bg-gradient-to-r from-emerald-500 to-teal-400 text-white shadow-emerald-500/20 hover:shadow-emerald-500/30'
          : 'bg-gradient-to-r from-orange-500 to-amber-400 text-[#1A1A1A] shadow-orange-500/20 hover:shadow-orange-500/30'
      }`}
    >
      {loading ? (
        <>
          <Loader2 className="w-4 h-4 animate-spin" />
          {isFlexPayMode ? 'Setting up...' : 'Creating order...'}
        </>
      ) : (
        <>
          {isFlexPayMode ? (
            <Zap className="w-4 h-4" />
          ) : (
            <CreditCard className="w-4 h-4" />
          )}
          {buttonText}
        </>
      )}
    </button>
  );
}

/**
 * FlexPay-specific checkout component wrapper.
 * Simplified API for FlexPay integration.
 */
export function FlexPayCheckoutButton(props: {
  companyId: string;
  tier: 'parwa' | 'high';
  totalAmount: number;
  customerEmail: string;
  customerName: string;
  planId?: string;
  onPlanActivated?: (planId: string) => void;
  disabled?: boolean;
}) {
  return (
    <RazorpayCheckout
      amount={100} // First installment ($100)
      isFlexPayMode={true}
      companyId={props.companyId}
      tier={props.tier}
      totalAmount={props.totalAmount}
      planId={props.planId}
      customerEmail={props.customerEmail}
      customerName={props.customerName}
      buttonText="Activate FlexPay Plan"
      disabled={props.disabled}
      onSuccess={(paymentId, orderId) => {
        console.log('[FlexPay] Payment successful:', { paymentId, orderId });
        props.onPlanActivated?.(props.planId || '');
      }}
      onTokenizationComplete={(tokenData) => {
        console.log('[FlexPay] Token saved:', tokenData);
      }}
    />
  );
}
