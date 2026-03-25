import Link from "next/link";
import Image from "next/image";
import { getFeaturedProducts } from "@/lib/data";
import { ProductCard } from "@/components/ProductCard";
import { getGuides } from "@/lib/guides";
import { resolveRegionContext } from "@/lib/request-context";
import { getLangFromSearchParams, t } from "@/lib/i18n";
import { getShippingProofs } from "@/lib/shipping-proof";

export default async function HomePage({
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
  const featured = await getFeaturedProducts({ region: ctx.region, debugAll: ctx.debugAll });
  const guides = getGuides().slice(0, 3);
  const featuredCards = featured.slice(0, 6);
  const featuredVisuals = featured
    .map((p) => p.images?.[0])
    .filter((url): url is string => Boolean(url));
  const fallbackHero =
    "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=1200&q=80";
  const heroImage = featuredVisuals[0] ?? fallbackHero;
  const secondaryHeroImage = featuredVisuals[1] ?? featuredVisuals[0] ?? fallbackHero;
  const proofs = getShippingProofs()
    .slice(0, 3)
    .map((proof, idx) => ({
      ...proof,
      image:
        proof.image.includes("placehold.co")
          ? featuredVisuals[idx % Math.max(featuredVisuals.length, 1)] ?? fallbackHero
          : proof.image,
    }));

  return (
    <div className="text-gray-100">
      <section className="relative overflow-hidden py-20 md:py-28">
        <div className="absolute inset-0 -z-10">
          <Image src={heroImage} alt="" fill className="object-cover" priority sizes="100vw" unoptimized />
          <div className="absolute inset-0 bg-black/60" />
        </div>
        <div className="mx-auto grid max-w-6xl gap-10 px-4 lg:grid-cols-[1.15fr_0.85fr] lg:items-center">
          <div>
            <p className="text-xs uppercase tracking-[0.22em] text-indigo-200/90">
              {t(lang, "Premium Visual Collection", "高质视觉精选")}
            </p>
            <h1 className="mt-4 text-3xl font-bold tracking-tight text-white drop-shadow md:text-5xl">
              {t(lang, "Premium Collectibles", "高端收藏级产品")}
            </h1>
            <p className="mt-4 max-w-2xl text-lg text-white/90 drop-shadow">
              {t(
                lang,
                "Curated visuals, discreet delivery, and transparent fulfillment updates for every order.",
                "以精选视觉、隐私交付和透明履约为核心，打造更安心的购买体验。"
              )}
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link
                href={`/products?${queryString}`}
                className="rounded-full bg-white px-7 py-3 font-medium text-gray-900 hover:bg-gray-100"
              >
                {t(lang, "Shop collection", "查看商品")}
              </Link>
              <Link
                href={`/guides?${queryString}`}
                className="rounded-full border border-white/50 bg-black/20 px-7 py-3 font-medium text-white hover:bg-black/35"
              >
                {t(lang, "Start with guides", "先看选购指南")}
              </Link>
            </div>
            <p className="mt-4 text-xs text-white/80">
              {t(lang, "Current region view:", "当前地区视图:")} {ctx.region}
            </p>
          </div>
          <div className="relative hidden lg:block">
            <div className="relative aspect-[4/5] overflow-hidden rounded-2xl border border-white/20 shadow-[0_20px_80px_rgba(0,0,0,0.45)]">
              <Image src={secondaryHeroImage} alt="" fill className="object-cover" unoptimized />
              <div className="absolute inset-0 bg-gradient-to-t from-black/50 via-transparent to-transparent" />
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12">
        <div className="rounded-2xl border border-white/10 bg-gradient-to-b from-[#171d31] to-[#111727] p-6 md:p-8">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-200/90">
            {t(lang, "Brand Story", "品牌故事")}
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-white">
            {t(
              lang,
              "Designed for trust, privacy, and transparent delivery.",
              "以信任、隐私与透明履约为核心打造。"
            )}
          </h2>
          <p className="mt-3 max-w-3xl text-sm text-gray-300">
            {t(
              lang,
              "We prioritize premium visual assets, discreet packaging, and visible fulfillment updates. Every featured product is curated to match our quality baseline before publication.",
              "我们优先使用高品质视觉素材、隐私包装与可视化发货进度。所有精选商品都经过质量基线审核后才公开展示。"
            )}
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-white">{t(lang, "Guides First", "内容先行")}</h2>
            <p className="mt-1 text-sm text-gray-300">
              {t(
                lang,
                "Learn materials, use scenarios, and maintenance before choosing products.",
                "先了解材质、使用场景和保养建议，再决定购买。"
              )}
            </p>
          </div>
          <Link href={`/guides?${queryString}`} className="text-sm text-indigo-200 underline hover:text-indigo-100">
            {t(lang, "View all guides", "查看全部指南")}
          </Link>
        </div>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          {guides.map((guide) => (
            <Link
              key={guide.id}
              href={`/guides/${guide.slug}?${queryString}`}
              className="rounded-lg border border-white/10 bg-[#12182a] p-5 hover:border-indigo-300/40 hover:shadow-[0_16px_45px_rgba(0,0,0,0.35)]"
            >
              <p className="text-xs uppercase tracking-wide text-gray-400">
                {guide.category} · {guide.readMinutes} min
              </p>
              <h3 className="mt-2 font-semibold text-gray-100">{guide.title}</h3>
              <p className="mt-2 text-sm text-gray-300">{guide.excerpt}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* Featured products */}
      <section className="mx-auto max-w-6xl px-4 py-12">
        <h2 className="text-xl font-semibold text-white">{t(lang, "Featured", "精选推荐")}</h2>
        <div className="mt-6 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {featuredCards.map((product) => (
            <ProductCard key={product.id} product={product} lang={lang} queryString={queryString} />
          ))}
        </div>
        <div className="mt-8 text-center">
          <Link
            href={`/products?${queryString}`}
            className="text-indigo-200 underline hover:text-indigo-100"
          >
            {t(lang, "View all products", "查看全部商品")}
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12">
        <div className="flex items-end justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold text-white">{t(lang, "Shipping Proof", "发货实拍")}</h2>
            <p className="mt-1 text-sm text-gray-300">
              {t(
                lang,
                "From warehouse packing to courier handover, review recent public fulfillment evidence.",
                "从仓库打包到交运节点，公开查看最新履约实拍证据。"
              )}
            </p>
          </div>
          <Link href={`/shipping-proof?${queryString}`} className="text-sm text-indigo-200 underline hover:text-indigo-100">
            {t(lang, "View all shipping proofs", "查看全部发货实拍")}
          </Link>
        </div>
        <div className="mt-6 grid gap-5 md:grid-cols-3">
          {proofs.map((proof) => (
            <article key={proof.id} className="overflow-hidden rounded-xl border border-white/10 bg-[#12182a]">
              <div className="relative h-44 w-full bg-[#0e1424]">
                <Image src={proof.image} alt={proof.title} fill className="object-cover" unoptimized />
              </div>
              <div className="p-4">
                <h3 className="font-medium text-gray-100">{proof.title}</h3>
                <p className="mt-1 text-xs text-gray-400">
                  {proof.carrier ?? "-"} · {proof.route ?? "-"}
                </p>
              </div>
            </article>
          ))}
        </div>
      </section>

      {/* Trust bar */}
      <section className="border-t border-white/10 bg-[#0a1020] py-10">
        <div className="mx-auto max-w-6xl px-4">
          <div className="grid gap-8 text-center sm:grid-cols-3">
            <div>
              <h3 className="font-semibold text-gray-100">{t(lang, "Discreet Packaging", "隐私包装")}</h3>
              <p className="mt-1 text-sm text-gray-400">
                {t(
                  lang,
                  "Plain packaging, no sensitive labels. Your privacy is our priority.",
                  "普通外箱，无敏感标签。你的隐私优先。"
                )}
              </p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-100">{t(lang, "Secure Checkout", "安全下单")}</h3>
              <p className="mt-1 text-sm text-gray-400">
                {t(
                  lang,
                  "We’ll contact you for secure payment after order confirmation.",
                  "订单确认后我们会联系你完成安全支付。"
                )}
              </p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-100">{t(lang, "Support", "客服支持")}</h3>
              <p className="mt-1 text-sm text-gray-400">
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
