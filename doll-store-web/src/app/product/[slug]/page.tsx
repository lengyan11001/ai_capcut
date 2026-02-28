import { notFound } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { getProductBySlug } from "@/lib/data";
import { AddToCartButton } from "./AddToCartButton";

export default async function ProductPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const product = getProductBySlug(slug);
  if (!product) notFound();
  const imageUrl = product.images[0] ?? "https://placehold.co/600x800?text=Product";

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="grid gap-8 lg:grid-cols-2">
        <div className="relative aspect-[3/4] overflow-hidden rounded-lg bg-gray-100">
          <Image
            src={imageUrl}
            alt={product.name}
            fill
            className="object-cover"
            sizes="(max-width: 1024px) 100vw, 50vw"
            priority
            unoptimized={imageUrl.startsWith("https://placehold.co")}
          />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{product.name}</h1>
          <p className="mt-2 text-gray-500">{product.material}</p>
          <div className="mt-4 flex items-center gap-3">
            <span className="text-2xl font-semibold text-gray-900">
              ${product.price.toLocaleString()}
            </span>
            {product.compareAtPrice != null && product.compareAtPrice > product.price && (
              <span className="text-lg text-gray-400 line-through">
                ${product.compareAtPrice.toLocaleString()}
              </span>
            )}
          </div>
          <div className="mt-6">
            <AddToCartButton
              productId={product.id}
              slug={product.slug}
              name={product.name}
              price={product.price}
              image={product.images[0]}
            />
          </div>
          <p className="mt-6 text-gray-600">{product.description}</p>
          {product.specs && Object.keys(product.specs).length > 0 && (
            <dl className="mt-6 border-t border-gray-200 pt-6">
              <dt className="font-medium text-gray-900">Specifications</dt>
              <dd className="mt-2">
                <ul className="space-y-1 text-sm text-gray-600">
                  {Object.entries(product.specs).map(([k, v]) => (
                    <li key={k}>
                      <span className="font-medium">{k}:</span> {v}
                    </li>
                  ))}
                </ul>
              </dd>
            </dl>
          )}
          <p className="mt-6">
            <Link href="/products" className="text-gray-600 underline hover:text-gray-900">
              ← Back to products
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
