import { NextResponse } from "next/server";

export async function GET() {
  // Health check endpoint for Docker / load balancer probes
  return NextResponse.json({
    status: "healthy",
    service: "parwa-frontend",
    timestamp: new Date().toISOString(),
    version: process.env.NEXT_PUBLIC_APP_VERSION || "0.1.0",
  });
}
