/**
 * FlexPay Plan Management API Endpoint
 * ═══════════════════════════════════════════════════════════════════
 *
 * GET    /api/flexpay/plan/[planId]     - Get plan details & progress
 * POST   /api/flexpay/plan/[planId]     - Update plan (pause/resume)
 * DELETE /api/flexpay/plan/[planId]     - Cancel plan
 *
 * Plan Operations:
 * - pause: Temporarily stop installment processing
 * - resume: Restart processing after pause
 * - cancel: Permanently stop and unregister plan
 */

import { NextRequest, NextResponse } from 'next/server';
import { 
  getPlan, 
  pausePlan, 
  resumePlan, 
  cancelPlan,
  getCompletedDayNumbers,
  calculatePlanProgress,
  generateScheduleSummary
} from '@/lib/flexpay/core';
import { 
  getPlan as getSchedulerPlan,
  getInstallmentStatus,
  getSchedulerStats 
} from '@/lib/flexpay/scheduler';

interface RouteContext {
  params: Promise<{ planId: string }>;
}

// ── GET: Plan Details ──────────────────────────────────────────────

export async function GET(req: NextRequest, context: RouteContext) {
  try {
    const { planId } = await context.params;

    // Get plan from scheduler store
    const plan = getSchedulerPlan(planId);
    
    if (!plan) {
      return NextResponse.json(
        { success: false, error: 'Plan not found' },
        { status: 404 }
      );
    }

    // Calculate current progress
    const completedDays = getCompletedDayNumbers(planId);
    const progress = calculatePlanProgress(plan, completedDays.size);

    // Get recent installment history (last 10)
    const recentInstallments = [];
    for (let day = Math.max(1, progress.daysCompleted - 9); day <= progress.daysCompleted; day++) {
      const status = getInstallmentStatus(planId, day);
      if (status) {
        recentInstallments.push({
          dayNumber: status.dayNumber,
          amount: status.primaryChargedAmount,
          status: status.primaryStatus,
          processedAt: status.primaryProcessedAt?.toISOString(),
          hasSecondaryCharge: status.secondaryStatus !== undefined && status.secondaryStatus !== 'not_applicable',
        });
      }
    }

    return NextResponse.json({
      success: true,
      plan: {
        id: plan.id,
        companyId: plan.companyId,
        tier: plan.tier,
        status: plan.status,
        totalAmount: plan.totalAmount,
        totalDays: plan.totalDays,
        baseAmount: plan.baseAmount,
        startDate: plan.startDate.toISOString(),
        expectedCompletionDate: plan.expectedCompletionDate.toISOString(),
        createdAt: plan.createdAt.toISOString(),
      },
      progress: {
        ...progress,
        currentDayLabel: `Day ${progress.currentDay} of ${progress.totalDays}`,
      },
      recentInstallments,
      scheduleSummary: generateScheduleSummary(plan),
    });

  } catch (error) {
    console.error('[FlexPay/API] Error getting plan:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to get plan details' },
      { status: 500 }
    );
  }
}

// ── POST: Pause/Resume ─────────────────────────────────────────────

export async function POST(req: NextRequest, context: RouteContext) {
  try {
    const { planId } = await context.params;
    
    // Parse action from body
    let body: { action?: string };
    try {
      body = await req.json();
    } catch {
      return NextResponse.json(
        { success: false, error: 'Invalid JSON in request body' },
        { status: 400 }
      );
    }

    const action = body.action;

    if (!action || !['pause', 'resume'].includes(action)) {
      return NextResponse.json(
        { success: false, error: 'Action must be either "pause" or "resume"' },
        { status: 400 }
      );
    }

    // Execute action
    const result = action === 'pause' ? pausePlan(planId) : resumePlan(planId);

    if (!result.success) {
      return NextResponse.json(
        { success: false, error: result.message },
        { status: 400 }
      );
    }

    // Get updated plan
    const updatedPlan = getSchedulerPlan(planId);

    return NextResponse.json({
      success: true,
      message: result.message,
      plan: updatedPlan ? {
        id: updatedPlan.id,
        status: updatedPlan.status,
      } : null,
    });

  } catch (error) {
    console.error('[FlexPay/API] Error updating plan:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to update plan' },
      { status: 500 }
    );
  }
}

// ── DELETE: Cancel Plan ────────────────────────────────────────────

export async function DELETE(_req: NextRequest, context: RouteContext) {
  try {
    const { planId } = await context.params;

    const result = cancelPlan(planId);

    if (!result.success) {
      return NextResponse.json(
        { success: false, error: result.message },
        { status: 400 }
      );
    }

    return NextResponse.json({
      success: true,
      message: result.message,
    });

  } catch (error) {
    console.error('[FlexPay/API] Error cancelling plan:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to cancel plan' },
      { status: 500 }
    );
  }
}
