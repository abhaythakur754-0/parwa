import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL } from "@/lib/config";

export async function GET(request: NextRequest) {
  try {
    const token = request.cookies.get("parwa_at")?.value;
    if (!token) {
      return NextResponse.json({ detail: "Not authenticated" }, { status: 401 });
    }

    const { searchParams } = new URL(request.url);
    const industry = searchParams.get("industry");
    const url = `${BACKEND_URL}/api/v1/integrations/catalog${industry ? `?industry=${industry}` : ""}`;

    const res = await fetch(url, {
      headers: { Authorization: `Bearer ${token}` },
    });

    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ detail: "Backend service unavailable" }, { status: 503 });
  }
}
