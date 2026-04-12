import Image from "next/image";
import Link from "next/link";

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-indigo-600">
        RealDollHub
      </p>
      <h1 className="mt-3 text-3xl font-bold tracking-tight text-gray-900 md:text-4xl">
        More than a doll. A resonance of care and craft.
      </h1>
      <p className="mt-4 text-lg leading-relaxed text-gray-600">
        At RealDollHub we are not simply listing products—we are curating a calmer, more
        intentional way to choose something deeply personal. Here, the line between what
        feels real and what you imagine is softened: not erased, but redrawn with respect
        and clarity.
      </p>
      <p className="mt-3 text-sm text-gray-600">
        Read the full three-chapter narrative:{" "}
        <Link href="/brand-story" className="font-medium text-indigo-600 underline hover:text-indigo-500">
          Brand story
        </Link>
        .
      </p>

      <figure className="mt-10 overflow-hidden rounded-2xl border border-gray-200 bg-gray-100 shadow-sm">
        <div className="relative aspect-[16/10] w-full md:aspect-[2/1]">
          <Image
            src="/brand/hand-finishing-workshop.png"
            alt="Craftsperson airbrushing fine detail on a silicone torso in a professional workshop"
            fill
            className="object-cover object-center"
            sizes="(max-width: 768px) 100vw, 768px"
            priority
            unoptimized
          />
        </div>
        <figcaption className="border-t border-gray-100 px-4 py-3 text-center text-xs text-gray-500">
          Hand finishing and color work—where precision meets material science in the studio.
        </figcaption>
      </figure>

      <article className="mt-12 space-y-10">
        <section>
        <h2 className="text-xl font-semibold text-gray-900">Obsessed with getting the details right</h2>
        <p className="mt-3 leading-7 text-gray-600">
          Our work is rooted in Chinese manufacturing craft: experienced technicians, tight
          tolerances on assembly, and a refusal to ship “good enough.” RealDollHub is not built
          for anonymous mass turnover. From how a joint resists and settles into motion to how
          skin reads under ordinary room light, finishing and hand work are checked the way you
          would expect from a serious domestic studio—not a single hero photo on a sales page.
        </p>
        </section>

        <section>
        <h2 className="text-xl font-semibold text-gray-900">Made in China, held to our own bar</h2>
        <p className="mt-3 leading-7 text-gray-600">
          Production runs on China&apos;s mature specialty supply chain—materials, tooling, and
          skilled labor in one ecosystem. Our QC is written and enforced here: clear checkpoints,
          documented criteria, and no rushing the final sign-off. We set inspection thresholds
          above typical industry baselines because the goal is not volume alone, but movement
          that feels natural and surfaces that stay convincing over time.
        </p>
        </section>

        <section>
        <h2 className="text-xl font-semibold text-gray-900">What that means for you</h2>
        <p className="mt-3 leading-7 text-gray-600">
          You receive listings we would stand behind in daylight: discreet fulfillment, transparent
          lead-time communication, and silicone-forward curation aligned with long-term ownership.
          If something is unclear before you pay, we would rather answer twice than guess once.
        </p>
        </section>
      </article>

      <p className="mt-12 text-sm text-gray-600">
        Want the step-by-step workshop breakdown? See our{" "}
        <Link href="/craft" className="font-medium text-indigo-600 underline hover:text-indigo-500">
          Craft &amp; bespoke guide
        </Link>
        . Questions?{" "}
        <Link href="/contact" className="font-medium text-indigo-600 underline hover:text-indigo-500">
          Contact us
        </Link>
        .
      </p>
    </div>
  );
}
