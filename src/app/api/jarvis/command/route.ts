/**
 * JARVIS Command Processing API Routes (Week 3 - Phase 1)
 *
 * REST API endpoints for the JARVIS command processing system.
 * Provides access to command processing, drafts, and approvals.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getCommandProcessor } from '@/lib/jarvis/command';

// ── Helper: Get tenant context from request ───────────────────────────

function getTenantContext(request: NextRequest): {
  tenantId: string;
  variant: 'mini_parwa' | 'parwa' | 'parwa_high';
} {
  const tenantId = request.headers.get('x-tenant-id') || 'default';
  const variant = (request.headers.get('x-variant') as 'mini_parwa' | 'parwa' | 'parwa_high') || 'parwa';

  return { tenantId, variant };
}

// ── GET: Get Commands and Suggestions ────────────────────────────────

export async function GET(request: NextRequest) {
  try {
    const { tenantId, variant } = getTenantContext(request);
    const { searchParams } = new URL(request.url);
    const action = searchParams.get('action') || 'available';

    const processor = await getCommandProcessor({ tenant_id: tenantId, variant });

    switch (action) {
      case 'available':
        const commands = processor.getAvailableCommands();
        return NextResponse.json({
          success: true,
          data: { commands, total: commands.length },
        });

      case 'suggestions':
        const text = searchParams.get('text') || '';
        const sessionId = searchParams.get('session_id') || 'default';
        const suggestions = processor.getSuggestions(text, sessionId);
        return NextResponse.json({
          success: true,
          data: { suggestions },
        });

      case 'context':
        const ctxSessionId = searchParams.get('session_id') || 'default';
        const contextSummary = processor.getContextSummary(ctxSessionId);
        return NextResponse.json({
          success: true,
          data: { context: contextSummary },
        });

      case 'approvals':
        const userId = searchParams.get('user_id') || '';
        const userRole = searchParams.get('user_role') || 'agent';
        const approvals = processor.getPendingApprovals(userId, userRole);
        return NextResponse.json({
          success: true,
          data: { approvals, total: approvals.length },
        });

      default:
        return NextResponse.json({
          success: false,
          error: `Unknown action: ${action}`,
        }, { status: 400 });
    }
  } catch (error) {
    console.error('[Command API] GET error:', error);
    return NextResponse.json({
      success: false,
      error: 'Internal server error',
    }, { status: 500 });
  }
}

// ── POST: Process Command ─────────────────────────────────────────────

export async function POST(request: NextRequest) {
  try {
    const { tenantId, variant } = getTenantContext(request);
    const body = await request.json();
    const { action, ...params } = body;

    const processor = await getCommandProcessor({ tenant_id: tenantId, variant });

    switch (action) {
      case 'process':
        if (!params.text || !params.session_id) {
          return NextResponse.json({
            success: false,
            error: 'Missing required fields: text, session_id',
          }, { status: 400 });
        }

        const result = await processor.process({
          text: params.text,
          session_id: params.session_id,
          context: params.context,
        });

        return NextResponse.json({
          success: true,
          data: result,
        });

      case 'approve_draft':
        if (!params.draft_id || !params.approved_by) {
          return NextResponse.json({
            success: false,
            error: 'Missing required fields: draft_id, approved_by',
          }, { status: 400 });
        }

        const approveResult = await processor.approveDraft(
          params.draft_id,
          params.approved_by,
          params.comment
        );

        return NextResponse.json({
          success: approveResult.success,
          data: approveResult,
        });

      case 'reject_draft':
        if (!params.draft_id || !params.rejected_by || !params.reason) {
          return NextResponse.json({
            success: false,
            error: 'Missing required fields: draft_id, rejected_by, reason',
          }, { status: 400 });
        }

        const rejectResult = processor.rejectDraft(
          params.draft_id,
          params.rejected_by,
          params.reason
        );

        return NextResponse.json({
          success: rejectResult.success,
          data: rejectResult,
        });

      default:
        return NextResponse.json({
          success: false,
          error: `Unknown action: ${action}`,
        }, { status: 400 });
    }
  } catch (error) {
    console.error('[Command API] POST error:', error);
    return NextResponse.json({
      success: false,
      error: 'Internal server error',
    }, { status: 500 });
  }
}

// ── DELETE: Clear Session ─────────────────────────────────────────────

export async function DELETE(request: NextRequest) {
  try {
    const { tenantId, variant } = getTenantContext(request);
    const { searchParams } = new URL(request.url);
    const sessionId = searchParams.get('session_id');

    if (!sessionId) {
      return NextResponse.json({
        success: false,
        error: 'Missing session_id',
      }, { status: 400 });
    }

    const processor = await getCommandProcessor({ tenant_id: tenantId, variant });
    processor.clearSession(sessionId);

    return NextResponse.json({
      success: true,
      message: 'Session cleared',
    });
  } catch (error) {
    console.error('[Command API] DELETE error:', error);
    return NextResponse.json({
      success: false,
      error: 'Internal server error',
    }, { status: 500 });
  }
}
