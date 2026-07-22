/**
 * FlexPay Create Plan API Endpoint
 * ═══════════════════════════════════════════════════════════════════
 *
 * POST /api/flexpay/create-plan
 *
 * Creates a new FlexPay installment plan for a subscription.
 * Validates input, generates schedule, and registers with scheduler.
 *
 * Request Body:
 * {
 *   companyId: string,
 *   tier: 'mini' | 'parwa' | 'high',
 *   totalAmount: number, (optional, defaults from tier)
 *   startDate?: string (ISO date, optional, defaults to now)
 *   customerEmail?: string,
 *   customerName?: string
 * }
 *
 * Response:
 * {
 *   success: true,
 *   plan: FlexPayPlan,
 *   scheduleSummary: string
 * }
 */

import { NextRequest, NextResponse } from 'next/server';
import { 
  createFlexPayPlan, 
  validateTransactionAmount,
  TIER_PRICES,
  type VariantTier,
  type FlexPayPlan 
} from '@/lib/flexpay/core';
import { registerPlan } from '@/lib/flexpay/scheduler';
import { randomUUID } from 'crypto';

// ── Types ──────────────────────────────────────────────────────────

interface CreatePlanRequest {
  companyId: string;
  tier: VariantTier;
  totalAmount?: number;
  startDate?: string;
  customerEmail?: string;
  customerName?: string;
}

// ── Validation ─────────────────────────────────────────────────────

function validateCreatePlanRequest(body: Partial<CreatePlanRequest>): { valid: boolean; errors: string[] } {
  const errors: string[] = [];

  if (!body.companyId || body.companyId.trim().length === 0) {
    errors.push('companyId is required');
  }

  if (!body.tier || !['mini', 'parwa', 'high'].includes(body.tier)) {
    errors.push('tier must be one of: mini, parwa, high');
  }

  if (body.totalAmount !== undefined && body.totalAmount <= 0) {
    errors.push('totalAmount must be greater than zero');
  }

  if (body.startDate) {
    const date = new Date(body.startDate);
    if (isNaN(date.getTime())) {
      errors.push('startDate must be a valid ISO date string');
    }
  }

  return { valid: errors.length === 0, errors };
}

// ── Handler ────────────────────────────────────────────────────────

export async function POST(req: NextRequest) {
  try {
    // Parse request body
    let body: CreatePlanRequest;
    try {
      body = await req.json();
    } catch {
      return NextResponse.json(
        { success: false, error: 'Invalid JSON in request body' },
        { status: 400 }
      );
    }

    // Validate request
    const validation = validateCreatePlanRequest(body);
    if (!validation.valid) {
      return NextResponse.json(
        { success: false, error: 'Validation failed', details: validation.errors },
        { status: 400 }
      );
    }

    // Determine amount (use provided or default from tier)
    const totalAmount = body.totalAmount ?? TIER_PRICES[body.tier as VariantTier];

    // Validate transaction amounts are safe for Razorpay
    const baseValidation = validateTransactionAmount(100); // Base daily amount
    if (!baseValidation.valid) {
      return NextResponse.json(
        { success: false, error: 'System configuration error: Base amount exceeds limits' },
        { status: 500 }
      );
    }

    // Generate unique plan ID
    const planId = `flexpay_${randomUUID().replace(/-/g, '').substring(0, 12)}`;

    // Parse start date or use now
    const startDate = body.startDate ? new Date(body.startDate) : new Date();

    // Create the plan
    const plan = createFlexPayPlan({
      id: planId,
      companyId: body.companyId,
      tier: body.tier as VariantTier,
      totalAmount,
      startDate,
    });

    // Register with scheduler for automatic processing
    registerPlan(plan);

    // Log creation (in production, this would go to your logging system)
    console.log(`[FlexPay/API] Created plan ${planId} for company ${body.companyId}`, {
      tier: body.tier,
      totalAmount,
      totalDays: plan.totalDays,
      customerEmail: body.customerEmail,
    });

    // Return success response
    return NextResponse.json({
      success: true,
      plan: {
        ...plan,
        createdAt: plan.createdAt.toISOString(),
        startDate: plan.startDate.toISOString(),
        expectedCompletionDate: plan.expectedCompletionDate.toISOString(),
      },
      message: `FlexPay plan created successfully. ${plan.totalDays} installments starting ${startDate.toLocaleDateString()}`,
    });

  } catch (error) {
    console.error('[FlexPay/API] Error creating plan:', error);
    
    const message = error instanceof Error ? error.message : 'Unknown error occurred';
    
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to create FlexPay plan',
        details: message 
      },
      { status: 500 }
    );
  }
}

// ── Optional: GET to list plans (for admin) ───────────────────────

export async function GET() {
  try {
    const { getRegisteredPlans, getSchedulerStats } = await import('@/lib/flexpay/scheduler');
    
    const plans = getRegisteredPlans();
    const stats = getSchedulerStats();

    return NextResponse.json({
      success: true,
      stats,
      plans: plans.map(p => ({
        id: p.id,
        companyId: p.companyId,
        tier: p.tier,
        status: p.status,
        totalAmount: p.totalAmount,
        totalDays: p.totalDays,
        currentDay: Math.floor((Date.now() - new Date(p.startDate).getTime()) / (1000 * 60 * 60 * 24)) + 1,
        progress: `${Math.min(100, Math.round(((Date.now() - new Date(p.startDate).getTime()) / (1000 * 60 * 60 * 24)) / p.totalDays * 100))}%`,
      })),
    });
  } catch (error) {
    console.error('[FlexPay/API] Error listing plans:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to list plans' },
      { status: 500 }
    );
  }
}
