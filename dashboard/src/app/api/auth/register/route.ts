import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { email, password, full_name, company_name } = body;

    if (!email || !password || !full_name || !company_name) {
      return NextResponse.json(
        { detail: 'Email, password, full name, and company name are required' },
        { status: 400 }
      );
    }

    // Mock successful registration
    const mockUser = {
      id: 'usr_mock_' + Date.now(),
      email: email,
      full_name: full_name,
      phone: null,
      avatar_url: null,
      role: 'admin',
      is_active: true,
      is_verified: false,
      company_id: 'comp_mock_' + Date.now(),
      company_name: company_name,
      onboarding_completed: false,
      created_at: new Date().toISOString(),
    };

    const mockTokens = {
      access_token: 'mock_access_token_' + Date.now(),
      refresh_token: 'mock_refresh_token_' + Date.now(),
      token_type: 'bearer',
      expires_in: 3600,
    };

    return NextResponse.json({
      user: mockUser,
      tokens: mockTokens,
      is_new_user: true,
    });
  } catch {
    return NextResponse.json(
      { detail: 'Invalid request body' },
      { status: 400 }
    );
  }
}
