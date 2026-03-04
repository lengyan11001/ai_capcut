import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !serviceRoleKey) {
  console.error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
  process.exit(1);
}

const filePath = resolve(process.cwd(), "src/data/products.json");
const raw = await readFile(filePath, "utf-8");
const products = JSON.parse(raw);

const supabase = createClient(supabaseUrl, serviceRoleKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const rows = products.map((p) => ({
  slug: p.slug,
  name: p.name,
  description: p.description ?? "",
  category_id: p.categoryId ?? "silicone",
  material: p.material ?? "",
  currency: p.currency ?? "CNY",
  cost_currency: p.costCurrency ?? p.currency ?? "CNY",
  sale_currency: p.saleCurrency ?? p.currency ?? "CNY",
  cost_price: p.costPrice ?? p.price ?? 0,
  sale_price: p.salePrice ?? p.price ?? 0,
  compare_at_price: p.compareAtPrice ?? null,
  source_type: p.sourceType ?? "origin",
  shipping_quote_mode: p.shippingQuoteMode ?? "quote_after_confirm",
  is_free_shipping_overseas: p.isFreeShippingOverseas ?? false,
  images: Array.isArray(p.images) ? p.images : [],
  video_url: p.videoUrl ?? null,
  specs: p.specs ?? {},
  add_on_options: Array.isArray(p.addOnOptions) ? p.addOnOptions : [],
  visible_regions: Array.isArray(p.visibleRegions) ? p.visibleRegions : ["ALL"],
  shippable_countries: Array.isArray(p.shippableCountries) ? p.shippableCountries : [],
  featured: Boolean(p.featured),
  asset_status: p.assetStatus ?? "published",
}));

const { error } = await supabase.from("products").upsert(rows, { onConflict: "slug" });
if (error) {
  console.error("Import failed:", error.message);
  process.exit(1);
}

console.log(`Imported ${rows.length} products. cost_price initialized and sale_price ready for admin edits.`);

