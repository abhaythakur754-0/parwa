import { NextResponse } from "next/server";

/**
 * Root /api/ — no longer exposes a public hello-world endpoint.
 * Returns 404 for unknown API root requests.
 */
export async function GET() {
  return NextResponse.json(
    { success: false, error: "Not found" },
    { status: 404 }
  );
}
