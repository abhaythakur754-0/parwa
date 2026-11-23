/**
 * SHOBH Knowledge Base Connect API
 * 
 * POST /api/kb/connect - Connect to an existing knowledge base
 * Can connect to:
 * - CRM KBs (HubSpot, Salesforce, Zoho)
 * - Existing uploaded KBs
 * - Default FlexPay CRM KB
 */

import { NextRequest, NextResponse } from 'next/server';
import { getAuthenticatedUserId } from '@/lib/api-auth';
import { connectExistingKB, createKnowledgeBase } from '@/lib/supabase-db';

export async function POST(request: NextRequest) {
  let userId: string | null = null;
  let body: any = {};
  try {
    userId = await getAuthenticatedUserId(request);

    if (!userId) {
      return NextResponse.json(
        { error: 'unauthorized', message: 'User not authenticated' },
        { status: 401 }
      );
    }

    body = await request.json();
    const { kb_id, name, crm_type, source_url } = body;

    // Validate required fields
    if (!kb_id && !name) {
      return NextResponse.json(
        { error: 'validation_error', message: 'Either kb_id or name is required' },
        { status: 400 }
      );
    }

    console.log(`[KB] Connecting user ${userId} to KB:`, { kb_id, crm_type, name });

    // Create linked KB entry in database
    const connectedKb = await connectExistingKB(
      userId,
      kb_id || `custom-${Date.now()}`,
      name || `Connected KB (${crm_type})`,
      crm_type,
    );

    // If source_url provided, we could fetch and sync documents here
    // For now, just mark as active

    console.log(`[KB] ✅ Connected successfully! ID: ${connectedKb?.id}`);

    return NextResponse.json({
      success: true,
      data: connectedKb,
      message: `Successfully connected to ${name || crm_type || 'knowledge base'}`,
      status: 'connected',
    });
  } catch (error) {
    console.error('[KB Connect Error]:', error);
    return NextResponse.json(
      { error: 'internal_error', message: 'Unable to connect knowledge base' },
      { status: 500 }
    );
  }
}
