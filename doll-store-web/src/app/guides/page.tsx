import Link from "next/link";
import { getGuides } from "@/lib/guides";

export default function GuidesPage() {
  const guides = getGuides();

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">Buying Guides</h1>
      <p className="mt-2 text-sm text-gray-600">
        Content-first recommendations: materials, scenarios, care routines, and practical buying
        decisions.
      </p>
      <div className="mt-6 grid gap-6 md:grid-cols-2">
        {guides.map((guide) => (
          <article key={guide.id} className="rounded-lg border border-gray-200 bg-white p-5">
            <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
              {guide.category} · {guide.readMinutes} min read
            </p>
            <h2 className="mt-2 text-lg font-semibold text-gray-900">{guide.title}</h2>
            <p className="mt-2 text-sm text-gray-600">{guide.excerpt}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {guide.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded-full border border-gray-200 px-2 py-0.5 text-xs text-gray-600"
                >
                  #{tag}
                </span>
              ))}
            </div>
            <Link
              href={`/guides/${guide.slug}`}
              className="mt-4 inline-block text-sm font-medium text-gray-700 underline hover:text-gray-900"
            >
              Read guide →
            </Link>
          </article>
        ))}
      </div>
    </div>
  );
}

