import { notFound } from "next/navigation";
import { getCategoryBySlug, getProducts } from "@/lib/data";
import { ProductCard } from "@/components/ProductCard";
import { resolveRegionContext } from "@/lib/request-context";

export default async function CategoryPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { slug } = await params;
  const resolvedSearchParams = await searchParams;
  const ctx = await resolveRegionContext(resolvedSearchParams);
  const category = getCategoryBySlug(slug);
  if (!category) notFound();
  const products = getProducts(slug, { region: ctx.region, debugAll: ctx.debugAll });
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">{category.name}</h1>
      {category.description && (
        <p className="mt-2 text-gray-600">{category.description}</p>
      )}
      <p className="mt-2 text-xs text-gray-500">
        Region view: {ctx.region}
        {ctx.debugRegion ? ` (debug_region=${ctx.debugRegion})` : ""}
        {ctx.debugAll ? " · debug_all enabled" : ""}
      </p>
      <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {products.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
      {products.length === 0 && (
        <p className="mt-8 text-gray-500">No products in this category yet.</p>
      )}
    </div>
  );
}
