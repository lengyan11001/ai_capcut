import Link from "next/link";
import Image from "next/image";
import { getCategories, getFeaturedProducts } from "@/lib/data";
import { ProductCard } from "@/components/ProductCard";

const HERO_IMAGE = "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=1200&q=80";

export default function HomePage() {
  const categories = getCategories();
  const featured = getFeaturedProducts();

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
            Premium Collectibles
          </h1>
          <p className="mt-4 text-lg text-white/90 drop-shadow">
            Full body dolls and accessories. Discreet packaging, worldwide delivery.
          </p>
          <Link
            href="/products"
            className="mt-6 inline-block rounded bg-white px-6 py-3 font-medium text-gray-900 hover:bg-gray-100"
          >
            Shop All
          </Link>
        </div>
      </section>

      {/* Category cards */}
      <section className="mx-auto max-w-6xl px-4 py-12">
        <h2 className="text-xl font-semibold text-gray-900">Shop by Category</h2>
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
        <h2 className="text-xl font-semibold text-gray-900">Featured</h2>
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
            View all products
          </Link>
        </div>
      </section>

      {/* Trust bar */}
      <section className="border-t border-gray-200 bg-gray-50 py-10">
        <div className="mx-auto max-w-6xl px-4">
          <div className="grid gap-8 text-center sm:grid-cols-3">
            <div>
              <h3 className="font-semibold text-gray-900">Discreet Packaging</h3>
              <p className="mt-1 text-sm text-gray-600">
                Plain packaging, no sensitive labels. Your privacy is our priority.
              </p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Secure Checkout</h3>
              <p className="mt-1 text-sm text-gray-600">
                We’ll contact you for secure payment after order confirmation.
              </p>
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">Support</h3>
              <p className="mt-1 text-sm text-gray-600">
                Questions? Contact us anytime. Returns policy available.
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
