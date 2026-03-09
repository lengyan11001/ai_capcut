import Image from "next/image";
import { getShippingProofs } from "@/lib/shipping-proof";
import { getLangFromSearchParams, t } from "@/lib/i18n";

export default async function ShippingProofPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const lang = getLangFromSearchParams(await searchParams);
  const proofs = getShippingProofs();

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">
        {t(lang, "Shipping Proof Center", "发货实拍中心")}
      </h1>
      <p className="mt-2 text-sm text-gray-600">
        {t(
          lang,
          "Public shipping evidence from packing to courier handover for transparent fulfillment.",
          "公开展示从打包到交运的发货证据，帮助你清晰了解履约流程。"
        )}
      </p>
      <div className="mt-6 grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {proofs.map((proof) => (
          <article key={proof.id} className="overflow-hidden rounded-lg border border-gray-200 bg-white">
            <div className="relative h-52 w-full bg-gray-100">
              <Image src={proof.image} alt={proof.title} fill className="object-cover" unoptimized />
            </div>
            <div className="p-4">
              <h2 className="font-semibold text-gray-900">{proof.title}</h2>
              <p className="mt-2 text-sm text-gray-600">{proof.summary}</p>
              <p className="mt-2 text-xs text-gray-500">
                {proof.carrier ?? "-"} · {proof.route ?? "-"}
              </p>
              {proof.eventTime ? (
                <p className="mt-1 text-xs text-gray-500">{new Date(proof.eventTime).toLocaleString()}</p>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
