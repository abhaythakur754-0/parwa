/**
 * FlexPay Core Algorithm — Smart Payment Splitting Calculator
 * ═══════════════════════════════════════════════════════════════════
 *
 * Splits large subscription payments into daily installments that stay
 * under Razorpay's ₹10,000 (~$104) per-transaction limit.
 *
 * Business Rules:
 * - Target: Foreign/International companies paying in USD
 * - Exchange Rate: ~₹96.38 per $1 USD → max ~$104 per transaction safely
 * - Collection Window: Exactly 30 days (matching subscription cycle)
 * - Base installment: $100/day
 * - Every 3rd day: Double charge ($100 at midnight + $100 at 2am, 2hrs apart)
 * - Handles unlimited parallel customers simultaneously
 *
 * Pricing Tiers:
 *   PARWA:        $2,499/mo → ~25 days collection  
 *   PARWA High:   $3,999/mo → 30 days collection (full schedule)
 *
 * CLAUDE.md Compliance:
 * - P-002: All tiers use same algorithm, amounts differ by tier
 * - P-003: Simple business language in error messages
 */

// ── Types ──────────────────────────────────────────────────────────

export type VariantTier = 'parwa' | 'high';

export interface InstallmentSchedule {
  /** Day number (1-30) */
  day: number;
  /** Amount to charge on this day in USD */
  amount: number;
  /** For double-charge days: secondary charge time offset in hours */
  secondaryOffsetHours?: number;
  /** Secondary charge amount (only on every 3rd day) */
  secondaryAmount?: number;
  /** Total for this day (amount + secondaryAmount) */
  totalForDay: number;
  /** Whether this is a double-charge day */
  isDoubleChargeDay: boolean;
}

export interface FlexPayPlan {
  /** Unique plan identifier */
  id: string;
  /** Company/customer ID */
  companyId: string;
  /** Subscription tier */
  tier: VariantTier;
  /** Total subscription amount in USD */
  totalAmount: number;
  /** Complete installment schedule */
  schedule: InstallmentSchedule[];
  /** Number of days needed to collect full amount */
  totalDays: number;
  /** Base daily installment amount */
  baseAmount: number;
  /** Plan creation timestamp */
  createdAt: Date;
  /** Plan start date */
  startDate: Date;
  /** Expected completion date */
  expectedCompletionDate: Date;
  /** Current status */
  status: 'active' | 'paused' | 'completed' | 'cancelled' | 'failed';
}

export interface InstallmentStatus {
  /** Reference to the plan */
  planId: string;
  /** Day number this installment represents */
  dayNumber: number;
  /** Primary charge status */
  primaryStatus: 'pending' | 'processing' | 'success' | 'failed';
  /** Secondary charge status (for double-charge days) */
  secondaryStatus?: 'pending' | 'processing' | 'success' | 'failed' | 'not_applicable';
  /** Razorpay payment ID for primary charge */
  primaryPaymentId?: string;
  /** Razorpay payment ID for secondary charge */
  secondaryPaymentId?: string;
  /** Amount actually charged (primary) */
  primaryChargedAmount?: number;
  /** Amount actually charged (secondary) */
  secondaryChargedAmount?: number;
  /** Timestamp when primary was processed */
  primaryProcessedAt?: Date;
  /** Timestamp when secondary was processed */
  secondaryProcessedAt?: Date;
  /** Error message if failed */
  errorMessage?: string;
  /** Retry count */
  retryCount: number;
}

// ── Constants ───────────────────────────────────────────────────────

/**
 * Razorpay transaction limit in INR
 * Actual limit is ₹10,000; we use ₹9,900 as safe limit (with small buffer)
 * This allows $100 USD transactions (~₹9,638 at current rate)
 */
export const RAZORPAY_MAX_INR_LIMIT = 9900;

/**
 * Exchange rate: INR per 1 USD
 * Using conservative rate; should be updated from live API in production
 */
export const EXCHANGE_RATE_USD_TO_INR = 96.38;

/**
 * Maximum safe USD per transaction (with buffer)
 * ₹9,900 / 96.38 ≈ $102.74, so $100 is safe
 */
export const MAX_SAFE_USD_PER_TRANSACTION = 100;

/**
 * Base daily installment amount in USD
 * Set at $100 which converts to ~₹9,638 (under ₹10K limit)
 */
export const BASE_DAILY_AMOUNT = 100;

/**
 * Total collection window in days (matches subscription cycle)
 */
export const COLLECTION_WINDOW_DAYS = 30;

/**
 * Interval for double-charge days (every Nth day)
 */
export const DOUBLE_CHARGE_INTERVAL = 3;

/**
 * Hours between primary and secondary charge on double-charge days
 */
export const DOUBLE_CHARGE_HOUR_GAP = 2;

// ── Tier Configuration ─────────────────────────────────────────────

export const TIER_PRICES: Record<VariantTier, number> = {
  parwa: 2499,
  high: 3999,
};

// ── Core Algorithm ──────────────────────────────────────────────────

/**
 * Calculate the complete installment schedule for a given amount and tier.
 *
 * Algorithm:
 * 1. Determine base daily amount ($100)
 * 2. Every 3rd day, add a second charge of $100 (2 hours after first)
 * 3. Continue until total amount is covered within 30 days
 * 4. Adjust final installment if needed to match exact amount
 *
 * @param totalAmount - Total subscription amount in USD
 * @param tier - Subscription tier (affects validation)
 * @returns Array of daily installment schedules
 *
 * @example
 * // For $3,999 (PARWA High):
 * // Days 1,2: $100 each = $200
 * // Day 3: $100 + $100 = $200 (double charge)
 * // Days 4,5: $100 each = $200
 * // Day 6: $100 + $100 = $200 (double charge)
 * // ... continues for 30 days
 * // Total collected: $3,999 (adjusted last day)
 */
export function calculateInstallmentSchedule(
  totalAmount: number,
  tier: VariantTier
): InstallmentSchedule[] {
  // Validate inputs
  if (totalAmount <= 0) {
    throw new Error('Total amount must be greater than zero');
  }

  if (!TIER_PRICES[tier]) {
    throw new Error(`Invalid tier: ${tier}. Must be one of: ${Object.keys(TIER_PRICES).join(', ')}`);
  }

  // Validate amount matches tier (allowing small rounding differences)
  const expectedAmount = TIER_PRICES[tier];
  const tolerance = expectedAmount * 0.01; // 1% tolerance
  if (Math.abs(totalAmount - expectedAmount) > tolerance) {
    console.warn(`[FlexPay] Amount $${totalAmount} differs from expected $${expectedAmount} for tier ${tier}`);
  }

  const schedule: InstallmentSchedule[] = [];
  let remainingAmount = totalAmount;
  let day = 1;

  // Generate schedule until amount is fully allocated or we hit 30 days
  // NOTE: Double-charge days only apply to PARWA High tier
  // Mini PARWA and PARWA use simple $100/day charging
  const useDoubleCharge = tier === 'high';
  
  while (remainingAmount > 0 && day <= COLLECTION_WINDOW_DAYS) {
    const isDoubleChargeDay = useDoubleCharge && (day % DOUBLE_CHARGE_INTERVAL === 0);
    
    // Calculate charges for this day
    let primaryAmount = Math.min(BASE_DAILY_AMOUNT, remainingAmount);
    let secondaryAmount = 0;
    
    if (isDoubleChargeDay && remainingAmount > BASE_DAILY_AMOUNT) {
      // Double-charge day: split into two transactions
      secondaryAmount = Math.min(BASE_DAILY_AMOUNT, remainingAmount - primaryAmount);
      // Adjust primary if we need less than base amount
      if (remainingAmount < BASE_DAILY_AMOUNT * 2) {
        // Not enough for full double charge, adjust
        const halfRemaining = Math.ceil(remainingAmount / 2);
        primaryAmount = Math.min(halfRemaining, remainingAmount);
        secondaryAmount = remainingAmount - primaryAmount;
      }
    }

    const totalForDay = primaryAmount + secondaryAmount;

    schedule.push({
      day,
      amount: primaryAmount,
      ...(secondaryAmount > 0 ? {
        secondaryOffsetHours: DOUBLE_CHARGE_HOUR_GAP,
        secondaryAmount,
      } : {}),
      totalForDay,
      isDoubleChargeDay: isDoubleChargeDay && secondaryAmount > 0,
    });

    remainingAmount -= totalForDay;
    day++;
  }

  // Adjust last installment if there's a small remainder due to rounding
  if (schedule.length > 0 && remainingAmount > 0 && remainingAmount < 1) {
    const lastInstallment = schedule[schedule.length - 1];
    lastInstallment.amount += remainingAmount;
    lastInstallment.totalForDay += remainingAmount;
    remainingAmount = 0;
  }

  // Safety check: ensure we collect the full amount
  const scheduledTotal = schedule.reduce((sum, s) => sum + s.totalForDay, 0);
  if (Math.abs(scheduledTotal - totalAmount) > 1) {
    throw new Error(`[FlexPay] Schedule calculation error: Expected $${totalAmount}, got $${scheduledTotal}`);
  }

  return schedule;
}

/**
 * Get today's installments for a given plan.
 * Returns the installment(s) that should be processed today.
 */
export function getTodaysInstallments(
  plan: FlexPayPlan,
  currentDate: Date = new Date()
): { primary?: InstallmentSchedule; secondary?: InstallmentSchedule } {
  if (plan.status !== 'active') {
    return {};
  }

  const startDate = new Date(plan.startDate);
  const current = new Date(currentDate);
  
  // Reset times to midnight for day comparison
  startDate.setHours(0, 0, 0, 0);
  current.setHours(0, 0, 0, 0);

  const diffTime = current.getTime() - startDate.getTime();
  const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24)) + 1; // 1-indexed

  if (diffDays < 1 || diffDays > plan.schedule.length) {
    return {};
  }

  const todaysSchedule = plan.schedule[diffDays - 1];

  // Check if it's time for secondary charge (after 2am on double-charge days)
  const currentHour = currentDate.getHours();
  const needsSecondary = 
    todaysSchedule.isDoubleChargeDay && 
    todaysSchedule.secondaryOffsetHours && 
    currentHour >= todaysSchedule.secondaryOffsetHours;

  return {
    primary: todaysSchedule,
    ...(needsSecondary ? { secondary: todaysSchedule } : {}),
  };
}

/**
 * Calculate progress metrics for a plan.
 */
export function calculatePlanProgress(plan: FlexPayPlan, completedDays: number): {
  currentDay: number;
  totalDays: number;
  daysCompleted: number;
  daysRemaining: number;
  percentageComplete: number;
  amountCollected: number;
  amountRemaining: number;
  isOnTrack: boolean;
  isComplete: boolean;
} {
  const totalDays = plan.totalDays;
  const daysCompleted = Math.min(completedDays, totalDays);
  const daysRemaining = Math.max(0, totalDays - daysCompleted);
  const percentageComplete = totalDays > 0 ? (daysCompleted / totalDays) * 100 : 0;

  // Calculate amounts
  let amountCollected = 0;
  for (let i = 0; i < daysCompleted && i < plan.schedule.length; i++) {
    amountCollected += plan.schedule[i].totalForDay;
  }
  const amountRemaining = plan.totalAmount - amountCollected;

  return {
    currentDay: daysCompleted + 1,
    totalDays,
    daysCompleted,
    daysRemaining,
    percentageComplete: Math.round(percentageComplete * 100) / 100,
    amountCollected,
    amountRemaining,
    isOnTrack: daysCompleted >= Math.floor((Date.now() - new Date(plan.startDate).getTime()) / (1000 * 60 * 60 * 24)),
    isComplete: daysCompleted >= totalDays,
  };
}

/**
 * Convert USD amount to INR (Razorpay requires INR).
 * Uses conservative exchange rate with safety buffer.
 */
export function usdToInr(usdAmount: number): number {
  const inrAmount = usdAmount * EXCHANGE_RATE_USD_TO_INR;
  
  // Check against Razorpay limit
  if (inrAmount > RAZORPAY_MAX_INR_LIMIT) {
    throw new Error(
      `[FlexPay] Amount $${usdAmount} (₹${inrAmount.toFixed(2)}) exceeds Razorpay's safe transaction limit of ₹${RAZORPAY_MAX_INR_LIMIT}`
    );
  }
  
  // Convert to paise (Razorpay uses integer paise)
  return Math.round(inrAmount * 100);
}

/**
 * Validate that an amount is safe for Razorpay processing.
 */
export function validateTransactionAmount(usdAmount: number): { valid: boolean; reason?: string; inrAmount: number } {
  const inrAmount = usdAmount * EXCHANGE_RATE_USD_TO_INR;
  
  if (usdAmount <= 0) {
    return { valid: false, reason: 'Amount must be greater than zero', inrAmount };
  }
  
  if (inrAmount > RAZORPAY_MAX_INR_LIMIT) {
    return { 
      valid: false, 
      reason: `Amount $${usdAmount} (₹${inrAmount.toFixed(2)}) exceeds Razorpay's safe limit of ₹${RAZORPAY_MAX_INR_LIMIT}`,
      inrAmount 
    };
  }
  
  // Add small buffer - don't go above 98% of limit
  if (inrAmount > RAZORPAY_MAX_INR_LIMIT * 0.98) {
    return { 
      valid: false, 
      reason: `Amount $${usdAmount} too close to limit. Use a smaller amount.`,
      inrAmount 
    };
  }
  
  return { valid: true, inrAmount };
}

/**
 * Create a new FlexPay plan from subscription details.
 */
export function createFlexPayPlan(params: {
  id: string;
  companyId: string;
  tier: VariantTier;
  totalAmount: number;
  startDate?: Date;
}): FlexPayPlan {
  const { id, companyId, tier, totalAmount, startDate = new Date() } = params;
  
  const schedule = calculateInstallmentSchedule(totalAmount, tier);
  const totalDays = schedule.length;
  
  const expectedCompletion = new Date(startDate);
  expectedCompletion.setDate(expectedCompletion.getDate() + totalDays);
  
  return {
    id,
    companyId,
    tier,
    totalAmount,
    schedule,
    totalDays,
    baseAmount: BASE_DAILY_AMOUNT,
    createdAt: new Date(),
    startDate,
    expectedCompletionDate: expectedCompletion,
    status: 'active',
  };
}

// ── Utility Functions ───────────────────────────────────────────────

/**
 * Generate a human-readable summary of the payment schedule.
 * Useful for customer-facing displays and emails.
 */
export function generateScheduleSummary(plan: FlexPayPlan): string {
  const lines = [
    `FlexPay Payment Schedule`,
    `═══════════════════════════`,
    `Plan ID: ${plan.id}`,
    `Tier: ${plan.tier.toUpperCase()}`,
    `Total Amount: $${plan.totalAmount.toLocaleString()}`,
    `Duration: ${plan.totalDays} days`,
    `Start Date: ${plan.startDate.toLocaleDateString()}`,
    `Expected Completion: ${plan.expectedCompletionDate.toLocaleDateString()}`,
    ``,
    `Daily Breakdown:`,
    `─────────────────`,
  ];
  
  // Group by pattern
  const singleChargeDays = plan.schedule.filter(s => !s.isDoubleChargeDay).length;
  const doubleChargeDays = plan.schedule.filter(s => s.isDoubleChargeDay).length;
  
  lines.push(`- Regular days ($${BASE_DAILY_AMOUNT}/day): ${singleChargeDays} days`);
  lines.push(`- Double-charge days ($${BASE_DAILY_AMOUNT} x 2): ${doubleChargeDays} days`);
  lines.push(`- Every ${DOUBLE_CHARGE_INTERVAL}th day has two charges, ${DOUBLE_CHARGE_HOUR_GAP} hours apart`);
  
  return lines.join('\n');
}

/**
 * Get the next pending installment for a plan.
 */
export function getNextPendingInstallment(
  plan: FlexPayPlan,
  completedDayNumbers: Set<number>
): InstallmentSchedule | null {
  for (const installment of plan.schedule) {
    if (!completedDayNumbers.has(installment.day)) {
      return installment;
    }
  }
  return null;
}

/**
 * Check if a plan can be paused (has active installments remaining).
 */
export function canPausePlan(plan: FlexPayPlan): boolean {
  return plan.status === 'active';
}

/**
 * Check if a plan can be resumed (is currently paused).
 */
export function canResumePlan(plan: FlexPayPlan): boolean {
  return plan.status === 'paused';
}

/**
 * Calculate retry delay with exponential backoff.
 */
export function calculateRetryDelay(failureCount: number): number {
  // Start at 1 hour, max at 24 hours
  const baseDelayMs = 60 * 60 * 1000; // 1 hour
  const maxDelayMs = 24 * 60 * 60 * 1000; // 24 hours
  
  // Exponential backoff: 1hr, 2hr, 4hr, 8hr, 16hr, 24hr (capped)
  const delay = Math.min(baseDelayMs * Math.pow(2, failureCount), maxDelayMs);
  
  return delay;
}

// ── Plan Operations (for API routes) ──────────────────────────────

/**
 * Get a plan by ID from scheduler store.
 */
export function getPlan(planId: string): FlexPayPlan | null {
  try {
    // Import dynamically to avoid circular dependencies
    const { getPlan: getSchedulerPlan } = require('@/lib/flexpay/scheduler');
    return getSchedulerPlan(planId);
  } catch {
    return null;
  }
}

/**
 * Pause an active FlexPay plan.
 */
export function pausePlan(planId: string): { success: boolean; message: string } {
  try {
    const { getPlan: getSchedulerPlan, updatePlanStatus } = require('@/lib/flexpay/scheduler');
    const plan = getSchedulerPlan(planId);
    
    if (!plan) {
      return { success: false, message: 'Plan not found' };
    }
    
    if (!canPausePlan(plan)) {
      return { success: false, message: 'Plan cannot be paused (not active)' };
    }
    
    updatePlanStatus(planId, 'paused');
    return { success: true, message: 'Plan paused successfully' };
  } catch (error) {
    console.error('[FlexPay] Error pausing plan:', error);
    return { success: false, message: 'Failed to pause plan' };
  }
}

/**
 * Resume a paused FlexPay plan.
 */
export function resumePlan(planId: string): { success: boolean; message: string } {
  try {
    const { getPlan: getSchedulerPlan, updatePlanStatus } = require('@/lib/flexpay/scheduler');
    const plan = getSchedulerPlan(planId);
    
    if (!plan) {
      return { success: false, message: 'Plan not found' };
    }
    
    if (!canResumePlan(plan)) {
      return { success: false, message: 'Plan cannot be resumed (not paused)' };
    }
    
    updatePlanStatus(planId, 'active');
    return { success: true, message: 'Plan resumed successfully' };
  } catch (error) {
    console.error('[FlexPay] Error resuming plan:', error);
    return { success: false, message: 'Failed to resume plan' };
  }
}

/**
 * Cancel a FlexPay plan permanently.
 */
export function cancelPlan(planId: string): { success: boolean; message: string } {
  try {
    const { getPlan: getSchedulerPlan, updatePlanStatus, removePlan } = require('@/lib/flexpay/scheduler');
    const plan = getSchedulerPlan(planId);
    
    if (!plan) {
      return { success: false, message: 'Plan not found' };
    }
    
    // Remove plan from scheduler or mark as cancelled
    if (removePlan) {
      removePlan(planId);
    } else {
      updatePlanStatus(planId, 'cancelled');
    }
    
    return { success: true, message: 'Plan cancelled successfully' };
  } catch (error) {
    console.error('[FlexPay] Error cancelling plan:', error);
    return { success: false, message: 'Failed to cancel plan' };
  }
}

/**
 * Get completed day numbers for a plan.
 */
export function getCompletedDayNumbers(planId: string): Set<number> {
  try {
    const { getInstallmentStatus } = require('@/lib/flexpay/scheduler');
    const completedDays = new Set<number>();
    
    // Check first 100 days for completed installments
    for (let day = 1; day <= 100; day++) {
      const status = getInstallmentStatus(planId, day);
      if (status && status.primaryStatus === 'success') {
        completedDays.add(day);
      }
    }
    
    return completedDays;
  } catch {
    return new Set();
  }
}
