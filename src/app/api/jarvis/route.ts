/**
 * JARVIS Unified API Route - Week 4 (Phase 1)
 *
 * Main API endpoint for JARVIS operations.
 * Provides unified access to the complete JARVIS functionality.
 */

import { NextRequest, NextResponse } from 'next/server';
import {
  getJarvisOrchestrator,
  shutdownJarvisOrchestrator,
} from '@/lib/jarvis/integration/jarvis-orchestrator';
import type { Variant } from '@/types/variant';
import type { ProcessJarvisCommandResponse } from '@/lib/jarvis/integration/types';

// ── Request Types ──────────────────────────────────────────────────

interface ProcessRequest {
  command: string;
  sessionId?: string;
  context?: {
    currentPage?: string;
    activeTicketId?: string;
    activeCustomerId?: string;
    filters?: Record<string, unknown>;
  };
  forceMode?: 'direct' | 'draft';
}

interface ApproveRequest {
  draftId: string;
  sessionId: string;
  comment?: string;
}

interface RejectRequest {
  draftId: string;
  sessionId: string;
  reason?: string;
}

interface EndSessionRequest {
  sessionId: string;
}

// ── Helper Functions ───────────────────────────────────────────────

function getOrganizationId(request: NextRequest): string {
  // Extract organization ID from headers or use default
  return request.headers.get('x-organization-id') || 'default_org';
}

function getUserId(request: NextRequest): string {
  // Extract user ID from headers or auth token
  return request.headers.get('x-user-id') || 'anonymous';
}

function getUserRole(request: NextRequest): string {
  // Extract user role from headers
  return request.headers.get('x-user-role') || 'agent';
}

function getVariant(request: NextRequest): Variant {
  // Extract variant from headers or subscription
  const variant = request.headers.get('x-variant') as Variant;
  return variant || 'parwa';
}

function getClientInfo(request: NextRequest) {
  return {
    ipAddress: request.headers.get('x-forwarded-for') || 
               request.headers.get('x-real-ip') ||
               'unknown',
    userAgent: request.headers.get('user-agent') || 'unknown',
  };
}

// ── POST Handler ───────────────────────────────────────────────────

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const organizationId = getOrganizationId(request);
    const userId = getUserId(request);
    const userRole = getUserRole(request);
    const variant = getVariant(request);
    const clientInfo = getClientInfo(request);

    // Get or create orchestrator
    const orchestrator = getJarvisOrchestrator({
      organizationId,
      variant,
      debug: process.env.NODE_ENV === 'development',
    });

    // Initialize if needed
    await orchestrator.initialize();

    // Handle different action types
    const action = body.action || 'process';

    switch (action) {
      case 'process': {
        const processData: ProcessRequest = body;
        
        const response = await orchestrator.processCommand({
          command: processData.command,
          sessionId: processData.sessionId,
          userId,
          userRole,
          context: processData.context,
          forceMode: processData.forceMode,
        });

        return NextResponse.json({
          success: true,
          ...response,
        });
      }

      case 'approve': {
        const approveData: ApproveRequest = body;
        
        const response = await orchestrator.approveDraft(
          approveData.draftId,
          approveData.sessionId,
          userId,
          approveData.comment
        );

        return NextResponse.json({
          success: true,
          ...response,
        });
      }

      case 'reject': {
        const rejectData: RejectRequest = body;
        
        const response = await orchestrator.rejectDraft(
          rejectData.draftId,
          rejectData.sessionId,
          userId,
          rejectData.reason
        );

        return NextResponse.json({
          success: true,
          ...response,
        });
      }

      case 'end_session': {
        const endData: EndSessionRequest = body;
        
        await orchestrator.endSession(endData.sessionId, userId);

        return NextResponse.json({
          success: true,
          message: 'Session ended',
        });
      }

      case 'acknowledge_alert': {
        const { alertId, sessionId } = body;
        
        const result = await orchestrator.acknowledgeAlert(
          alertId,
          userId,
          sessionId
        );

        return NextResponse.json({
          success: result,
          message: result ? 'Alert acknowledged' : 'Failed to acknowledge alert',
        });
      }

      default:
        return NextResponse.json(
          { success: false, error: 'Invalid action' },
          { status: 400 }
        );
    }
  } catch (error) {
    console.error('JARVIS API error:', error);
    
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : 'Internal server error',
      },
      { status: 500 }
    );
  }
}

// ── GET Handler ─────────────────────────────────────────────────────

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const organizationId = getOrganizationId(request);
    const variant = getVariant(request);
    const action = searchParams.get('action') || 'health';

    // Get or create orchestrator
    const orchestrator = getJarvisOrchestrator({
      organizationId,
      variant,
      debug: process.env.NODE_ENV === 'development',
    });

    switch (action) {
      case 'health': {
        const health = await orchestrator.getHealth();
        return NextResponse.json({
          success: true,
          health,
        });
      }

      case 'state': {
        const sessionId = searchParams.get('sessionId');
        
        if (sessionId) {
          const session = orchestrator.getSession(sessionId);
          return NextResponse.json({
            success: true,
            session,
          });
        }

        const awarenessState = await orchestrator.getAwarenessState();
        return NextResponse.json({
          success: true,
          state: awarenessState,
        });
      }

      case 'alerts': {
        const alerts = await orchestrator.getPendingAlerts();
        return NextResponse.json({
          success: true,
          alerts,
        });
      }

      case 'capabilities': {
        const capabilities = orchestrator.getCapabilities();
        return NextResponse.json({
          success: true,
          capabilities,
        });
      }

      case 'stats': {
        const stats = orchestrator.getStats();
        return NextResponse.json({
          success: true,
          stats,
        });
      }

      default:
        return NextResponse.json(
          { success: false, error: 'Invalid action' },
          { status: 400 }
        );
    }
  } catch (error) {
    console.error('JARVIS API error:', error);
    
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : 'Internal server error',
      },
      { status: 500 }
    );
  }
}

// ── DELETE Handler ──────────────────────────────────────────────────

export async function DELETE(request: NextRequest) {
  try {
    const organizationId = getOrganizationId(request);
    
    // Shutdown orchestrator for this organization
    await shutdownJarvisOrchestrator(organizationId);

    return NextResponse.json({
      success: true,
      message: 'JARVIS shutdown complete',
    });
  } catch (error) {
    console.error('JARVIS shutdown error:', error);
    
    return NextResponse.json(
      {
        success: false,
        error: error instanceof Error ? error.message : 'Internal server error',
      },
      { status: 500 }
    );
  }
}
