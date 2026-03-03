import { notFound } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { getProductBySlug } from "@/lib/data";
import { AddToCartButton } from "./AddToCartButton";
import { formatMoney } from "@/lib/money";
import { resolveRegionContext } from "@/lib/request-context";

export default async function ProductPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { slug } = await params;
  const resolvedSearchParams = await searchParams;
  const ctx = await resolveRegionContext(resolvedSearchParams);
  const product = getProductBySlug(slug, { region: ctx.region, debugAll: ctx.debugAll });
  if (!product) notFound();
  const imageUrl = product.images[0] ?? "https://placehold.co/600x800?text=Product";
  const isPlaceholder = imageUrl.startsWith("https://placehold.co");
  const isProxyImage = imageUrl.startsWith("/api/image-proxy");

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-4">
          <div className="relative aspect-[3/4] overflow-hidden rounded-lg bg-gray-100">
            <Image
            src={imageUrl}
            alt={product.name}
            fill
            className="object-cover"
            sizes="(max-width: 1024px) 100vw, 50vw"
            priority
            unoptimized={isPlaceholder || isProxyImage}
          />
          </div>
          {/* 商品视频占位：videoUrl 填入自有或供应商授权视频 URL */}
          {product.videoUrl && (
            <div className="rounded-lg overflow-hidden bg-gray-900">
              <video
                src={product.videoUrl}
                controls
                className="w-full aspect-video object-contain"
                preload="metadata"
              >
                Your browser does not support the video tag.
              </video>
            </div>
          )}
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{product.name}</h1>
          <p className="mt-1 text-xs text-gray-500">
            Region view: {ctx.region}
            {ctx.debugAll ? " · debug_all enabled" : ""}
          </p>
          <p className="mt-2 text-gray-500">
            {product.material} · {product.sourceType === "origin" ? "Origin supply" : "Warehouse supply"}
          </p>
          <div className="mt-4 flex items-center gap-3">
            <span className="text-2xl font-semibold text-gray-900">
              {formatMoney(product.price, product.currency ?? "CNY")}
            </span>
            {product.compareAtPrice != null && product.compareAtPrice > product.price && (
              <span className="text-lg text-gray-400 line-through">
                {formatMoney(product.compareAtPrice, product.currency ?? "CNY")}
              </span>
            )}
          </div>
          {product.shippingNotice && (
            <p className="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              {product.shippingNotice}
            </p>
          )}
          <div className="mt-6">
            <AddToCartButton
              productId={product.id}
              slug={product.slug}
              name={product.name}
              price={product.price}
              currency={product.currency}
              image={product.images[0]}
            />
          </div>
          <p className="mt-6 text-gray-600">{product.description}</p>
          {product.addOnOptions && product.addOnOptions.length > 0 && (
            <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-4">
              <h3 className="font-medium text-gray-900">Optional functions (factory add-ons)</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-600">
                {product.addOnOptions.map((opt) => (
                  <li key={opt}>{opt}</li>
                ))}
              </ul>
            </div>
          )}
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
