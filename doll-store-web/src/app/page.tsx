import Link from "next/link";
import Image from "next/image";
import { getCategories, getFeaturedProducts } from "@/lib/data";
import { ProductCard } from "@/components/ProductCard";
import { getGuides } from "@/lib/guides";
import { resolveRegionContext } from "@/lib/request-context";
import { getLangFromSearchParams, t } from "@/lib/i18n";

const HERO_IMAGE = "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=1200&q=80";

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolvedSearchParams = await searchParams;
  const lang = getLangFromSearchParams(resolvedSearchParams);
  const ctx = await resolveRegionContext(resolvedSearchParams);
  const categories = getCategories();
  const featured = await getFeaturedProducts({ region: ctx.region, debugAll: ctx.debugAll });
  const guides = getGuides().slice(0, 3);

  return (
    <div>
      {/* Hero：占位图来自 Unsplash，上线前请替换为自有或供应商授权素材 */}
      <section className="relative py-16 md:py-24">
        <div className="absolute inset-0 -z-10">
          <Image src={HERO_IMAGE} alt="" fill className="object-cover" priority sizes="100vw" />
          <div className="absolute inset-0 bg-black/40" />
        </div>
        <div className="mx-auto max-w-6xl px-4 text-center">
          <h1 className="text-3xl font-bold tracking-tight text-white drop-shadow md:text-4xl">
            {t(lang, "Premium Collectibles", "高端收藏级产品")}
          </h1>
          <p className="mt-4 text-lg text-white/90 drop-shadow">
            {t(
              lang,
              "Full body dolls and accessories. Discreet packaging, worldwide delivery.",
              "全身娃娃与配件，隐私包装，全球配送。"
            )}
          </p>
          <Link
            href="/guides"
            className="mt-6 inline-block rounded bg-white px-6 py-3 font-medium text-gray-900 hover:bg-gray-100"
          >
            {t(lang, "Start with Guides", "先看选购指南")}
          </Link>
          <p className="mt-3 text-xs text-white/80">{t(lang, "Current region view:", "当前地区视图:")} {ctx.region}</p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-gray-900">{t(lang, "Guides First", "内容先行")}</h2>
            <p className="mt-1 text-sm text-gray-600">
              {t(
                lang,
                "Learn materials, use scenarios, and maintenance before choosing products.",
                "先了解材质、使用场景和保养建议，再决定购买。"
              )}
            </p>
          </div>
          <Link href="/guides" className="text-sm text-gray-700 underline hover:text-gray-900">
            {t(lang, "View all guides", "查看全部指南")}
          </Link>
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {guides.map((guide) => (
            <Link
              key={guide.id}
              href={`/guides/${guide.slug}`}
              className="rounded-lg border border-gray-200 bg-white p-5 hover:border-gray-300 hover:shadow-sm"
            >
              <p className="text-xs uppercase tracking-wide text-gray-500">
                {guide.category} · {guide.readMinutes} min
              </p>
              <h3 className="mt-2 font-semibold text-gray-900">{guide.title}</h3>
              <p className="mt-2 text-sm text-gray-600">{guide.excerpt}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* Category cards */}
      <section className="mx-auto max-w-6xl px-4 py-12">
        <h2 className="text-xl font-semibold text-gray-900">{t(lang, "Shop by Category", "按品类选购")}</h2>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {categories.map((cat) => (
            <Link
              key={cat.id}
              href={`/category/${cat.slug}`}
              className="rounded-lg border border-gray-200 bg-white p-6 text-center transition hover:border-gray-300 hover:shadow"
            >
              <h3 className="font-medium text-gray-900">{cat.name}</h3>
              {cat.description && (
                <p className="mt-2 text-sm text-gray-500">{cat.description}</p>
              )}
            </Link>
          ))}
        </div>
      </section>

      {/* Featured products */}
      <section className="mx-auto max-w-6xl px-4 py-12">
        <h2 className="text-xl font-semibold text-gray-900">{t(lang, "Featured", "精选推荐")}</h2>
        <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {featured.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
        <div className="mt-8 text-center">
          <Link
            href="/products"
            className="text-gray-600 underline hover:text-gray-900"
          >
            {t(lang, "View all products", "查看全部商品")}
          </Link>
        </div>
      </section>

      {/* Trust bar */}
      <section className="border-t border-gray-200 bg-gray-50 py-10">
        <div className="mx-auto max-w-6xl px-4">
          <div className="grid gap-8 text-center sm:grid-cols-3">
            <div>
              <h3 className="font-semibold text-gray-900">{t(lang, "Discreet Packaging", "隐私包装")}</h3>
              <p className="mt-1 text-sm text-gray-600">
                {t(
                  lang,
                  "Plain packaging, no sensitive labels. Your privacy is our priority.",
                  "普通外箱，无敏感标签。你的隐私优先。"
                )}
              </p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">{t(lang, "Secure Checkout", "安全下单")}</h3>
              <p className="mt-1 text-sm text-gray-600">
                {t(
                  lang,
                  "We’ll contact you for secure payment after order confirmation.",
                  "订单确认后我们会联系你完成安全支付。"
                )}
              </p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">{t(lang, "Support", "客服支持")}</h3>
              <p className="mt-1 text-sm text-gray-600">
                {t(
                  lang,
                  "Questions? Contact us anytime. Returns policy available.",
                  "有疑问可随时联系，支持售后与退换说明。"
                )}
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
