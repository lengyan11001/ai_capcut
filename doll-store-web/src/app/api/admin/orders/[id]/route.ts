import { NextRequest } from "next/server";
import { isAdminRequestAuthorized } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { normalizeOrderItems } from "@/lib/order-items";

type AdminOrderPatchPayload = {
  status?: string;
  shippingCarrier?: string;
  trackingNumber?: string;
  trackingUrl?: string;
  adminNote?: string;
  payTxHash?: string;
  paidAmount?: number;
  markPaid?: boolean;
  markShipped?: boolean;
  markDelivered?: boolean;
};

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!isAdminRequestAuthorized(request)) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }
  const supabase = getSupabaseAdmin();
  if (!supabase) {
    return Response.json({ error: "Supabase is not configured" }, { status: 500 });
  }
  const { id } = await params;
  const { data, error } = await supabase
    .from("orders")
    .select("id, email, shipping_name, shipping_address, shipping_phone, total, currency, status, created_at, items")
    .eq("id", id)
    .single();

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
  return Response.json({ success: true, order: data });
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!isAdminRequestAuthorized(request)) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }
  const supabase = getSupabaseAdmin();
  if (!supabase) {
    return Response.json({ error: "Supabase is not configured" }, { status: 500 });
  }
  const { id } = await params;

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }
  const payload = body as AdminOrderPatchPayload;

  const { data: existing, error: fetchError } = await supabase
    .from("orders")
    .select("status, items")
    .eq("id", id)
    .single();
  if (fetchError) {
    return Response.json({ error: fetchError.message }, { status: 500 });
  }

  const currentItems = normalizeOrderItems(existing?.items);
  const now = new Date().toISOString();

  const nextItems = {
    ...currentItems,
    fulfillment: {
      ...currentItems.fulfillment,
      ...(payload.shippingCarrier !== undefined ? { carrier: payload.shippingCarrier } : {}),
      ...(payload.trackingNumber !== undefined ? { trackingNumber: payload.trackingNumber } : {}),
      ...(payload.trackingUrl !== undefined ? { trackingUrl: payload.trackingUrl } : {}),
      ...(payload.markShipped ? { shippedAt: now } : {}),
      ...(payload.markDelivered ? { deliveredAt: now } : {}),
    },
    payment: {
      ...currentItems.payment,
      ...(payload.payTxHash !== undefined ? { txHash: payload.payTxHash } : {}),
      ...(payload.paidAmount !== undefined ? { paidAmount: payload.paidAmount } : {}),
      ...(payload.markPaid ? { paidAt: now } : {}),
    },
    notes: {
      ...currentItems.notes,
      ...(payload.adminNote !== undefined ? { admin: payload.adminNote } : {}),
    },
  };

  const nextStatus =
    payload.status ??
    (payload.markDelivered
      ? "delivered"
      : payload.markShipped
        ? "shipped"
        : payload.markPaid
          ? "paid"
          : existing?.status ?? "pending");

  const { error } = await supabase
    .from("orders")
    .update({
      status: nextStatus,
      items: nextItems,
    })
    .eq("id", id);

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
  return Response.json({ success: true });
}
