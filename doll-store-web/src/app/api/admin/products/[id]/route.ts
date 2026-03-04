import { NextRequest } from "next/server";
import { isAdminRequestAuthorized } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-admin";

type PartialAdminProductPayload = {
  slug?: string;
  name?: string;
  description?: string;
  categoryId?: string;
  material?: string;
  currency?: "CNY" | "USD" | "EUR";
  costPrice?: number;
  salePrice?: number;
  compareAtPrice?: number | null;
  sourceType?: "origin" | "overseas_us" | "overseas_eu";
  shippingQuoteMode?: "included" | "quote_after_confirm";
  isFreeShippingOverseas?: boolean;
  images?: string[];
  videoUrl?: string | null;
  specs?: Record<string, string>;
  addOnOptions?: string[];
  visibleRegions?: string[];
  shippableCountries?: string[];
  featured?: boolean;
};

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  if (!isAdminRequestAuthorized(request)) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
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
  const payload = body as PartialAdminProductPayload;

  const updateData = {
    ...(payload.slug !== undefined ? { slug: payload.slug } : {}),
    ...(payload.name !== undefined ? { name: payload.name } : {}),
    ...(payload.description !== undefined ? { description: payload.description } : {}),
    ...(payload.categoryId !== undefined ? { category_id: payload.categoryId } : {}),
    ...(payload.material !== undefined ? { material: payload.material } : {}),
    ...(payload.currency !== undefined ? { currency: payload.currency } : {}),
    ...(payload.costPrice !== undefined ? { cost_price: payload.costPrice } : {}),
    ...(payload.salePrice !== undefined ? { sale_price: payload.salePrice } : {}),
    ...(payload.compareAtPrice !== undefined ? { compare_at_price: payload.compareAtPrice } : {}),
    ...(payload.sourceType !== undefined ? { source_type: payload.sourceType } : {}),
    ...(payload.shippingQuoteMode !== undefined ? { shipping_quote_mode: payload.shippingQuoteMode } : {}),
    ...(payload.isFreeShippingOverseas !== undefined
      ? { is_free_shipping_overseas: payload.isFreeShippingOverseas }
      : {}),
    ...(payload.images !== undefined ? { images: payload.images } : {}),
    ...(payload.videoUrl !== undefined ? { video_url: payload.videoUrl } : {}),
    ...(payload.specs !== undefined ? { specs: payload.specs } : {}),
    ...(payload.addOnOptions !== undefined ? { add_on_options: payload.addOnOptions } : {}),
    ...(payload.visibleRegions !== undefined ? { visible_regions: payload.visibleRegions } : {}),
    ...(payload.shippableCountries !== undefined ? { shippable_countries: payload.shippableCountries } : {}),
    ...(payload.featured !== undefined ? { featured: payload.featured } : {}),
    updated_at: new Date().toISOString(),
  };

  const { error } = await supabase.from("products").update(updateData).eq("id", id);
  if (error) {
    return Response.json({ error: error.message }, { status: 500 });
  }
  return Response.json({ success: true });
}

