/**
 * FakeCRM Proxy API Route
 * 
 * Proxies requests to the FakeCRM mini-service (port 8888)
 * This makes FakeCRM accessible through the ZAI domain
 * 
 * Usage: /api/fake-crm/health
 *        /api/fake-crm/analytics/overview
 *        /api/fake-crm/crm/v3/objects/contacts
 */

import { NextRequest, NextResponse } from 'next/server';

const FAKE_CRM_PORT = 8888;
const FAKE_CRM_HOST = `http://localhost:${FAKE_CRM_PORT}`;

export async function GET(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  
  // Remove /api/fake-crm prefix to get the actual FakeCRM path
  const fakeCrmPath = pathname.replace(/^\/api\/fake-crm/, '') || '/';
  
  // Build the target URL
  const targetUrl = `${FAKE_CRM_HOST}${fakeCrmPath}?${searchParams.toString()}`;
  
  console.log(`[FakeCRM Proxy] GET ${fakeCrmPath} -> ${targetUrl}`);
  
  try {
    const response = await fetch(targetUrl, {
      method: 'GET',
      headers: {
        'Authorization': request.headers.get('authorization') || '',
        'Content-Type': 'application/json',
      },
    });
    
    const data = await response.json();
    
    return NextResponse.json(data, {
      status: response.status,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'X-Fake-CRM-Proxied': 'true',
        'X-Original-Path': fakeCrmPath,
      },
    });
  } catch (error) {
    console.error('[FakeCRM Proxy] Error:', error);
    return NextResponse.json(
      { error: 'FakeCRM service unavailable', details: error instanceof Error ? error.message : 'Unknown error' },
      { status: 502 }
    );
  }
}

export async function POST(request: NextRequest) {
  const { pathname, searchParams } = request.nextUrl;
  
  const fakeCrmPath = pathname.replace(/^\/api\/fake-crm/, '') || '/';
  const targetUrl = `${FAKE_CRM_HOST}${fakeCrmPath}?${searchParams.toString()}`;
  
  console.log(`[FakeCRM Proxy] POST ${fakeCrmPath} -> ${targetUrl}`);
  
  try {
    const body = await request.json();
    
    const response = await fetch(targetUrl, {
      method: 'POST',
      headers: {
        'Authorization': request.headers.get('authorization') || '',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });
    
    const data = await response.json();
    
    return NextResponse.json(data, {
      status: response.status,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'X-Fake-CRM-Proxied': 'true',
      },
    });
  } catch (error) {
    console.error('[FakeCRM Proxy] Error:', error);
    return NextResponse.json(
      { error: 'FakeCRM service unavailable' },
      { status: 502 }
    );
  }
}

// Handle OPTIONS for CORS preflight
export async function OPTIONS() {
  return new NextResponse(null, {
    status: 200,
    headers: {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    },
  });
}
