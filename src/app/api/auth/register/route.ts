import { NextRequest, NextResponse } from "next/server";
import { proxyAuthRequest, transformRegisterBody, transformAuthResponse } from "@/lib/backend-proxy";

/**
 * POST /api/auth/register
 * Proxies to backend: POST /api/auth/register
 *
 * Frontend sends: { email, password, fullName, companyName, industry }
 * Backend expects: { email, password, confirm_password, full_name, company_name, industry }
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    return proxyAuthRequest(request, {
      backendPath: "/api/auth/register",
      method: "POST",
      body,
      transformBody: transformRegisterBody,
      transformResponse: transformAuthResponse,
      setCookies: true,
    });
  } catch (error: unknown) {
    const message =
      error instanceof Error ? error.message : "An unexpected error occurred";
    console.error("Register error:", message);
    return NextResponse.json(
      { status: "error", message: "An unexpected error occurred. Please try again." },
      { status: 500 }
    );
  }
}
