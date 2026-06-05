import { NextRequest, NextResponse } from "next/server";

/**
 * POST /api/shopify/refund-initiate
 *
 * Proxy for the Refund Initiate Tool.
 * Forwards refund requests to the backend PARWA API which handles:
 *   1. Shopify refund creation (marks order items as refunded)
 *   2. Paddle adjustment (processes the actual money back)
 *   3. ClientRefundService tracking (audit trail)
 *
 * Input:  order_id + items + amount
 * Output: refund object (ties into Paddle for payment processing)
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Validate required fields
    if (!body.order_id) {
      return NextResponse.json(
        { error: "order_id is required" },
        { status: 400 }
      );
    }

    if (!body.company_id) {
      return NextResponse.json(
        { error: "company_id is required" },
        { status: 400 }
      );
    }

    // Forward to backend API
    const backendUrl = process.env.BACKEND_URL || "http://localhost:5100";

    const response = await fetch(`${backendUrl}/api/shopify/refunds`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(request.headers.get("cookie") && {
          cookie: request.headers.get("cookie") || "",
        }),
      },
      body: JSON.stringify({
        order_id: body.order_id,
        items: body.items || [],
        amount: body.amount || null,
        reason: body.reason || "",
        notify_customer: body.notify_customer !== false,
        process_payment: body.process_payment !== false,
      }),
    });

    const data = await response.json();

    if (!response.ok) {
      return NextResponse.json(
        { error: data.error || data.detail || "Refund initiation failed" },
        { status: response.status }
      );
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error("[refund-initiate] Error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
