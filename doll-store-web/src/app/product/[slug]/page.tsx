import { notFound } from "next/navigation";
import Link from "next/link";
import { getProductBySlug } from "@/lib/data";
import { AddToCartButton } from "./AddToCartButton";
import { formatMoney } from "@/lib/money";
import { resolveRegionContext } from "@/lib/request-context";
import { ProductMediaGallery } from "@/components/ProductMediaGallery";
import { getLangFromSearchParams, t } from "@/lib/i18n";

export default async function ProductPage({
  params,
  searchParams,
}: {
  params: Promise<{ slug: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { slug } = await params;
  const resolvedSearchParams = await searchParams;
  const lang = getLangFromSearchParams(resolvedSearchParams);
  const ctx = await resolveRegionContext(resolvedSearchParams);
  const product = await getProductBySlug(slug, { region: ctx.region, debugAll: ctx.debugAll });
  if (!product) notFound();
  const displayPrice = product.salePrice ?? product.price;
  const displayCurrency = product.saleCurrency ?? product.currency ?? "CNY";
  const shippingText =
    (product.sourceType === "overseas_us" || product.sourceType === "overseas_eu") &&
    product.isFreeShippingOverseas
      ? "Free shipping from overseas warehouse."
      : "Shipping quoted after destination confirmation.";
  const backHref = `/products?lang=${lang}${ctx.debugRegion ? `&debug_region=${ctx.debugRegion}` : ""}${
    ctx.debugAll ? "&debug_all=1" : ""
  }`;

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-4">
          <ProductMediaGallery
            name={product.name}
            images={product.images.length > 0 ? product.images : ["https://placehold.co/600x800?text=Product"]}
            videoUrl={product.videoUrl}
          />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{product.name}</h1>
          <p className="mt-1 text-xs text-gray-500">
            {t(lang, "Region view:", "地区视图:")} {ctx.region}
            {ctx.debugAll ? " · debug_all enabled" : ""}
          </p>
          <p className="mt-2 text-gray-500">
            {product.material} · {product.sourceType === "origin" ? "Origin supply" : "Warehouse supply"}
          </p>
          <div className="mt-4 flex items-center gap-3">
            <span className="text-2xl font-semibold text-gray-900">
              {formatMoney(displayPrice, displayCurrency)}
            </span>
            {product.compareAtPrice != null && product.compareAtPrice > displayPrice && (
              <span className="text-lg text-gray-400 line-through">
                {formatMoney(product.compareAtPrice, displayCurrency)}
              </span>
            )}
          </div>
          {(product.shippingNotice || product.shippingQuoteMode || product.isFreeShippingOverseas) && (
            <p className="mt-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
              {product.shippingNotice ?? shippingText}
            </p>
          )}
          <div className="mt-6">
            <AddToCartButton
              productId={product.id}
              slug={product.slug}
              name={product.name}
              price={displayPrice}
              currency={displayCurrency}
              image={product.images[0]}
            />
          </div>
          <p className="mt-6 text-gray-600">{product.description}</p>
          {product.addOnOptions && product.addOnOptions.length > 0 && (
            <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-4">
              <h3 className="font-medium text-gray-900">
                {t(lang, "Optional functions (factory add-ons)", "可选功能（工厂增配）")}
              </h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-600">
                {product.addOnOptions.map((opt) => (
                  <li key={opt}>{opt}</li>
                ))}
              </ul>
            </div>
          )}
          {product.specs && Object.keys(product.specs).length > 0 && (
            <dl className="mt-6 border-t border-gray-200 pt-6">
              <dt className="font-medium text-gray-900">{t(lang, "Specifications", "规格参数")}</dt>
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
            <Link href={backHref} className="text-gray-600 underline hover:text-gray-900">
              {t(lang, "← Back to products", "← 返回商品列表")}
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
