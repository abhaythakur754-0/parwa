import { NextRequest, NextResponse } from 'next/server';
import { proxyToBackend } from '@/lib/bff-proxy';

/**
 * Approvals proxy route.
 * Forwards /api/approvals/* to backend /api/approvals/*
 */

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const fullPath = path.join('/');
  const url = new URL(request.url);
  const qs = url.searchParams.toString();
  return proxyToBackend(`/api/approvals/${fullPath}${qs ? `?${qs}` : ''}`, 'GET', request);
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const fullPath = path.join('/');
  const url = new URL(request.url);
  const qs = url.searchParams.toString();
  return proxyToBackend(`/api/approvals/${fullPath}${qs ? `?${qs}` : ''}`, 'POST', request);
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const fullPath = path.join('/');
  const url = new URL(request.url);
  const qs = url.searchParams.toString();
  return proxyToBackend(`/api/approvals/${fullPath}${qs ? `?${qs}` : ''}`, 'PATCH', request);
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const fullPath = path.join('/');
  const url = new URL(request.url);
  const qs = url.searchParams.toString();
  return proxyToBackend(`/api/approvals/${fullPath}${qs ? `?${qs}` : ''}`, 'DELETE', request);
}
