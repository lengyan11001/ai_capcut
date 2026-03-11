import { NextRequest } from "next/server";
import { createPaypalOrder } from "@/lib/paypal";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { amount, currency } = body as {
    amount?: number;
    currency?: "USD" | "EUR" | "CNY";
  };
  if (typeof amount !== "number" || amount <= 0) {
    return Response.json({ error: "Invalid amount" }, { status: 400 });
  }
  const resolvedCurrency = currency ?? "USD";
  if (!["USD", "EUR", "CNY"].includes(resolvedCurrency)) {
    return Response.json({ error: "Unsupported currency" }, { status: 400 });
  }

  try {
    const order = await createPaypalOrder({
      amount,
      currency: resolvedCurrency,
    });
    return Response.json({ success: true, paypalOrderId: order.id });
  } catch (error) {
    return Response.json(
      { error: error instanceof Error ? error.message : "PayPal create order failed" },
      { status: 500 }
    );
  }
}
