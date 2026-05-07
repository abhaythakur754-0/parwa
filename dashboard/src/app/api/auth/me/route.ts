import { NextResponse } from 'next/server';

export async function GET() {
  // Mock /api/auth/me endpoint — returns user from Authorization header or a default user
  return NextResponse.json({
    id: 'usr_mock_1',
    email: 'demo@parwa.ai',
    full_name: 'Demo User',
    phone: null,
    avatar_url: null,
    role: 'admin',
    is_active: true,
    is_verified: true,
    company_id: 'comp_mock_1',
    company_name: 'Demo Corp',
    onboarding_completed: true,
    created_at: new Date().toISOString(),
  });
}
