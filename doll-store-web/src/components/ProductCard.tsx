import Link from "next/link";
import Image from "next/image";
import type { Product } from "@/types";
import { formatMoney } from "@/lib/money";

export function ProductCard({ product }: { product: Product }) {
  const imageUrl = product.images[0] ?? "https://placehold.co/600x800?text=Product";
  const isPlaceholder = imageUrl.startsWith("https://placehold.co");
  const isProxyImage = imageUrl.startsWith("/api/image-proxy");
  const displayPrice = product.salePrice ?? product.price;
  const displayCurrency = product.saleCurrency ?? product.currency ?? "CNY";
  const shippingText =
    (product.sourceType === "overseas_us" || product.sourceType === "overseas_eu") &&
    product.isFreeShippingOverseas
      ? "Free shipping from overseas warehouse."
      : "Shipping quoted after destination confirmation.";
  return (
    <Link
      href={`/product/${product.slug}`}
      className="group block overflow-hidden rounded-lg border border-gray-200 bg-white transition hover:border-gray-300 hover:shadow-md"
    >
      <div className="relative aspect-[3/4] bg-gray-100">
        <Image
          src={imageUrl}
          alt={product.name}
          fill
          className="object-cover transition group-hover:scale-[1.02]"
          sizes="(max-width: 768px) 100vw, 33vw"
          unoptimized={isPlaceholder || isProxyImage}
        />
        {product.compareAtPrice != null && product.compareAtPrice > product.price && (
          <span className="absolute left-2 top-2 rounded bg-red-600 px-2 py-0.5 text-xs text-white">
            Sale
          </span>
        )}
      </div>
      <div className="p-4">
        <h3 className="font-medium text-gray-900 group-hover:text-gray-700">
          {product.name}
        </h3>
        <p className="mt-1 text-sm text-gray-500">
          {product.material} · {product.sourceType === "origin" ? "Origin supply" : "Warehouse supply"}
        </p>
        <div className="mt-2 flex items-center gap-2">
          <span className="font-semibold text-gray-900">
            {formatMoney(displayPrice, displayCurrency)}
          </span>
          {product.compareAtPrice != null && product.compareAtPrice > displayPrice && (
            <span className="text-sm text-gray-400 line-through">
              {formatMoney(product.compareAtPrice, displayCurrency)}
            </span>
          )}
        </div>
        <p className="mt-1 text-xs text-gray-500">
          {shippingText}
        </p>
      </div>
    </Link>
  );
}
