/**
 * PARWA Demo Session API
 *
 * POST /api/demo/session — Create a new demo session
 * GET  /api/demo/session — Get existing demo session
 */

import { NextRequest, NextResponse } from 'next/server';

// Inline the needed functions to avoid import chain issues
const PLAN_PRICES: Record<string, number> = { starter: 999, growth: 2499, high: 3999 };
const HUMAN_AGENT_COST = 4500;
const AGENTS_PER_PLAN: Record<string, number> = { starter: 3, growth: 8, high: 15 };

const DEMO_VARIANTS = [
  { id: 'starter', name: 'PARWA Starter', tier: 'starter' },
  { id: 'growth', name: 'PARWA Growth', tier: 'growth' },
  { id: 'high', name: 'PARWA High', tier: 'high' },
];

function generateId(prefix: string = 'demo'): string {
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

// In-memory store (shared within this route only)
const sessions = new Map();

function calculateBillSummary(tier: string, industry: string, ticketVolume: number = 1000) {
  const planPrice = PLAN_PRICES[tier] || 999;
  const agentsCount = AGENTS_PER_PLAN[tier] || 3;
  const humanCost = HUMAN_AGENT_COST * agentsCount;
  const overageTickets = Math.max(0, ticketVolume - (tier === 'starter' ? 1000 : tier === 'growth' ? 5000 : 15000));
  const overageCost = overageTickets * 0.10;

  const items = [
    {
      name: `PARWA ${tier.charAt(0).toUpperCase() + tier.slice(1)} Plan`,
      type: 'plan',
      unit_price: planPrice,
      quantity: 1,
      total: planPrice,
      description: `${agentsCount} AI agents`,
    },
  ];

  if (overageCost > 0) {
    items.push({
      name: 'Ticket Overage',
      type: 'overage',
      unit_price: 0.10,
      quantity: overageTickets,
      total: Math.round(overageCost * 100) / 100,
      description: `${overageTickets} tickets over limit`,
    });
  }

  const subtotal = items.reduce((sum: number, i: { total: number }) => sum + i.total, 0);
  const tax = Math.round(subtotal * 0.08 * 100) / 100;
  const total = subtotal + tax;
  const savingsVsHuman = humanCost - total;
  const savingsPercentage = Math.round((savingsVsHuman / humanCost) * 100);
  const roiMonths = savingsVsHuman > 0 ? Math.round((total / savingsVsHuman) * 10) / 10 : 99;

  return {
    items,
    subtotal,
    tax,
    total,
    currency: 'USD',
    billing_cycle: 'monthly',
    savings_vs_human: savingsVsHuman,
    savings_percentage: savingsPercentage,
    roi_months: roiMonths,
    monthly_estimate: total,
    annual_estimate: Math.round(total * 12 * 0.85 * 100) / 100,
  };
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { variant_id, variant_tier, industry, entry_source } = body;

    if (!variant_id || !variant_tier || !industry) {
      return NextResponse.json(
        { error: { code: 'MISSING_FIELDS', message: 'variant_id, variant_tier, and industry are required' } },
        { status: 400 },
      );
    }

    const variant = DEMO_VARIANTS.find((v) => v.id === variant_id);
    if (!variant) {
      return NextResponse.json(
        { error: { code: 'VARIANT_NOT_FOUND', message: `Variant "${variant_id}" not found` } },
        { status: 404 },
      );
    }

    const now = new Date();
    const expiresAt = new Date(now.getTime() + 24 * 60 * 60 * 1000);

    const session = {
      id: generateId('sess'),
      variant_id,
      variant_tier,
      status: 'active',
      created_at: now.toISOString(),
      expires_at: expiresAt.toISOString(),
      messages_used: 0,
      messages_limit: 40,
      call_seconds_used: 0,
      call_seconds_limit: 180,
      shadow_mode: 'shadow',
      knowledge_base_ids: [] as string[],
    };

    sessions.set(session.id, session);

    // Welcome messages
    const welcomeMessages: Record<string, string> = {
      starter: 'Control Center active. I am the PARWA Starter agent — "The 24/7 Trainee." I handle FAQs, data collection, and basic escalation 24/7. What can I help you with?',
      growth: 'Control Center active. I am the PARWA Growth agent — "The Junior Agent." Smart recommendations, churn & fraud detection, multi-channel support. What scenario shall we run?',
      high: 'Control Center active. I am the PARWA High agent — "The Senior Agent." Fully autonomous decisions, peer review & VIP handling, all channels. What\'s your command?',
    };

    const bill_summary = calculateBillSummary(variant_tier, industry);

    return NextResponse.json({
      session: { ...session, bill_summary },
      welcome_message: welcomeMessages[variant_tier] || welcomeMessages.starter,
    });
  } catch (error) {
    return NextResponse.json(
      { error: { code: 'SESSION_CREATE_ERROR', message: error instanceof Error ? error.message : 'Failed to create demo session' } },
      { status: 500 },
    );
  }
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const sessionId = searchParams.get('session_id');

    if (!sessionId) {
      return NextResponse.json(
        { error: { code: 'MISSING_SESSION_ID', message: 'session_id is required' } },
        { status: 400 },
      );
    }

    const session = sessions.get(sessionId);
    if (!session) {
      return NextResponse.json(
        { error: { code: 'SESSION_NOT_FOUND', message: 'Demo session not found' } },
        { status: 404 },
      );
    }

    const bill_summary = calculateBillSummary(session.variant_tier, 'ecommerce');

    return NextResponse.json({
      session: { ...session, bill_summary },
      welcome_message: '',
    });
  } catch (error) {
    return NextResponse.json(
      { error: { code: 'SESSION_GET_ERROR', message: 'Failed to get demo session' } },
      { status: 500 },
    );
  }
}
