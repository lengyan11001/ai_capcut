import type { Category, Product } from "@/types";
import categoriesData from "@/data/categories.json";
import productsData from "@/data/products.json";

const categories = categoriesData as Category[];
const IMAGE_PROXY_PREFIX = "http://47.107.244.246:3000/uploads/";

function normalizeImageUrl(url: string): string {
  if (url.startsWith(IMAGE_PROXY_PREFIX)) {
    return `/api/image-proxy?url=${encodeURIComponent(url)}`;
  }
  return url;
}

const products = (productsData as unknown as Product[]).map((product) => ({
  ...product,
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

export function getCategories(): Category[] {
  return categories;
}

export function getCategoryBySlug(slug: string): Category | undefined {
  return categories.find((c) => c.slug === slug);
}

export function getProducts(
  categorySlug?: string,
  options?: { region?: RegionCode; debugAll?: boolean }
): Product[] {
  const base = options?.debugAll
    ? products
    : products.filter((p) => canShowByRegion(p, options?.region ?? "ROW"));

  if (!categorySlug) return base;
  const cat = categories.find((c) => c.slug === categorySlug);
  if (!cat) return base;
  return base.filter((p) => p.categoryId === cat.id);
}

export function getProductBySlug(
  slug: string,
  options?: { region?: RegionCode; debugAll?: boolean }
): Product | undefined {
  return getProducts(undefined, options).find((p) => p.slug === slug);
}

export function getFeaturedProducts(options?: { region?: RegionCode; debugAll?: boolean }): Product[] {
  return getProducts(undefined, options).filter((p) => p.featured);
}
