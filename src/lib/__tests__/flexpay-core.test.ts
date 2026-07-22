/**
 * FlexPay Core Algorithm — Comprehensive Unit Tests
 * ═══════════════════════════════════════════════════════════════════
 *
 * Tests all core functions including:
 * - Schedule calculation for all tiers
 * - Amount validation and conversion
 * - Progress tracking
 * - Edge cases and error handling
 *
 * CLAUDE.md Compliance:
 * - P-001: Goal-driven execution (tests verify requirements)
 */

import {
  calculateInstallmentSchedule,
  createFlexPayPlan,
  usdToInr,
  validateTransactionAmount,
  getTodaysInstallments,
  calculatePlanProgress,
  generateScheduleSummary,
  getNextPendingInstallment,
  canPausePlan,
  canResumePlan,
  calculateRetryDelay,
  // Constants
  BASE_DAILY_AMOUNT,
  COLLECTION_WINDOW_DAYS,
  DOUBLE_CHARGE_INTERVAL,
  DOUBLE_CHARGE_HOUR_GAP,
  RAZORPAY_MAX_INR_LIMIT,
  EXCHANGE_RATE_USD_TO_INR,
  TIER_PRICES,
} from '../flexpay/core';

// ── Test Constants ─────────────────────────────────────────────────

const TEST_PLAN_ID = 'test_plan_001';
const TEST_COMPANY_ID = 'company_123';
const TEST_START_DATE = new Date('2024-01-01T00:00:00Z');

// ── Helper Functions ───────────────────────────────────────────────

function createTestPlan(tier: VariantTier, amount?: number): FlexPayPlan {
  return createFlexPayPlan({
    id: TEST_PLAN_ID,
    companyId: TEST_COMPANY_ID,
    tier,
    totalAmount: amount ?? TIER_PRICES[tier],
    startDate: TEST_START_DATE,
  });
}

function sumSchedule(schedule: InstallmentSchedule[]): number {
  return schedule.reduce((sum, s) => sum + s.totalForDay, 0);
}

// ── Test Suites ────────────────────────────────────────────────────

describe('FlexPay Core Algorithm', () => {

  // ═══════════════════════════════════════════════════════════════════
  // SCHEDULE CALCULATION TESTS
  // ═══════════════════════════════════════════════════════════════════

  describe('calculateInstallmentSchedule', () => {

    describe('Mini PARWA Tier ($999)', () => {
      it('should generate correct schedule for $999 tier', () => {
        const schedule = calculateInstallmentSchedule(999, 'mini');
        
        expect(schedule.length).toBeGreaterThan(0);
        expect(schedule.length).toBeLessThanOrEqual(COLLECTION_WINDOW_DAYS);
        
        const total = sumSchedule(schedule);
        expect(total).toBe(999);
      });

      it('should complete $999 in approximately 10 days', () => {
        const schedule = calculateInstallmentSchedule(999, 'mini');
        
        // At $100/day + double charges every 3rd day (~$133 avg), should be ~10 days
        expect(schedule.length).toBeGreaterThanOrEqual(8);
        expect(schedule.length).toBeLessThanOrEqual(12);
      });
    });

    describe('PARWA Tier ($2,499)', () => {
      it('should generate correct schedule for $2,499 tier', () => {
        const schedule = calculateInstallmentSchedule(2499, 'parwa');
        
        expect(schedule.length).toBeGreaterThan(0);
        expect(schedule.length).toBeLessThanOrEqual(COLLECTION_WINDOW_DAYS);
        
        const total = sumSchedule(schedule);
        expect(total).toBe(2499);
      });

      it('should complete $2,499 in approximately 25 days', () => {
        const schedule = calculateInstallmentSchedule(2499, 'parwa');
        
        // Should take around 19-27 days at ~$100-133/day average
        expect(schedule.length).toBeGreaterThanOrEqual(19);
        expect(schedule.length).toBeLessThanOrEqual(28);
      });
    });

    describe('PARWA High Tier ($3,999)', () => {
      it('should generate full 30-day schedule for $3,999 tier', () => {
        const schedule = calculateInstallmentSchedule(3999, 'high');
        
        expect(schedule.length).toBe(COLLECTION_WINDOW_DAYS); // Exactly 30 days
        
        const total = sumSchedule(schedule);
        expect(total).toBe(3999);
      });

      it('should have double charges every 3rd day', () => {
        const schedule = calculateInstallmentSchedule(3999, 'high');
        
        // Check days 3, 6, 9, etc. are double charge days (except possibly last day)
        for (let day = 3; day <= schedule.length; day += 3) {
          const installment = schedule[day - 1]; // 0-indexed
          expect(installment.isDoubleChargeDay).toBe(true);
          expect(installment.secondaryOffsetHours).toBe(DOUBLE_CHARGE_HOUR_GAP);
          
          // Last day may have adjusted amounts to match total exactly
          if (day < schedule.length) {
            expect(installment.secondaryAmount).toBe(BASE_DAILY_AMOUNT);
            expect(installment.totalForDay).toBe(BASE_DAILY_AMOUNT * 2);
          } else {
            // Last day should still have secondary charge but may be adjusted
            expect(installment.secondaryAmount).toBeGreaterThan(0);
            expect(installment.totalForDay).toBeGreaterThan(0);
          }
        }
      });

      it('should have single charges on non-double-charge days', () => {
        const schedule = calculateInstallmentSchedule(3999, 'high');
        
        // Days 1, 2, 4, 5, 7, 8... should be single charge
        const singleChargeDays = [1, 2, 4, 5, 7, 8];
        for (const day of singleChargeDays) {
          if (day <= schedule.length) {
            const installment = schedule[day - 1];
            expect(installment.isDoubleChargeDay).toBe(false);
            expect(installment.amount).toBe(BASE_DAILY_AMOUNT);
            expect(installment.totalForDay).toBe(BASE_DAILY_AMOUNT);
            expect(installment.secondaryAmount).toBeUndefined();
          }
        }
      });
    });

    describe('Double Charge Pattern Validation', () => {
      it('should correctly identify double-charge intervals', () => {
        const schedule = calculateInstallmentSchedule(3999, 'high');
        
        let doubleChargeCount = 0;
        let singleChargeCount = 0;
        
        for (const installment of schedule) {
          if (installment.isDoubleChargeDay) {
            doubleChargeCount++;
            expect(installment.amount).toBe(BASE_DAILY_AMOUNT);
            // Last double-charge day may have adjusted secondary amount
            if (doubleChargeCount < 10) { // Not the last one
              expect(installment.secondaryAmount).toBe(BASE_DAILY_AMOUNT);
            } else {
              expect(installment.secondaryAmount).toBeGreaterThan(0);
            }
          } else {
            singleChargeCount++;
          }
        }
        
        // For 30 days with interval of 3: 10 double-charge days, 20 single-charge days
        expect(doubleChargeCount).toBe(10);
        expect(singleChargeCount).toBe(20);
      });

      it('should maintain 2-hour gap between charges on double-charge days', () => {
        const schedule = calculateInstallmentSchedule(3999, 'high');
        
        for (const installment of schedule) {
          if (installment.isDoubleChargeDay) {
            expect(installment.secondaryOffsetHours).toBe(DOUBLE_CHARGE_HOUR_GAP);
          }
        }
      });
    });

    describe('Total Amount Accuracy', () => {
      it('should exactly match total amount for all tiers', () => {
        const testCases: [number, VariantTier][] = [
          [999, 'mini'],
          [2499, 'parwa'],
          [3999, 'high'],
        ];

        for (const [amount, tier] of testCases) {
          const schedule = calculateInstallmentSchedule(amount, tier);
          const total = sumSchedule(schedule);
          expect(total).toBe(amount);
        }
      });

      it('should handle edge case amounts correctly', () => {
        // Test amounts that don't divide evenly
        const schedule = calculateInstallmentSchedule(1001, 'mini'); // Just over 10 days
        const total = sumSchedule(schedule);
        expect(total).toBe(1001);
      });
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  // PLAN CREATION TESTS
  // ═══════════════════════════════════════════════════════════════════

  describe('createFlexPayPlan', () => {
    it('should create a valid plan with required fields', () => {
      const plan = createTestPlan('high');

      expect(plan.id).toBe(TEST_PLAN_ID);
      expect(plan.companyId).toBe(TEST_COMPANY_ID);
      expect(plan.tier).toBe('high');
      expect(plan.totalAmount).toBe(TIER_PRICES.high);
      expect(plan.status).toBe('active');
      expect(plan.schedule).toBeDefined();
      expect(plan.schedule.length).toBeGreaterThan(0);
    });

    it('should set expected completion date correctly', () => {
      const plan = createTestPlan('mini');
      
      const expectedEnd = new Date(TEST_START_DATE);
      expectedEnd.setDate(expectedEnd.getDate() + plan.totalDays);
      
      expect(plan.expectedCompletionDate.getTime()).toBe(expectedEnd.getTime());
    });

    it('should use custom start date when provided', () => {
      const customDate = new Date('2024-06-15T00:00:00Z');
      const plan = createFlexPayPlan({
        id: TEST_PLAN_ID,
        companyId: TEST_COMPANY_ID,
        tier: 'parwa',
        totalAmount: 2499,
        startDate: customDate,
      });

      expect(plan.startDate.getTime()).toBe(customDate.getTime());
    });

    it('should default to current date when no start date provided', () => {
      const beforeCreation = new Date();
      const plan = createFlexPayPlan({
        id: TEST_PLAN_ID,
        companyId: TEST_COMPANY_ID,
        tier: 'mini',
        totalAmount: 999,
      });
      const afterCreation = new Date();

      expect(plan.startDate.getTime()).toBeGreaterThanOrEqual(beforeCreation.getTime());
      expect(plan.startDate.getTime()).toBeLessThanOrEqual(afterCreation.getTime());
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  // CURRENCY CONVERSION TESTS
  // ═══════════════════════════════════════════════════════════════════

  describe('usdToInr', () => {
    it('should convert USD to INR paise correctly', () => {
      const result = usdToInr(100); // $100
      
      // $100 × 96.38 = ₹9,638 → 963,800 paise
      expect(result).toBe(963800);
    });

    it('should throw error for amounts exceeding Razorpay limit', () => {
      expect(() => usdToInr(105)).toThrow(/exceeds Razorpay's safe transaction limit/);
    });

    it('should handle boundary values correctly', () => {
      // Max safe amount should not throw
      const maxSafeUsd = Math.floor(RAZORPAY_MAX_INR_LIMIT / EXCHANGE_RATE_USD_TO_INR);
      expect(() => usdToInr(maxSafeUsd)).not.toThrow();
      
      // Just over should throw
      expect(() => usdToInr(maxSafeUsd + 1)).toThrow();
    });
  });

  describe('validateTransactionAmount', () => {
    it('should validate safe amounts', () => {
      const result = validateTransactionAmount(100);
      
      expect(result.valid).toBe(true);
      expect(result.inrAmount).toBeCloseTo(9638, 0);
    });

    it('should reject zero or negative amounts', () => {
      const zeroResult = validateTransactionAmount(0);
      expect(zeroResult.valid).toBe(false);
      
      const negativeResult = validateTransactionAmount(-100);
      expect(negativeResult.valid).toBe(false);
    });

    it('should reject amounts exceeding limit', () => {
      const result = validateTransactionAmount(105);
      expect(result.valid).toBe(false);
      expect(result.reason).toContain('exceeds Razorpay');
    });

    it('should reject amounts too close to limit', () => {
      // Amount that's >98% of limit (threshold is 98%)
      const borderlineUsd = (RAZORPAY_MAX_INR_LIMIT * 0.985) / EXCHANGE_RATE_USD_TO_INR;
      const result = validateTransactionAmount(borderlineUsd);
      expect(result.valid).toBe(false);
      expect(result.reason).toContain('too close to limit');
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  // TODAY'S INSTALLMENTS TESTS
  // ═══════════════════════════════════════════════════════════════════

  describe('getTodaysInstallments', () => {
    it('should return primary installment on active days', () => {
      const plan = createTestPlan('high');
      
      // Day 1 (same as start date)
      const day1 = getTodaysInstallments(plan, TEST_START_DATE);
      
      expect(day1.primary).toBeDefined();
      expect(day1.primary?.day).toBe(1);
      expect(day1.primary?.amount).toBe(BASE_DAILY_AMOUNT);
    });

    it('should return empty object before start date', () => {
      const plan = createTestPlan('high');
      
      const beforeStart = new Date(TEST_START_DATE);
      beforeStart.setDate(beforeStart.getDate() - 1);
      
      const result = getTodaysInstallments(plan, beforeStart);
      
      expect(result.primary).toBeUndefined();
      expect(result.secondary).toBeUndefined();
    });

    it('should return secondary installment after offset hours on double-charge days', () => {
      const plan = createTestPlan('high');
      
      // Day 3 is a double-charge day (every 3rd day)
      const day3Date = new Date(TEST_START_DATE);
      day3Date.setDate(day3Date.getDate() + 2); // Day 3 (0-indexed: +2)
      
      // Before secondary time (midnight) - no secondary
      const earlyMorning = new Date(day3Date);
      earlyMorning.setHours(1, 0, 0, 0);
      const earlyResult = getTodaysInstallments(plan, earlyMorning);
      expect(earlyResult.primary).toBeDefined();
      expect(earlyResult.secondary).toBeUndefined();
      
      // After secondary time (2am) - should have secondary
      const lateMorning = new Date(day3Date);
      lateMorning.setHours(3, 0, 0, 0);
      const lateResult = getTodaysInstallments(plan, lateMorning);
      expect(lateResult.primary).toBeDefined();
      expect(lateResult.secondary).toBeDefined();
    });

    it('should return empty for paused plans', () => {
      const plan = createTestPlan('high');
      plan.status = 'paused';
      
      const result = getTodaysInstallments(plan, TEST_START_DATE);
      
      expect(result.primary).toBeUndefined();
    });

    it('should return empty for completed plans', () => {
      const plan = createTestPlan('high');
      plan.status = 'completed';
      
      const result = getTodaysInstallments(plan, TEST_START_DATE);
      
      expect(result.primary).toBeUndefined();
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  // PROGRESS CALCULATION TESTS
  // ═══════════════════════════════════════════════════════════════════

  describe('calculatePlanProgress', () => {
    it('should calculate progress correctly at start', () => {
      const plan = createTestPlan('high');
      const progress = calculatePlanProgress(plan, 0);
      
      expect(progress.daysCompleted).toBe(0);
      expect(progress.daysRemaining).toBe(plan.totalDays);
      expect(progress.percentageComplete).toBe(0);
      expect(progress.amountCollected).toBe(0);
      expect(progress.amountRemaining).toBe(plan.totalAmount);
      expect(progress.currentDay).toBe(1);
      expect(progress.isComplete).toBe(false);
    });

    it('should calculate progress correctly in middle', () => {
      const plan = createTestPlan('high');
      const midPoint = Math.floor(plan.totalDays / 2);
      const progress = calculatePlanProgress(plan, midPoint);
      
      expect(progress.daysCompleted).toBe(midPoint);
      expect(progress.daysRemaining).toBe(plan.totalDays - midPoint);
      expect(progress.percentageComplete).toBeGreaterThan(40);
      expect(progress.percentageComplete).toBeLessThan(60);
      expect(progress.amountCollected).toBeGreaterThan(0);
      expect(progress.amountRemaining).toBeLessThan(plan.totalAmount);
    });

    it('should show 100% when complete', () => {
      const plan = createTestPlan('high');
      const progress = calculatePlanProgress(plan, plan.totalDays);
      
      expect(progress.daysCompleted).toBe(plan.totalDays);
      expect(progress.daysRemaining).toBe(0);
      expect(progress.percentageComplete).toBe(100);
      expect(progress.amountRemaining).toBe(0);
      expect(progress.isComplete).toBe(true);
    });

    it('should handle completed days exceeding total', () => {
      const plan = createTestPlan('mini');
      const progress = calculatePlanProgress(plan, 100); // Way more than needed
      
      expect(progress.daysCompleted).toBe(plan.totalDays);
      expect(progress.percentageComplete).toBe(100);
      expect(progress.isComplete).toBe(true);
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  // UTILITY FUNCTION TESTS
  // ═══════════════════════════════════════════════════════════════════

  describe('generateScheduleSummary', () => {
    it('should generate human-readable summary', () => {
      const plan = createTestPlan('high');
      const summary = generateScheduleSummary(plan);
      
      expect(summary).toContain('FlexPay Payment Schedule');
      expect(summary).toContain(plan.id);
      expect(summary).toContain('HIGH');
      expect(summary).toContain('$3,999');
      expect(summary).toContain(`${plan.totalDays} days`);
      expect(summary).toContain('$100');
    });

    it('should include double-charge information', () => {
      const plan = createTestPlan('high');
      const summary = generateScheduleSummary(plan);
      
      expect(summary).toContain('Double-charge');
      expect(summary).toContain(`${DOUBLE_CHARGE_INTERVAL}`);
      expect(summary).toContain(`${DOUBLE_CHARGE_HOUR_GAP}`);
    });
  });

  describe('getNextPendingInstallment', () => {
    it('should return first installment when none completed', () => {
      const plan = createTestPlan('high');
      const next = getNextPendingInstallment(plan, new Set());
      
      expect(next).toBeDefined();
      expect(next?.day).toBe(1);
    });

    it('should skip completed installments', () => {
      const plan = createTestPlan('high');
      const completed = new Set([1, 2, 3]);
      const next = getNextPendingInstallment(plan, completed);
      
      expect(next).toBeDefined();
      expect(next?.day).toBe(4);
    });

    it('should return null when all completed', () => {
      const plan = createTestPlan('mini');
      const completed = new Set(plan.schedule.map(s => s.day));
      const next = getNextPendingInstallment(plan, completed);
      
      expect(next).toBeNull();
    });
  });

  describe('canPausePlan / canResumePlan', () => {
    it('should allow pausing active plans', () => {
      const plan = createTestPlan('high');
      plan.status = 'active';
      
      expect(canPausePlan(plan)).toBe(true);
      expect(canResumePlan(plan)).toBe(false);
    });

    it('should allow resuming paused plans', () => {
      const plan = createTestPlan('high');
      plan.status = 'paused';
      
      expect(canPausePlan(plan)).toBe(false);
      expect(canResumePlan(plan)).toBe(true);
    });

    it('should not allow pause/resume for other statuses', () => {
      const statuses: Array<FlexPayPlan['status']> = ['completed', 'cancelled', 'failed'];
      
      for (const status of statuses) {
        const plan = createTestPlan('mini');
        plan.status = status;
        
        expect(canPausePlan(plan)).toBe(false);
        expect(canResumePlan(plan)).toBe(false);
      }
    });
  });

  describe('calculateRetryDelay', () => {
    it('should calculate exponential backoff delays', () => {
      // First failure: 1 hour
      expect(calculateRetryDelay(0)).toBe(60 * 60 * 1000);
      
      // Second failure: 2 hours
      expect(calculateRetryDelay(1)).toBe(2 * 60 * 60 * 1000);
      
      // Third failure: 4 hours
      expect(calculateRetryDelay(2)).toBe(4 * 60 * 60 * 1000);
    });

    it('should cap delay at 24 hours', () => {
      // After many failures, should cap at 24 hours
      const maxDelay = 24 * 60 * 60 * 1000;
      expect(calculateRetryDelay(10)).toBe(maxDelay);
      expect(calculateRetryDelay(100)).toBe(maxDelay);
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  // ERROR HANDLING TESTS
  // ═══════════════════════════════════════════════════════════════════

  describe('Error Handling', () => {
    it('should throw error for zero or negative amounts', () => {
      expect(() => calculateInstallmentSchedule(0, 'mini')).toThrow(
        'Total amount must be greater than zero'
      );
      expect(() => calculateInstallmentSchedule(-100, 'mini')).toThrow(
        'Total amount must be greater than zero'
      );
    });

    it('should throw error for invalid tier', () => {
      expect(() => 
        calculateInstallmentSchedule(999, 'invalid' as VariantTier)
      ).toThrow(/Invalid tier/);
    });

    it('should warn but not throw for amounts differing from tier price', () => {
      const warnSpy = jest.spyOn(console, 'warn').mockImplementation();
      
      // This should work but log a warning
      const schedule = calculateInstallmentSchedule(1500, 'mini'); // Not standard mini price
      
      expect(schedule).toBeDefined();
      expect(warnSpy).toHaveBeenCalled();
      
      warnSpy.mockRestore();
    });
  });

  // ═══════════════════════════════════════════════════════════════════
  // CONSTANT VALIDATION TESTS
  // ═══════════════════════════════════════════════════════════════════

  describe('Constants', () => {
    it('should have valid exchange rate configuration', () => {
      expect(EXCHANGE_RATE_USD_TO_INR).toBeGreaterThan(0);
      expect(RAZORPAY_MAX_INR_LIMIT).toBeGreaterThan(0);
      
      // Verify base daily amount converts to under limit
      const baseInr = BASE_DAILY_AMOUNT * EXCHANGE_RATE_USD_TO_INR;
      expect(baseInr).toBeLessThan(RAZORPAY_MAX_INR_LIMIT);
    });

    it('should have valid collection window', () => {
      expect(COLLECTION_WINDOW_DAYS).toBe(30);
      expect(DOUBLE_CHARGE_INTERVAL).toBe(3);
      expect(DOUBLE_CHARGE_HOUR_GAP).toBe(2);
    });

    it('should have correct tier prices', () => {
      expect(TIER_PRICES.mini).toBe(999);
      expect(TIER_PRICES.parwa).toBe(2499);
      expect(TIER_PRICES.high).toBe(3999);
    });
  });
});
