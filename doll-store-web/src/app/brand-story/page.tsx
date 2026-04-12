import Image from "next/image";
import Link from "next/link";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Brand story | RealDollHub",
  description:
    "Why RealDollHub exists: a quiet space for intentional choice, Chinese workshop excellence, and discreet fulfillment you can trust.",
};

function Chapter({
  n,
  title,
  kicker,
  children,
  image,
}: {
  n: string;
  title: string;
  kicker: string;
  children: React.ReactNode;
  image: { src: string; alt: string };
}) {
  return (
    <section className="border-t border-gray-200 pt-14 first:border-t-0 first:pt-0">
      <p className="text-xs font-semibold uppercase tracking-[0.28em] text-indigo-600">
        Chapter {n}
      </p>
      <h2 className="mt-2 text-2xl font-bold text-gray-900 md:text-3xl">{title}</h2>
      <p className="mt-1 text-sm font-medium text-gray-500">{kicker}</p>
      <div className="mt-8 overflow-hidden rounded-2xl border border-gray-200 bg-gray-100 shadow-sm">
        <div className="relative aspect-[16/10] w-full md:aspect-[2/1]">
          <Image
            src={image.src}
            alt={image.alt}
            fill
            className="object-cover object-center"
            sizes="(max-width: 768px) 100vw, 896px"
            unoptimized
          />
        </div>
      </div>
      <div className="mt-8 space-y-4 text-base leading-relaxed text-gray-600">{children}</div>
    </section>
  );
}

export default function BrandStoryPage() {
  return (
    <div className="bg-white">
      <div className="relative">
        <div className="relative h-[min(48vh,380px)] w-full md:h-[min(52vh,440px)]">
          <Image
            src="/craft/b46.jpg"
            alt="RealDollHub brand — craftsmanship and presence"
            fill
            className="object-cover object-center"
            priority
            sizes="100vw"
            unoptimized
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/40 to-black/20" />
          <div className="absolute bottom-0 left-0 right-0 px-4 pb-10 md:pb-14">
            <div className="mx-auto max-w-3xl text-center">
              <p className="text-xs font-semibold uppercase tracking-[0.28em] text-white/85">
                RealDollHub
              </p>
              <h1 className="mt-3 text-3xl font-bold tracking-tight text-white md:text-5xl">
                Brand story
              </h1>
              <p className="mx-auto mt-4 max-w-xl text-base text-white/90 md:text-lg">
                Three chapters: why we started, what we believe about “feeling real,” and the
                promise behind every discreet shipment.
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-3xl px-4 py-14 md:py-20">
        <Chapter
          n="1"
          title="The origin"
          kicker="A calmer way to choose"
          image={{
            src: "/brand/hand-finishing-workshop.png",
            alt: "Technician finishing silicone in a Chinese workshop",
          }}
        >
          <p>
            The world rarely slows down—and choosing something this personal shouldn&apos;t feel
            like a noisy auction of misleading renders. RealDollHub began from a simple frustration:
            too many listings, not enough clarity on what actually ships, and too little respect for
            the buyer&apos;s privacy after checkout.
          </p>
          <p>
            We did not set out to be another anonymous catalog. We set out to be a{" "}
            <strong className="font-semibold text-gray-800">hub</strong> where serious Chinese
            workshop output meets honest copy, silicone-first curation, and fulfillment you can
            follow without guesswork. The name is literal: a crossroads of craft, materials, and care—
            not a fantasy pasted on top of reality.
          </p>
          <p>
            For us, the product is never “just silicone.” It is a tangible answer to a private need
            for presence, comfort, and imagination—handled with the same discretion we would want
            for ourselves.
          </p>
        </Chapter>

        <Chapter
          n="2"
          title="The philosophy"
          kicker="Feeling—not only seeing"
          image={{
            src: "/craft/b40.jpg",
            alt: "Layered skin coloring and realistic silicone finish",
          }}
        >
          <p>
            Our core bias is <strong className="font-semibold text-gray-800">warmth over cold plastic</strong>
            . A companion-grade piece should not only photograph well; it should settle into believable
            weight, motion, and surface read when the lights are ordinary and the room is quiet.
          </p>
          <p>
            That pursuit took years of iteration with partner workshops: finding the translucency
            band that still looks human under indoor LEDs, pairing skeleton damping with poses people
            actually use, and refusing to hype features that are not on the SKU you paid for.
          </p>
          <p>
            Where a listing includes smart thermoregulation or responsive audio, those layers exist
            to shrink the “silicone chill” gap—not to replace care, storage, or realistic expectations.
            We are still building objects; we simply refuse to treat them like disposable toys.
          </p>
        </Chapter>

        <Chapter
          n="3"
          title="The promise"
          kicker="Discreet delivery, clear handoff"
          image={{
            src: "/craft/b44.jpg",
            alt: "Quality control and product readiness before shipping",
          }}
        >
          <p>
            RealDollHub is meant to sit above commodity churn. To our collectors, each unit is both a
            functional work of art and a private anchor for late nights when judgment is the last
            thing you need. Our mission stays narrow: honor your instincts with{" "}
            <strong className="font-semibold text-gray-800">transparent listings</strong>,{" "}
            <strong className="font-semibold text-gray-800">documented QC habits</strong>, and{" "}
            <strong className="font-semibold text-gray-800">discreet packaging</strong> that does not
            advertise your life choices on the label.
          </p>
          <p>
            Before handoff, pieces pass a final readiness pass aligned with the factory program—finish,
            obvious defects, and configuration checks—so we are not guessing at the loading dock. When
            the box leaves, we know we are sending more than resin and metal: we are sending a promise
            that you should not have to settle for opacity, shame, or “surprise me” quality.
          </p>
          <p>
            If something in the story still feels abstract, read the{" "}
            <Link href="/craft" className="font-medium text-indigo-600 underline hover:text-indigo-500">
              Craft &amp; bespoke guide
            </Link>{" "}
            next—then{" "}
            <Link href="/contact" className="font-medium text-indigo-600 underline hover:text-indigo-500">
              talk to us
            </Link>{" "}
            with specifics.
          </p>
        </Chapter>

        <p className="mt-16 border-t border-gray-200 pt-8 text-center text-xs text-gray-400">
          Narrative structure inspired by public brand-story pages in the industry (e.g.{" "}
          <a
            href="http://html.hunuo.com/2026/01/stww/%E5%85%B3%E4%BA%8E%E6%88%91%E4%BB%AC-%E5%93%81%E7%89%8C%E6%95%85%E4%BA%8B.html"
            className="text-indigo-600 underline hover:text-indigo-500"
            target="_blank"
            rel="noopener noreferrer"
          >
            reference layout
          </a>
          ). All copy is original to RealDollHub.
        </p>

        <p className="mt-6 text-center text-sm text-gray-600">
          <Link href="/about" className="font-medium text-indigo-600 underline hover:text-indigo-500">
            About us
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
