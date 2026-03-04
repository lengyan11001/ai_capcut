import { NextRequest } from "next/server";
import { isAdminRequestAuthorized } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-admin";

export async function GET(request: NextRequest) {
  if (!isAdminRequestAuthorized(request)) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = getSupabaseAdmin();
  if (!supabase) {
    return Response.json({ error: "Supabase is not configured" }, { status: 500 });
  }

  const url = new URL(request.url);
  const status = url.searchParams.get("status");
  const limitRaw = Number(url.searchParams.get("limit") ?? 200);
  const limit = Number.isFinite(limitRaw) ? Math.min(Math.max(limitRaw, 1), 500) : 200;

  let query = supabase
    .from("orders")
    .select("id, email, shipping_name, total, currency, status, created_at, items")
    .order("created_at", { ascending: false })
    .limit(limit);

  if (status) {
    query = query.eq("status", status);
  }

  const { data, error } = await query;
  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
  return Response.json({ success: true, orders: data ?? [] });
}
