import { getProducts } from "@/lib/data";
import { ProductCard } from "@/components/ProductCard";

export default function ProductsPage() {
  const products = getProducts();
  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">Origin Product Catalog</h1>
      <p className="mt-2 text-sm text-gray-600">
        Current prices are origin factory quotes (to freight forwarder). International shipping will
        be quoted by destination.
      </p>
      <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {products.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
    </div>
  );
}
