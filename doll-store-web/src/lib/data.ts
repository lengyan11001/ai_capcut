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

export function getCategories(): Category[] {
  return categories;
}

export function getCategoryBySlug(slug: string): Category | undefined {
  return categories.find((c) => c.slug === slug);
}

export function getProducts(categorySlug?: string): Product[] {
  if (!categorySlug) return products;
  const cat = categories.find((c) => c.slug === categorySlug);
  if (!cat) return products;
  return products.filter((p) => p.categoryId === cat.id);
}

export function getProductBySlug(slug: string): Product | undefined {
  return products.find((p) => p.slug === slug);
}

export function getFeaturedProducts(): Product[] {
  return products.filter((p) => p.featured);
}
