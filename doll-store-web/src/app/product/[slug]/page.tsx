import { notFound } from "next/navigation";
import Link from "next/link";
import { getProductBySlug } from "@/lib/data";
import { AddToCartButton } from "./AddToCartButton";
import { formatMoney } from "@/lib/money";
import { resolveRegionContext } from "@/lib/request-context";
import { ProductMediaGallery } from "@/components/ProductMediaGallery";
import { getLangFromSearchParams, t } from "@/lib/i18n";
import {
  localizeAddOnOption,
  localizeDescription,
  localizeMaterial,
  localizeProductName,
  localizeShippingNotice,
  localizeSpecValue,
} from "@/lib/product-copy";

const HIDDEN_SPEC_KEYS = new Set(["source_file"]);

const SPEC_LABELS: Record<string, { en: string; zh: string }> = {
  supplier: { en: "Supplier", zh: "供应商" },
  supplier_name: { en: "Supplier Name", zh: "供应商名称" },
  product_weight: { en: "Weight", zh: "重量" },
  vaginal_size_cm: { en: "Vaginal Size (cm)", zh: "阴道尺寸（CM）" },
  anal_size_cm: { en: "Anal Size (cm)", zh: "肛门尺寸（CM）" },
  product_size: { en: "Product Size", zh: "产品尺寸" },
  package_size_cm: { en: "Package Size (cm)", zh: "外包装尺寸（CM）" },
  feature: { en: "Product Features", zh: "产品特点" },
  supplier_code: { en: "Supplier Code", zh: "供应商编号" },
  supplier_stock: { en: "Supplier Stock", zh: "供应商库存" },
  gross_weight: { en: "Gross Weight", zh: "毛重" },
  package_stats: { en: "Package Stats", zh: "包装信息" },
  download_link: { en: "Download Link", zh: "下载链接" },
};

function formatSpecLabel(key: string, lang: "en" | "zh"): string {
  const dict = SPEC_LABELS[key];
  if (dict) return dict[lang];
  if (lang === "zh") return key;
  return key
    .split("_")
    .map((part) => (part ? part[0].toUpperCase() + part.slice(1) : part))
    .join(" ");
}

function formatSpecValue(key: string, value: string, lang: "en" | "zh"): string {
  const localized = localizeSpecValue(key, value, lang);
  if (lang === "en" && ["无", "暂无", "没有", "不支持", "空"].includes(value.trim())) {
    return "N/A";
  }
  return localized;
}

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
  const localizedName = localizeProductName(product.name, product.slug, lang);
  const displayPrice = product.salePrice ?? product.price;
  const displayCurrency = product.saleCurrency ?? product.currency ?? "CNY";
  const shippingText =
    (product.sourceType === "overseas_us" || product.sourceType === "overseas_eu") &&
    product.isFreeShippingOverseas
      ? t(lang, "Free shipping from overseas warehouse.", "海外仓包邮。")
      : t(lang, "Shipping quoted after destination confirmation.", "运费按收货地区确认后报价。");
  const backHref = `/products?lang=${lang}${ctx.debugRegion ? `&debug_region=${ctx.debugRegion}` : ""}${
    ctx.debugAll ? "&debug_all=1" : ""
  }`;
  const specEntries = Object.entries(product.specs ?? {}).filter(([key, value]) => {
    if (HIDDEN_SPEC_KEYS.has(key)) return false;
    if (value == null) return false;
    return String(value).trim().length > 0;
  });

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="grid gap-8 lg:grid-cols-2">
        <div className="space-y-4">
          <ProductMediaGallery
            name={localizedName}
            images={product.images.length > 0 ? product.images : ["https://placehold.co/600x800?text=Product"]}
            videoUrl={product.videoUrl}
            lang={lang}
          />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{localizedName}</h1>
          <p className="mt-1 text-xs text-gray-500">
            {t(lang, "Region view:", "地区视图:")} {ctx.region}
            {ctx.debugAll ? t(lang, " · debug_all enabled", " · 已开启debug_all") : ""}
          </p>
          <p className="mt-2 text-gray-500">
            {localizeMaterial(product.material, lang)} ·{" "}
            {product.sourceType === "origin" ? t(lang, "Origin supply", "产地供应") : t(lang, "Warehouse supply", "海外仓供应")}
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
              {product.shippingNotice ? localizeShippingNotice(product.shippingNotice, lang) : shippingText}
            </p>
          )}
          <div className="mt-3 rounded border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-700">
            <p>
              {t(
                lang,
                "See public packing and shipping evidence before ordering.",
                "下单前可先查看公开打包与发货实拍。"
              )}{" "}
              <Link href={`/shipping-proof?lang=${lang}`} className="underline">
                {t(lang, "Open shipping proof", "查看发货实拍")}
              </Link>
            </p>
          </div>
          <div className="mt-6">
            <AddToCartButton
              productId={product.id}
              slug={product.slug}
              name={localizedName}
              price={displayPrice}
              currency={displayCurrency}
              image={product.images[0]}
              lang={lang}
            />
          </div>
          <p className="mt-6 text-gray-600">{localizeDescription(product.description, lang)}</p>
          {product.addOnOptions && product.addOnOptions.length > 0 && (
            <div className="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-4">
              <h3 className="font-medium text-gray-900">
                {t(lang, "Optional functions (factory add-ons)", "可选功能（工厂增配）")}
              </h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-gray-600">
                {product.addOnOptions.map((opt) => (
                  <li key={opt}>{localizeAddOnOption(opt, lang)}</li>
                ))}
              </ul>
            </div>
          )}
          {specEntries.length > 0 && (
            <dl className="mt-6 border-t border-gray-200 pt-6">
              <dt className="font-medium text-gray-900">{t(lang, "Specifications", "规格参数")}</dt>
              <dd className="mt-2">
                <ul className="space-y-1 text-sm text-gray-600">
                  {specEntries.map(([key, value]) => (
                    <li key={key}>
                      <span className="font-medium">{formatSpecLabel(key, lang)}:</span>{" "}
                      {formatSpecValue(key, String(value), lang)}
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
