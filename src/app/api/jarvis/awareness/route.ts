/**
 * JARVIS Awareness Engine API Routes (Week 2 - Phase 1)
 *
 * REST API endpoints for the JARVIS awareness system.
 * Provides access to alerts, health, activity, sentiment, and metrics.
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAwarenessEngine } from '@/lib/jarvis/awareness';

// ── Helper: Get tenant context from request ───────────────────────────

function getTenantContext(request: NextRequest): { tenantId: string; variant: 'mini_parwa' | 'parwa' | 'parwa_high' } {
  // In production, this would come from authenticated session
  // For now, use headers or defaults
  const tenantId = request.headers.get('x-tenant-id') || 'default';
  const variant = (request.headers.get('x-variant') as 'mini_parwa' | 'parwa' | 'parwa_high') || 'parwa';

  return { tenantId, variant };
}

// ── GET: Get Awareness State ─────────────────────────────────────────

export async function GET(request: NextRequest) {
  try {
    const { tenantId, variant } = getTenantContext(request);
    const { searchParams } = new URL(request.url);
    const action = searchParams.get('action') || 'state';

    const engine = await getAwarenessEngine({ tenant_id: tenantId, variant });

    switch (action) {
      case 'state':
        return NextResponse.json({
          success: true,
          data: engine.getState(),
        });

      case 'health':
        const health = await engine.getSystemHealth();
        return NextResponse.json({
          success: true,
          data: health,
        });

      case 'alerts':
        const severity = searchParams.get('severity') as 'critical' | 'warning' | 'info' | 'opportunity' | null;
        const type = searchParams.get('type') as any;
        const alerts = engine.getActiveAlerts({
          severity: severity || undefined,
          type: type || undefined,
        });
        return NextResponse.json({
          success: true,
          data: {
            alerts,
            total: alerts.length,
          },
        });

      case 'sentiment':
        const period = (searchParams.get('period') as 'hour' | 'day' | 'week') || 'day';
        const trend = engine.getSentimentTrend(period);
        return NextResponse.json({
          success: true,
          data: trend,
        });

      case 'metrics':
        const metricName = searchParams.get('metric') || 'ticket.count';
        const aggregation = (searchParams.get('aggregation') as 'sum' | 'avg' | 'min' | 'max' | 'count' | 'p95' | 'p99') || 'avg';
        const periodMs = parseInt(searchParams.get('period_ms') || '3600000', 10);
        const metric = engine.getAggregatedMetric(metricName, aggregation, periodMs);
        return NextResponse.json({
          success: true,
          data: metric,
        });

      default:
        return NextResponse.json({
          success: false,
          error: `Unknown action: ${action}`,
        }, { status: 400 });
    }
  } catch (error) {
    console.error('[Awareness API] GET error:', error);
    return NextResponse.json({
      success: false,
      error: 'Internal server error',
    }, { status: 500 });
  }
}

// ── POST: Perform Actions ─────────────────────────────────────────────

export async function POST(request: NextRequest) {
  try {
    const { tenantId, variant } = getTenantContext(request);
    const body = await request.json();
    const { action, ...params } = body;

    const engine = await getAwarenessEngine({ tenant_id: tenantId, variant });

    switch (action) {
      case 'acknowledge_alert':
        if (!params.alert_id || !params.acknowledged_by) {
          return NextResponse.json({
            success: false,
            error: 'Missing alert_id or acknowledged_by',
          }, { status: 400 });
        }
        const acknowledged = await engine.acknowledgeAlert(
          params.alert_id,
          params.acknowledged_by,
          params.notes
        );
        return NextResponse.json({
          success: true,
          data: acknowledged,
        });

      case 'resolve_alert':
        if (!params.alert_id) {
          return NextResponse.json({
            success: false,
            error: 'Missing alert_id',
          }, { status: 400 });
        }
        const resolved = await engine.resolveAlert(params.alert_id, params.resolved_by);
        return NextResponse.json({
          success: true,
          data: resolved,
        });

      case 'track_activity':
        if (!params.customer_id || !params.activity_type || !params.channel) {
          return NextResponse.json({
            success: false,
            error: 'Missing required fields: customer_id, activity_type, channel',
          }, { status: 400 });
        }
        await engine.trackCustomerActivity({
          customer_id: params.customer_id,
          activity_type: params.activity_type,
          channel: params.channel,
          ticket_id: params.ticket_id,
          agent_id: params.agent_id,
          content: params.content,
        });
        return NextResponse.json({
          success: true,
          message: 'Activity tracked',
        });

      case 'analyze_sentiment':
        if (!params.text) {
          return NextResponse.json({
            success: false,
            error: 'Missing text field',
          }, { status: 400 });
        }
        const sentiment = await engine.analyzeSentiment(params.text, params.customer_id);
        return NextResponse.json({
          success: true,
          data: sentiment,
        });

      case 'record_metric':
        if (!params.name || params.value === undefined) {
          return NextResponse.json({
            success: false,
            error: 'Missing name or value',
          }, { status: 400 });
        }
        engine.recordMetric(params.name, params.value, params.tags);
        return NextResponse.json({
          success: true,
          message: 'Metric recorded',
        });

      case 'register_health_component':
        if (!params.name || !params.check) {
          return NextResponse.json({
            success: false,
            error: 'Missing component name or check function',
          }, { status: 400 });
        }
        engine.registerHealthComponent({
          name: params.name,
          check: params.check,
          thresholds: params.thresholds,
          intervalMs: params.interval_ms,
        });
        return NextResponse.json({
          success: true,
          message: 'Health component registered',
        });

      default:
        return NextResponse.json({
          success: false,
          error: `Unknown action: ${action}`,
        }, { status: 400 });
    }
  } catch (error) {
    console.error('[Awareness API] POST error:', error);
    return NextResponse.json({
      success: false,
      error: 'Internal server error',
    }, { status: 500 });
  }
}

// ── Customer Summary Endpoint ────────────────────────────────────────

export async function PUT(request: NextRequest) {
  try {
    const { tenantId, variant } = getTenantContext(request);
    const { searchParams } = new URL(request.url);
    const customerId = searchParams.get('customer_id');

    if (!customerId) {
      return NextResponse.json({
        success: false,
        error: 'Missing customer_id',
      }, { status: 400 });
    }

    const engine = await getAwarenessEngine({ tenant_id: tenantId, variant });
    const summary = await engine.getCustomerSummary(customerId);

    return NextResponse.json({
      success: true,
      data: summary,
    });
  } catch (error) {
    console.error('[Awareness API] PUT error:', error);
    return NextResponse.json({
      success: false,
      error: 'Internal server error',
    }, { status: 500 });
  }
}
