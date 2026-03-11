import { NextRequest } from "next/server";
import { capturePaypalOrder } from "@/lib/paypal";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { paypalOrderId } = body as { paypalOrderId?: string };
  if (!paypalOrderId) {
    return Response.json({ error: "paypalOrderId is required" }, { status: 400 });
  }

  try {
    const captured = await capturePaypalOrder(paypalOrderId);
    return Response.json({ success: true, ...captured });
  } catch (error) {
    return Response.json(
      { error: error instanceof Error ? error.message : "PayPal capture failed" },
      { status: 500 }
    );
  }
}
