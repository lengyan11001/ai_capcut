import { notFound } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { getGuideBySlug, getGuideProducts } from "@/lib/guides";
import { ProductCard } from "@/components/ProductCard";

export default async function GuideDetailPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const guide = getGuideBySlug(slug);
  if (!guide) notFound();

  const relatedProducts = await getGuideProducts(guide);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
        {guide.category} · {guide.readMinutes} min read
      </p>
      <h1 className="mt-2 text-3xl font-bold text-gray-900">{guide.title}</h1>
      <p className="mt-3 max-w-3xl text-gray-600">{guide.excerpt}</p>

      <div className="mt-4 flex flex-wrap gap-2">
        {guide.tags.map((tag) => (
          <span
            key={tag}
            className="rounded-full border border-gray-200 px-2 py-0.5 text-xs text-gray-600"
          >
            #{tag}
          </span>
        ))}
      </div>

      <article className="mt-8 space-y-10">
        {guide.sections.map((section) => (
          <section key={section.heading}>
            <h2 className="text-xl font-semibold text-gray-900">{section.heading}</h2>
            <p className="mt-2 leading-7 text-gray-700">{section.body}</p>
            {section.images && section.images.length > 0 && (
              <div
                className={`mt-5 grid gap-4 ${section.images.length > 1 ? "sm:grid-cols-2" : "max-w-2xl"}`}
              >
                {section.images.map((img) => (
                  <figure
                    key={img.src}
                    className="overflow-hidden rounded-xl border border-gray-200 bg-gray-50 shadow-sm"
                  >
                    <div className="relative aspect-[4/5] w-full bg-gray-100">
                      <Image
                        src={img.src}
                        alt={img.alt}
                        fill
                        className="object-cover object-center"
                        sizes="(max-width: 640px) 100vw, 50vw"
                        unoptimized
                      />
                    </div>
                    {img.caption && (
                      <figcaption className="border-t border-gray-100 px-3 py-2 text-center text-xs text-gray-600">
                        {img.caption}
                      </figcaption>
                    )}
                  </figure>
                ))}
              </div>
            )}
          </section>
        ))}
      </article>

      <section className="mt-10 border-t border-gray-200 pt-8">
        <h2 className="text-xl font-semibold text-gray-900">Recommended products</h2>
        <p className="mt-2 text-sm text-gray-600">
          Based on this guide, these models are good starting points.
        </p>
        <div className="mt-5 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {relatedProducts.map((product) => (
            <ProductCard key={product.id} product={product} />
          ))}
        </div>
      </section>

      <p className="mt-8">
        <Link href="/guides" className="text-gray-700 underline hover:text-gray-900">
          ← Back to all guides
        </Link>
      </p>
    </div>
  );
}

