import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const subPath = path.join("/");
  const url = `${BACKEND_URL}/api/v1/verification/${subPath}`;
  try {
    const res = await fetch(url, { headers: { ...Object.fromEntries(request.headers), host: new URL(BACKEND_URL).host } });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch { return NextResponse.json({ error: "Backend unavailable" }, { status: 503 }); }
}
