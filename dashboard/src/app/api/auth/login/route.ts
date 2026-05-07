import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { email, password } = body;

    if (!email || !password) {
      return NextResponse.json(
        { detail: 'Email and password are required' },
        { status: 400 }
      );
    }

    // Mock successful login
    const mockUser = {
      id: 'usr_mock_' + Date.now(),
      email: email,
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
      is_new_user: false,
    });
  } catch {
    return NextResponse.json(
      { detail: 'Invalid request body' },
      { status: 400 }
    );
  }
}
