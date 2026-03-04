import { getProducts } from "@/lib/data";
import { ProductCard } from "@/components/ProductCard";
import { resolveRegionContext } from "@/lib/request-context";
import { getLangFromSearchParams, t } from "@/lib/i18n";

export default async function ProductsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolvedSearchParams = await searchParams;
  const lang = getLangFromSearchParams(resolvedSearchParams);
  const ctx = await resolveRegionContext(resolvedSearchParams);
  const query = new URLSearchParams();
  query.set("lang", lang);
  if (ctx.debugRegion) query.set("debug_region", ctx.debugRegion);
  if (ctx.debugAll) query.set("debug_all", "1");
  const queryString = query.toString();
  const products = await getProducts(undefined, { region: ctx.region, debugAll: ctx.debugAll });

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">
        {t(lang, "Product Catalog", "商品目录")}
      </h1>
      <p className="mt-2 text-sm text-gray-600">
        {t(
          lang,
          "Current prices are origin factory quotes (to freight forwarder). International shipping will be quoted by destination.",
          "当前价格为工厂到货代报价，国际运费将按目的地单独核算。"
        )}
      </p>
      <p className="mt-2 text-xs text-gray-500">
        {t(lang, "Region view:", "地区视图:")} {ctx.region}
        {ctx.debugRegion ? ` (debug_region=${ctx.debugRegion})` : ""}
        {ctx.debugAll ? t(lang, " · debug_all enabled", " · 已开启debug_all") : ""}
      </p>
      <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {products.map((product) => (
          <ProductCard key={product.id} product={product} lang={lang} queryString={queryString} />
        ))}
      </div>
    </div>
  );
}
