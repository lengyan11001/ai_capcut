import type { Category, Product } from "@/types";
import categoriesData from "@/data/categories.json";
import productsData from "@/data/products.json";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { unstable_cache } from "next/cache";

const categories = categoriesData as Category[];
const IMAGE_PROXY_PREFIX = "http://47.107.244.246:3000/uploads/";
const CORE_SUPPLIERS = (process.env.NEXT_PUBLIC_CORE_SUPPLIERS ?? "mxj")
  .split(",")
  .map((v) => v.trim().toLowerCase())
  .filter(Boolean);
/** Opt-in only. When unset/false, all suppliers show (your Supabase catalog). */
const ENABLE_CORE_SUPPLIER_FILTER = process.env.NEXT_PUBLIC_ENABLE_CORE_SUPPLIER_FILTER === "true";

/** Set to true to bypass optional supplier storefront filter. */
const SHOW_ALL_PUBLIC_CATALOG = process.env.NEXT_PUBLIC_SHOW_ALL_CATALOG === "true";

/**
 * Optional: limit storefront to specs.supplier in this list (e.g. mxj). Default: empty = no extra filter.
 * Set NEXT_PUBLIC_STOREFRONT_SUPPLIERS=mxj only when you explicitly want MXJ-only.
 */
const STOREFRONT_SUPPLIERS = (process.env.NEXT_PUBLIC_STOREFRONT_SUPPLIERS ?? "")
  .split(",")
  .map((v) => v.trim().toLowerCase())
  .filter(Boolean);

export function isStorefrontSupplierFilterEnabled(): boolean {
  if (SHOW_ALL_PUBLIC_CATALOG) return false;
  return STOREFRONT_SUPPLIERS.length > 0;
}

function passesStorefrontCatalogFilter(product: Product): boolean {
  if (SHOW_ALL_PUBLIC_CATALOG) return true;
  if (STOREFRONT_SUPPLIERS.length === 0) return true;
  const supplier = getSupplierKey(product);
  if (supplier !== "" && STOREFRONT_SUPPLIERS.includes(supplier)) return true;
  // Import slugs are mxj-* even if an old row missed specs.supplier
  const slug = product.slug.toLowerCase();
  if (supplier === "" && slug.startsWith("mxj-") && STOREFRONT_SUPPLIERS.includes("mxj")) {
    return true;
  }
  return false;
}

function normalizeImageUrl(url: string): string {
  if (url.startsWith(IMAGE_PROXY_PREFIX)) {
    return `/api/image-proxy?url=${encodeURIComponent(url)}`;
  }
  return url;
}

const staticProducts = (productsData as unknown as Product[]).map((product) => ({
  ...product,
  costPrice: product.costPrice ?? product.price,
  salePrice: product.salePrice ?? product.price,
  costCurrency: product.costCurrency ?? product.currency ?? "CNY",
  saleCurrency: product.saleCurrency ?? product.currency ?? "CNY",
  currency: product.saleCurrency ?? product.currency ?? "CNY",
  shippingQuoteMode: product.shippingQuoteMode ?? "quote_after_confirm",
  isFreeShippingOverseas: product.isFreeShippingOverseas ?? false,
  assetStatus: product.assetStatus ?? "published",
  images: (product.images ?? []).map(normalizeImageUrl),
}));

export type RegionCode = "US" | "EU" | "ROW";

export function getRegionFromCountry(countryCode?: string | null): RegionCode {
  if (!countryCode) return "ROW";
  const cc = countryCode.toUpperCase();
  if (cc === "US") return "US";
  const euCountries = new Set([
    "AT","BE","BG","CY","CZ","DE","DK","EE","ES","FI","FR","GR","HR","HU","IE","IT","LT",
    "LU","LV","MT","NL","PL","PT","RO","SE","SI","SK",
  ]);
  if (euCountries.has(cc)) return "EU";
  return "ROW";
}

export function getDebugRegion(input?: string | null): RegionCode | null {
  if (!input) return null;
  const normalized = input.toUpperCase();
  if (normalized === "US" || normalized === "EU" || normalized === "ROW") {
    return normalized;
  }
  return null;
}

function canShowByRegion(product: Product, region: RegionCode): boolean {
  if (product.visibleRegions && product.visibleRegions.length > 0) {
    return product.visibleRegions.includes("ALL") || product.visibleRegions.includes(region);
  }

  if (product.sourceType === "overseas_us") return region === "US";
  if (product.sourceType === "overseas_eu") return region === "EU";
  return true;
}

function getSupplierKey(product: Product): string {
  const raw = product.specs?.supplier;
  return typeof raw === "string" ? raw.toLowerCase() : "";
}

function canShowBySupplier(product: Product): boolean {
  if (!ENABLE_CORE_SUPPLIER_FILTER) return true;
  if (CORE_SUPPLIERS.length === 0) return true;
  const supplier = getSupplierKey(product);
  // Unset / legacy rows (no specs.supplier) must still show, or the catalog and hero go empty.
  if (supplier === "") return true;
  return CORE_SUPPLIERS.includes(supplier);
}

type DbProductRow = {
  id: string;
  slug: string;
  name: string;
  description: string;
  category_id: string;
  material: string;
  currency: "CNY" | "USD" | "EUR";
  cost_currency: "CNY" | "USD" | "EUR" | null;
  sale_currency: "CNY" | "USD" | "EUR" | null;
  cost_price: number;
  sale_price: number;
  compare_at_price: number | null;
  images: string[] | null;
  video_url: string | null;
  source_type: "origin" | "overseas_us" | "overseas_eu";
  shipping_quote_mode: "included" | "quote_after_confirm";
  is_free_shipping_overseas: boolean;
  asset_status: "raw" | "processed" | "published" | null;
  specs: Record<string, string> | null;
  add_on_options: string[] | null;
  visible_regions: Array<"US" | "EU" | "ROW" | "ALL"> | null;
  shippable_countries: string[] | null;
  featured: boolean;
};

function mapDbProduct(row: DbProductRow): Product {
  return {
    id: row.id,
    slug: row.slug,
    name: row.name,
    description: row.description ?? "",
    price: Number(row.sale_price ?? 0),
    costPrice: Number(row.cost_price ?? row.sale_price ?? 0),
    salePrice: Number(row.sale_price ?? 0),
    compareAtPrice: row.compare_at_price == null ? undefined : Number(row.compare_at_price),
    costCurrency: row.cost_currency ?? row.currency ?? "CNY",
    saleCurrency: row.sale_currency ?? row.currency ?? "CNY",
    currency: row.sale_currency ?? row.currency ?? "CNY",
    images: (row.images ?? []).map(normalizeImageUrl),
    videoUrl: row.video_url ?? undefined,
    categoryId: row.category_id,
    material: row.material ?? "",
    sourceType: row.source_type ?? "origin",
    shippingQuoteMode: row.shipping_quote_mode ?? "quote_after_confirm",
    isFreeShippingOverseas: row.is_free_shipping_overseas ?? false,
    assetStatus: row.asset_status ?? "published",
    specs: row.specs ?? {},
    addOnOptions: row.add_on_options ?? [],
    visibleRegions: row.visible_regions ?? ["ALL"],
    shippableCountries: row.shippable_countries ?? [],
    featured: row.featured ?? false,
  };
}

function isDeployedProductionBuild(): boolean {
  return process.env.VERCEL === "1" || process.env.NODE_ENV === "production";
}

async function loadProductsFromSource(): Promise<Product[]> {
  const supabase = getSupabaseAdmin();
  if (!supabase) {
    // On Vercel/production, missing env must NOT fall back to repo products.json (looks like fake inventory).
    if (isDeployedProductionBuild()) return [];
    return staticProducts;
  }

  const { data, error } = await supabase
    .from("products")
    .select("*")
    .order("updated_at", { ascending: false });
  // Do not fall back to bundled products.json: that looked like "random default data" on refresh
  // when the query failed or the table was briefly empty.
  if (error) return [];
  if (!data || data.length === 0) return [];
  return (data as DbProductRow[]).map(mapDbProduct);
}

// Bump key when load behavior changes (avoids stale ISR holding old JSON fallback).
const loadProductsCached = unstable_cache(loadProductsFromSource, ["products-all-v3"], {
  revalidate: 30,
});

export function getCategories(): Category[] {
  return categories;
}

export function getCategoryBySlug(slug: string): Category | undefined {
  return categories.find((c) => c.slug === slug);
}

export async function getProducts(
  categorySlug?: string,
  options?: { region?: RegionCode; debugAll?: boolean }
): Promise<Product[]> {
  const products = await loadProductsCached();
  const base = options?.debugAll
    ? products
    : products.filter((p) => canShowByRegion(p, options?.region ?? "ROW") && canShowBySupplier(p));
  const publishedOnly = base.filter((p) => (p.assetStatus ?? "published") === "published");
  const storefront = publishedOnly.filter(passesStorefrontCatalogFilter);

  if (!categorySlug) return storefront;
  const cat = categories.find((c) => c.slug === categorySlug);
  if (!cat) return storefront;
  return storefront.filter((p) => p.categoryId === cat.id);
}

export async function getProductBySlug(
  slug: string,
  options?: { region?: RegionCode; debugAll?: boolean }
): Promise<Product | undefined> {
  return (await getProducts(undefined, options)).find((p) => p.slug === slug);
}

export async function getFeaturedProducts(
  options?: { region?: RegionCode; debugAll?: boolean }
): Promise<Product[]> {
  return (await getProducts(undefined, options)).filter((p) => p.featured);
}
