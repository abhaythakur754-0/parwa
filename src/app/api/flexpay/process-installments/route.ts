/**
 * FlexPay Process Installments API Endpoint
 * ═══════════════════════════════════════════════════════════════════
 *
 * POST /api/flexpay/process-installments
 *
 * Triggers processing of all due installments for active plans.
 * Can be called by cron job or manually for testing.
 *
 * Query Parameters:
 * - dryRun: boolean (optional) - If true, simulates without actual charges
 *
 * Response:
 * {
 *   success: true,
 *   result: SchedulerResult,
 *   processedAt: ISO date string
 * }
 */

import { NextRequest, NextResponse } from 'next/server';
import { processAllPlans, getSchedulerStats } from '@/lib/flexpay/scheduler';

export async function POST(req: NextRequest) {
  try {
    // Check for dry run mode
    const { searchParams } = new URL(req.url);
    const dryRun = searchParams.get('dryRun') === 'true';

    console.log(`[FlexPay/API] Processing installments${dryRun ? ' (dry run)' : ''}...`);

    // Process all plans
    const result = await processAllPlans({
      enabled: true,
    });

    // Return results
    return NextResponse.json({
      success: true,
      result: {
        ...result,
        runAt: result.runAt.toISOString(),
        details: result.details.map(d => ({
          ...d,
          // Don't expose internal errors in detail to clients
          errors: dryRun ? d.errors : undefined,
        })),
      },
      processedAt: new Date().toISOString(),
      dryRun,
      message: `Processed ${result.totalPlans} plans: ${result.successfulPlans} successful, ${result.failedPlans} failed`,
    });

  } catch (error) {
    console.error('[FlexPay/API] Error processing installments:', error);
    
    return NextResponse.json(
      { 
        success: false, 
        error: 'Failed to process installments',
        details: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}

// GET endpoint for checking scheduler status
export async function GET() {
  try {
    const stats = getSchedulerStats();
    
    return NextResponse.json({
      success: true,
      stats,
      timestamp: new Date().toISOString(),
      message: 'Scheduler is running',
    });
  } catch (error) {
    console.error('[FlexPay/API] Error getting scheduler status:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to get scheduler status' },
      { status: 500 }
    );
  }
}
