import type { Category, Product } from "@/types";
import categoriesData from "@/data/categories.json";
import productsData from "@/data/products.json";

const categories = categoriesData as Category[];
const products = productsData as unknown as Product[];

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
