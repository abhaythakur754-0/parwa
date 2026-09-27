/**
 * PARWA Knowledge Base List API
 * 
 * GET /api/kb/list - List all available knowledge bases (for connection)
 * Shows both user's own KBs and available CRM KBs
 */

import { NextRequest, NextResponse } from 'next/server';
import { getKnowledgeBases, connectExistingKB } from '@/lib/supabase-db';

function getUserId(req: NextRequest): string | null {
  const authHeader = req.headers.get('authorization');
  if (authHeader) return authHeader.replace('Bearer ', '');

  const cookieHeader = req.headers.get('cookie');
  if (cookieHeader) {
    const cookies = Object.fromEntries(
      cookieHeader.split(';').map((c) => {
        const [key, ...val] = c.trim().split('=');
        return [key, val.join('=')];
      })
    );
    if (cookies.parwa_at) return cookies.parwa_at;
    if (cookies.user_id) return cookies.user_id;
  }

  const url = new URL(req.url);
  return url.searchParams.get('user_id');
}

// Mock CRM knowledge bases that can be connected
// In production, these would come from your actual CRM integrations
const AVAILABLE_CRM_KBS = [
  {
    id: 'crm-hubspot-001',
    name: 'HubSpot Knowledge Base',
    crm_type: 'hubspot',
    description: 'Articles, FAQs, and documentation from HubSpot',
    document_count: 150,
    status: 'active',
    source_url: 'https://knowledge.hubspot.com',
  },
  {
    id: 'crm-salesforce-001',
    name: 'Salesforce Knowledge Base',
    crm_type: 'salesforce',
    description: 'Salesforce help articles and product docs',
    document_count: 280,
    status: 'active',
    source_url: 'https://help.salesforce.com',
  },
  {
    id: 'crm-zoho-001',
    name: 'Zoho CRM Knowledge Base',
    crm_type: 'zoho',
    description: 'Zoho product documentation and FAQs',
    document_count: 95,
    status: 'active',
    source_url: 'https://www.zoho.com/crm/help/',
  },
  {
    id: 'crm-flexpay-default',
    name: 'FlexPay Default KB (CRM)',
    crm_type: 'flexpay_crm',
    description: 'Default FlexPay CRM knowledge base with customer support articles',
    document_count: 50,
    status: 'active',
    source_url: null,
    is_default: true,
  },
];

export async function GET(request: NextRequest) {
  try {
    const userId = getUserId(request);
    
    // If no user ID, return only public/available KBs
    if (!userId) {
      return NextResponse.json({
        success: true,
        data: {
          user_kbs: [],
          available_crm_kbs: AVAILABLE_CRM_KBS,
        },
      });
    }

    // Get user's existing KBs from Supabase
    const userKbs = await getKnowledgeBases(userId);

    console.log(`[KB] Listed ${userKbs?.length || 0} KBs for user ${userId}`);

    return NextResponse.json({
      success: true,
      data: {
        user_kbs: userKbs || [],
        available_crm_kbs: AVAILABLE_CRM_KBS,
      },
      message: 'Knowledge bases retrieved successfully',
    });
  } catch (error) {
    console.error('[KB API] Error listing:', error);
    
    // Return mock data on error (graceful fallback)
    return NextResponse.json({
      success: true,
      data: {
        user_kbs: [],
        available_crm_kbs: AVAILABLE_CRM_KBS,
      },
      warning: 'Using fallback data (database unavailable)',
    });
  }
}
