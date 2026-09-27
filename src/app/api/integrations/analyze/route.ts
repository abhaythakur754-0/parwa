/**
 * POST /api/integrations/analyze
 *
 * Analyzes connected integrations and recommends missing ones.
 * Falls back to local analysis if backend is unavailable.
 *
 * Business Value:
 * - Reduces user confusion about which integrations they need
 * - Increases activation rate (more integrations = more value)
 * - Personalized recommendations based on actual data patterns
 */

import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://parwa-backend.onrender.com';

// Fallback recommendations when backend is unavailable or no integrations connected
function getFallbackRecommendations(industry?: string, connectedCount?: number): any {
  const allRecommendations = [
    {
      integration_key: 'stripe',
      name: 'Stripe',
      category: 'payments',
      priority: 'high',
      reason: 'Track payments, subscriptions, and MRR in real-time',
      business_impact: 'Complete revenue visibility across your business',
      icon_id: 'stripe',
      color_gradient: 'from-blue-500 to-purple-600',
      already_connected: false,
    },
    {
      integration_key: 'mailchimp',
      name: 'Mailchimp',
      category: 'marketing',
      priority: 'high',
      reason: 'Automate email nurturing and lead scoring campaigns',
      business_impact: 'Convert 23% more leads with automated sequences',
      icon_id: 'mailchimp',
      color_gradient: 'from-yellow-400 to-orange-500',
      already_connected: false,
    },
    {
      integration_key: 'slack',
      name: 'Slack',
      category: 'communication',
      priority: 'medium',
      reason: 'Get instant alerts when deals close or tickets escalate',
      business_impact: 'Reduce response time by 40%',
      icon_id: 'slack',
      color_gradient: 'from-purple-500 to-pink-500',
      already_connected: false,
    },
    {
      integration_key: 'mixpanel',
      name: 'Mixpanel',
      category: 'analytics',
      priority: 'medium',
      reason: 'Understand how users interact with your products',
      business_impact: 'Data-driven product decisions and funnel optimization',
      icon_id: 'mixpanel',
      color_gradient: 'from-cyan-400 to-blue-500',
      already_connected: false,
    },
    {
      integration_key: 'zendesk',
      name: 'Zendesk',
      category: 'helpdesk',
      priority: 'medium',
      reason: 'Full support workflow automation with knowledge base',
      business_impact: 'Reduce ticket resolution time by 35%',
      icon_id: 'zendesk',
      color_gradient: 'from-green-500 to-teal-500',
      already_connected: false,
    },
  ];

  return {
    company_id: 'fallback_' + Date.now(),
    analyzed_at: new Date().toISOString(),
    connected_integrations: [],
    data_profile: {
      total_contacts: 0,
      total_orders: 0,
      total_deals: 0,
      has_products: false,
      has_shipping_addresses: false,
      has_payment_data: false,
      has_email_campaigns: false,
      has_ticket_data: false,
      industries_detected: [industry || 'unknown'],
      business_type: industry ? `${industry} Business` : 'General',
      data_maturity: 'starting',
    },
    detected_gaps: [
      {
        id: 'gap_001',
        severity: 'high',
        category: 'payments',
        message: 'No payment processing integration connected',
        impact: 'Cannot track revenue automatically',
        recommended: ['stripe', 'razorpay'],
      },
      {
        id: 'gap_002',
        severity: 'high',
        category: 'marketing',
        message: 'No email marketing automation connected',
        impact: 'Missing lead nurturing capabilities',
        recommended: ['mailchimp', 'klaviyo'],
      },
      {
        id: 'gap_003',
        severity: 'medium',
        category: 'communication',
        message: 'No team communication tool connected',
        impact: 'No real-time notifications for team',
        recommended: ['slack'],
      },
    ],
    recommendations: allRecommendations.slice(0, connectedCount === 0 ? 5 : 3),
    analysis_summary: 
      connectedCount === 0
        ? `You haven't connected any integrations yet. Based on ${industry || 'general'} business needs, we recommend starting with these essential tools to maximize your workflow efficiency.`
        : `Based on your ${connectedCount} connected integration(s), here are additional tools we recommend to complete your stack.`,
    metrics: {
      total_recommendations: allRecommendations.length,
      high_priority: 2,
      medium_priority: 3,
      low_priority: 0,
    },
    is_fallback: true,
  };
}

export async function POST(request: NextRequest) {
  try {
    // Get request body
    let body = {};
    try {
      body = await request.json();
    } catch {
      // No body, that's ok
    }

    const { industry, connected_count = 0 } = body as { industry?: string; connected_count?: number };

    // Try backend first
    try {
      const authHeader = request.headers.get('authorization');
      
      const response = await fetch(`${BACKEND_URL}/api/crm/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authHeader ? { Authorization: authHeader } : {}),
          'Cookie': request.headers.get('cookie') || '',
          'Origin': 'https://parwa.buzz',
          'Referer': 'https://parwa.buzz/dashboard/integrations',
        },
        body: JSON.stringify(body),
      });

      if (response.ok) {
        const data = await response.json();
        return NextResponse.json(data);
      }
      
      // Backend returned error - log but continue to fallback
      console.warn('Backend analyze error:', response.status, await response.text().catch(() => ''));
    } catch (backendError) {
      console.warn('Backend unavailable, using fallback:', backendError);
    }

    // Use fallback recommendations
    const fallbackData = getFallbackRecommendations(industry, connected_count);
    
    return NextResponse.json(fallbackData);

  } catch (error) {
    console.error('CRM Analysis error:', error);
    return NextResponse.json(
      { error: 'Failed to analyze integrations' },
      { status: 500 }
    );
  }
}
