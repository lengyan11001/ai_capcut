import { NextRequest } from "next/server";
import { createClient } from "@supabase/supabase-js";
import type { OrderPayload } from "@/types";
import { isCountrySupported } from "@/lib/shipping";

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

  const { email, shipping, items, total, currency, paymentMethod } = body as OrderPayload;
  const resolvedPaymentMethod = paymentMethod === "crypto_manual" ? "crypto_manual" : "manual_contact";
  if (!email || !shipping?.name || !shipping?.address || !Array.isArray(items) || typeof total !== "number") {
    return Response.json(
      { error: "Missing required fields: email, shipping (name, address), items, total" },
      { status: 400 }
    );
  }
  if (!shipping?.country || !isCountrySupported(shipping.country)) {
    return Response.json(
      { error: "Destination country is not supported yet. Please contact support for manual quote." },
      { status: 400 }
    );
  }

  const supabase = getSupabase();
  if (supabase) {
    const orderItems = {
      lines: items,
      paymentMethod: resolvedPaymentMethod,
    };
    const { data, error } = await supabase
      .from("orders")
      .insert({
        email,
        shipping_name: shipping.name,
        shipping_address: [
          shipping.address,
          shipping.city,
          shipping.state,
          shipping.postalCode,
          shipping.country,
        ].filter(Boolean).join(", "),
        shipping_phone: shipping.phone ?? null,
        items: orderItems,
        total,
        currency: currency ?? "CNY",
        status: resolvedPaymentMethod === "crypto_manual" ? "pending_crypto" : "pending",
      })
      .select("id")
      .single();

    if (error) {
      console.error("Supabase insert error:", error);
      return Response.json(
        { error: "Failed to save order. Ensure Supabase table exists." },
        { status: 500 }
      );
    }
    return Response.json({ success: true, orderId: data?.id, paymentMethod: resolvedPaymentMethod });
  }

  // Fallback: no Supabase configured — return success with a placeholder ID so the flow still works.
  // In production you could send an email here (Resend/SendGrid) and then return success.
  console.warn("Orders API: No Supabase configured. Order not persisted.", {
    email,
    total,
    itemCount: items.length,
    paymentMethod: resolvedPaymentMethod,
  });
  return Response.json({
    success: true,
    orderId: `draft-${Date.now()}`,
    paymentMethod: resolvedPaymentMethod,
  });
}
