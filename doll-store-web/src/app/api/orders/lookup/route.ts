import { NextRequest } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { normalizeOrderItems } from "@/lib/order-items";

function getSupabase() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) return null;
  return createClient(url, key);
}

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { email, orderId } = body as { email?: string; orderId?: string };
  if (!email) {
    return Response.json({ error: "Email is required" }, { status: 400 });
  }

  const supabase = getSupabase();
  if (!supabase) {
    return Response.json({ error: "Supabase is not configured" }, { status: 500 });
  }

  let query = supabase
    .from("orders")
    .select("id, total, currency, status, created_at, items")
    .eq("email", email)
    .order("created_at", { ascending: false })
    .limit(20);

  if (orderId) {
    query = query.eq("id", orderId);
  }

  const { data, error } = await query;
  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }

  const orders = (data ?? []).map((row) => {
    const orderItems = normalizeOrderItems(row.items);
    return {
      id: row.id,
      total: row.total,
      currency: row.currency,
      status: row.status,
      createdAt: row.created_at,
      paymentMethod: orderItems.paymentMethod,
      trackingNumber: orderItems.fulfillment?.trackingNumber ?? null,
      trackingUrl: orderItems.fulfillment?.trackingUrl ?? null,
      shippingCarrier: orderItems.fulfillment?.carrier ?? null,
      proofImages: orderItems.fulfillment?.proofImages ?? [],
      proofVideos: orderItems.fulfillment?.proofVideos ?? [],
      shippedAt: orderItems.fulfillment?.shippedAt ?? null,
      deliveredAt: orderItems.fulfillment?.deliveredAt ?? null,
    };
  });

  return Response.json({ success: true, orders });
}
