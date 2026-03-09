import Image from "next/image";
import { getShippingProofs } from "@/lib/shipping-proof";
import { getLangFromSearchParams, t } from "@/lib/i18n";
import { resolveRegionContext } from "@/lib/request-context";
import { getProducts } from "@/lib/data";

export default async function ShippingProofPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const resolvedSearchParams = await searchParams;
  const lang = getLangFromSearchParams(resolvedSearchParams);
  const ctx = await resolveRegionContext(resolvedSearchParams);
  const products = await getProducts(undefined, { region: ctx.region, debugAll: ctx.debugAll });
  const fallbackImage =
    products.map((p) => p.images?.[0]).filter((v): v is string => Boolean(v))[0] ??
    "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=1200&q=80";
  const proofs = getShippingProofs().map((proof) => ({
    ...proof,
    image: proof.image.includes("placehold.co") ? fallbackImage : proof.image,
  }));

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 text-gray-100">
      <h1 className="text-2xl font-bold text-white">
        {t(lang, "Shipping Proof Center", "发货实拍中心")}
      </h1>
      <p className="mt-2 text-sm text-gray-300">
        {t(
          lang,
          "Public shipping evidence from packing to courier handover for transparent fulfillment.",
          "公开展示从打包到交运的发货证据，帮助你清晰了解履约流程。"
        )}
      </p>
      <div className="mt-6 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {proofs.map((proof) => (
          <article key={proof.id} className="overflow-hidden rounded-xl border border-white/10 bg-[#12182a]">
            <div className="relative h-52 w-full bg-[#0e1424]">
              <Image src={proof.image} alt={proof.title} fill className="object-cover" unoptimized />
            </div>
            <div className="p-4">
              <h2 className="font-semibold text-gray-100">{proof.title}</h2>
              <p className="mt-2 text-sm text-gray-300">{proof.summary}</p>
              <p className="mt-2 text-xs text-gray-400">
                {proof.carrier ?? "-"} · {proof.route ?? "-"}
              </p>
              {proof.eventTime ? (
                <p className="mt-1 text-xs text-gray-400">{new Date(proof.eventTime).toLocaleString()}</p>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
