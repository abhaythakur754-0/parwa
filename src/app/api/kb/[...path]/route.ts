import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://127.0.0.1:8000";

export async function GET(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const subPath = path.join("/");
  const searchParams = request.nextUrl.searchParams.toString();
  const url = `${BACKEND_URL}/api/v1/kb/${subPath}${searchParams ? `?${searchParams}` : ""}`;
  try {
    const res = await fetch(url, { headers: { ...Object.fromEntries(request.headers), host: new URL(BACKEND_URL).host } });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch { return NextResponse.json({ error: "Backend unavailable" }, { status: 503 }); }
}

export async function POST(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const subPath = path.join("/");
  const url = `${BACKEND_URL}/api/v1/kb/${subPath}`;
  try {
    const contentType = request.headers.get("content-type") || "";
    if (contentType.includes("multipart/form-data")) {
      const formData = await request.formData();
      const res = await fetch(url, { method: "POST", body: formData });
      const data = await res.json();
      return NextResponse.json(data, { status: res.status });
    }
    const body = await request.json();
    const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", ...Object.fromEntries(request.headers), host: new URL(BACKEND_URL).host }, body: JSON.stringify(body) });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch { return NextResponse.json({ error: "Backend unavailable" }, { status: 503 }); }
}

export async function DELETE(request: NextRequest, { params }: { params: Promise<{ path: string[] }> }) {
  const { path } = await params;
  const subPath = path.join("/");
  const url = `${BACKEND_URL}/api/v1/kb/${subPath}`;
  try {
    const res = await fetch(url, { method: "DELETE", headers: { ...Object.fromEntries(request.headers), host: new URL(BACKEND_URL).host } });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch { return NextResponse.json({ error: "Backend unavailable" }, { status: 503 }); }
}
