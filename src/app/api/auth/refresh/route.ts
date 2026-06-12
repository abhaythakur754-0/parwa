import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL } from "@/lib/config";

export async function POST(request: NextRequest) {
  try {
    const refreshToken = request.cookies.get("parwa_rt")?.value;

    if (!refreshToken) {
      return NextResponse.json(
        { detail: "No refresh token" },
        { status: 401 }
      );
    }

    const res = await fetch(`${BACKEND_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    const data = await res.json();

    if (!res.ok) {
      return NextResponse.json(data, { status: res.status });
    }

    // Update httpOnly cookies
    const response = NextResponse.json(data);
    if (data.access_token) {
      response.cookies.set("parwa_at", data.access_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 60 * 60,
        path: "/",
      });
    }
    if (data.refresh_token) {
      response.cookies.set("parwa_rt", data.refresh_token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        maxAge: 60 * 60 * 24 * 7,
        path: "/",
      });
    }

    return response;
  } catch {
    return NextResponse.json(
      { detail: "Backend service unavailable" },
      { status: 503 }
    );
  }
}
