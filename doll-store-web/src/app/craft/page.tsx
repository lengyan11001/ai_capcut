import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Craft & bespoke guide | RealDollHub",
  description:
    "How Chinese workshop craft, molding, coloring, and optional smart features come together on curated silicone dolls—feature sets vary by SKU.",
};

const foundation = [
  {
    src: "/craft/b38.jpg",
    alt: "Precision molding and prototype work in the workshop",
    title: "Precision molding",
    body: "Forms start from disciplined sculpts and molds so proportions stay coherent at full scale—not stretched or flattened at the last minute.",
  },
  {
    src: "/craft/b39.jpg",
    alt: "Hand refinement on a doll prototype",
    title: "Hand-refined sculpting",
    body: "Experienced sculptors adjust transitions, joint neighborhoods, and silhouette flow so the body reads naturally in real light, not only in renders.",
  },
  {
    src: "/craft/b40.jpg",
    alt: "Layered skin coloring process",
    title: "Multi-layer skin coloring",
    body: "We avoid flat, single-pass spray. Translucent layers build depth so silicone can suggest subsurface warmth instead of plastic uniformity.",
  },
  {
    src: "/craft/b41.jpg",
    alt: "Facial detailing and makeup work",
    title: "Hyper-real makeup (where equipped)",
    body: "On heads that ship with detailed finishing, gradients and lip depth are built by hand so expressions stay individual—not copy-paste decals.",
  },
  {
    src: "/craft/b42.jpg",
    alt: "Hand-implanted hair detail",
    title: "Hand-implanted hair",
    body: "Where a listing includes implanted hair, strands are set to follow believable growth direction for softer visual layering at close range.",
  },
  {
    src: "/craft/b43.jpg",
    alt: "Skin texture and pore-level finishing",
    title: "Authentic skin texture",
    body: "Final passes add pore-level variation so highlights break up cleanly—reducing the toy-like sheen you see on rushed mass pieces.",
  },
];

const technology = [
  {
    src: "/craft/b44.jpg",
    alt: "Internal heating and electronics integration",
    title: "Smart heating (select SKUs)",
    body: "Some builds add controlled warming so silicone loses the cold-room feel. Overheat safeguards are part of mature modules—confirm on the product page.",
  },
  {
    src: "/craft/b45.jpg",
    alt: "Sensor and interactive systems",
    title: "Touch & voice feedback (select SKUs)",
    body: "Higher tiers may pair sensitive zones with responsive audio. This is never a generic buzzer track—it is tuned per program when offered.",
  },
  {
    src: "/craft/b47.jpg",
    alt: "Skeleton articulation and posing",
    title: "Yoga-flex skeleton & damping",
    body: "Alloy internals aim for smooth posing without instant loosening. Damping is set so cuddling and deliberate poses both feel cooperative.",
  },
  {
    src: "/brand/hand-finishing-workshop.png",
    alt: "Technician hand-finishing silicone in the studio",
    title: "QC & hand finishing",
    body: "Before anything ships under our curation, workshop teams re-check color, texture, and obvious defects—Chinese craft with a retail-grade bar, not factory-only speed.",
  },
];

export default function CraftGuidePage() {
  return (
    <div className="bg-white text-gray-900">
      <section className="relative">
        <div className="relative h-[min(52vh,420px)] w-full md:h-[min(56vh,480px)]">
          <Image
            src="/craft/b46.jpg"
            alt="Silicone doll craftsmanship and studio detail"
            fill
            className="object-cover object-center"
            priority
            sizes="100vw"
            unoptimized
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/75 via-black/35 to-transparent" />
          <div className="absolute bottom-0 left-0 right-0 px-4 pb-10 md:pb-12">
            <div className="mx-auto max-w-4xl">
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-white/80">
                RealDollHub · Craft guide
              </p>
              <h1 className="mt-3 text-3xl font-bold tracking-tight text-white md:text-4xl">
                From data and mold to finished silicone
              </h1>
              <p className="mt-3 max-w-2xl text-base text-white/90 md:text-lg">
                A practical walkthrough of how Chinese workshop craft, color, and optional smart
                layers stack together—so you know what to look for before you buy.
              </p>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-4xl px-4 py-12 md:py-16">
        <p className="text-lg leading-relaxed text-gray-600">
          We are not interested in cold, anonymous boxes. RealDollHub curates silicone programs where
          engineering and hand work meet: molds that respect real proportions, coloring that reads
          alive under indoor light, and—on select models—optional heating, audio, and skeleton
          upgrades. The goal is simple: narrow the gap between what you imagine and what arrives at
          your door.
        </p>

        <h2 className="mt-14 text-2xl font-bold text-gray-900">The foundation: realism at the surface</h2>
        <p className="mt-3 text-gray-600">
          Every step below happens in partner workshops we audit for repeatability. Details can vary
          by factory batch; your product page lists exactly what is included on that SKU.
        </p>

        <div className="mt-10 grid gap-8 sm:grid-cols-2">
          {foundation.map((item) => (
            <article
              key={item.title}
              className="overflow-hidden rounded-xl border border-gray-200 bg-gray-50 shadow-sm"
            >
              <div className="relative aspect-[4/3] w-full bg-gray-200">
                <Image
                  src={item.src}
                  alt={item.alt}
                  fill
                  className="object-cover object-center"
                  sizes="(max-width: 640px) 100vw, 50vw"
                  unoptimized
                />
              </div>
              <div className="p-5">
                <h3 className="text-lg font-semibold text-gray-900">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-gray-600">{item.body}</p>
              </div>
            </article>
          ))}
        </div>

        <h2 className="mt-16 text-2xl font-bold text-gray-900">
          The technology layer: sensory options
        </h2>
        <p className="mt-3 text-gray-600">
          Not every doll ships with every module. When a feature matters to you—heat, sound,
          standing feet, articulated hands—verify the listing or message us before payment.
        </p>

        <div className="mt-10 grid gap-8 sm:grid-cols-2">
          {technology.map((item) => (
            <article
              key={item.title}
              className="overflow-hidden rounded-xl border border-gray-200 bg-gray-50 shadow-sm"
            >
              <div className="relative aspect-[4/3] w-full bg-gray-200">
                <Image
                  src={item.src}
                  alt={item.alt}
                  fill
                  className="object-cover object-center"
                  sizes="(max-width: 640px) 100vw, 50vw"
                  unoptimized
                />
              </div>
              <div className="p-5">
                <h3 className="text-lg font-semibold text-gray-900">{item.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-gray-600">{item.body}</p>
              </div>
            </article>
          ))}
        </div>

        <p className="mt-10 text-sm leading-relaxed text-gray-600">
          Other premium modules you may see on specific SKUs include internal suction or vibration
          programs, segmented finger bones, subtle vein painting under translucent silicone, hand-implanted
          detail hair, and reinforced standing setups—each is called out on the product card when it
          applies.
        </p>

        <p className="mt-12 rounded-lg border border-amber-200/80 bg-amber-50/90 px-4 py-3 text-sm text-amber-950">
          <strong className="font-semibold">Note:</strong> Feature names above describe categories
          common in premium silicone programs. Your exact configuration always follows the product
          page and order confirmation—not this overview.
        </p>

        <p className="mt-10 text-sm text-gray-500">
          Layout and topic flow were inspired by public craft guides in the industry (e.g.{" "}
          <a
            href="http://html.hunuo.com/2026/01/stww/%E5%85%B3%E4%BA%8E%E6%88%91%E4%BB%AC-%E5%B7%A5%E8%89%BA%E4%B8%8E%E5%AE%9A%E5%88%B6%E6%8C%87%E5%8D%97.html"
            className="text-indigo-600 underline hover:text-indigo-500"
            target="_blank"
            rel="noopener noreferrer"
          >
            sample reference
          </a>
          ). Copy on this page is written for RealDollHub; workshop photos are hosted locally for
          stable loading.
        </p>

        <p className="mt-6 text-gray-600">
          <Link href="/about" className="font-medium text-indigo-600 underline hover:text-indigo-500">
            Brand story
          </Link>
          {" · "}
          <Link href="/contact" className="font-medium text-indigo-600 underline hover:text-indigo-500">
            Contact
          </Link>
          {" · "}
          <Link href="/products" className="font-medium text-indigo-600 underline hover:text-indigo-500">
            Shop
          </Link>
        </p>
      </div>
    </div>
  );
}
