import { NextRequest } from "next/server";
import { isAdminRequestAuthorized } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-admin";

type AdminProductPayload = {
  slug: string;
  name: string;
  description: string;
  categoryId: string;
  material: string;
  currency?: "CNY" | "USD" | "EUR";
  costCurrency?: "CNY" | "USD" | "EUR";
  saleCurrency?: "CNY" | "USD" | "EUR";
  costPrice: number;
  salePrice: number;
  compareAtPrice?: number | null;
  sourceType?: "origin" | "overseas_us" | "overseas_eu";
  shippingQuoteMode?: "included" | "quote_after_confirm";
  isFreeShippingOverseas?: boolean;
  images: string[];
  videoUrl?: string | null;
  specs?: Record<string, string>;
  addOnOptions?: string[];
  visibleRegions?: string[];
  shippableCountries?: string[];
  featured?: boolean;
  assetStatus?: "raw" | "processed" | "published";
};

export async function POST(request: NextRequest) {
  if (!isAdminRequestAuthorized(request)) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = getSupabaseAdmin();
  if (!supabase) {
    return Response.json({ error: "Supabase is not configured" }, { status: 500 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const payload = body as AdminProductPayload;
  if (!payload.slug || !payload.name || !payload.categoryId) {
    return Response.json({ error: "Missing required fields: slug, name, categoryId" }, { status: 400 });
  }
  if (!Number.isFinite(payload.costPrice) || !Number.isFinite(payload.salePrice)) {
    return Response.json({ error: "costPrice and salePrice must be numbers" }, { status: 400 });
  }

  const { data, error } = await supabase
    .from("products")
    .insert({
      slug: payload.slug,
      name: payload.name,
      description: payload.description ?? "",
      category_id: payload.categoryId,
      material: payload.material ?? "",
      currency: payload.currency ?? "CNY",
      cost_currency: payload.costCurrency ?? payload.currency ?? "CNY",
      sale_currency: payload.saleCurrency ?? payload.currency ?? "CNY",
      cost_price: payload.costPrice,
      sale_price: payload.salePrice,
      compare_at_price: payload.compareAtPrice ?? null,
      source_type: payload.sourceType ?? "origin",
      shipping_quote_mode: payload.shippingQuoteMode ?? "quote_after_confirm",
      is_free_shipping_overseas: payload.isFreeShippingOverseas ?? false,
      images: payload.images ?? [],
      video_url: payload.videoUrl ?? null,
      specs: payload.specs ?? {},
      add_on_options: payload.addOnOptions ?? [],
      visible_regions: payload.visibleRegions ?? ["ALL"],
      shippable_countries: payload.shippableCountries ?? [],
      featured: payload.featured ?? false,
      asset_status: payload.assetStatus ?? "published",
    })
    .select("id")
    .single();

  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
  return Response.json({ success: true, id: data?.id });
}

