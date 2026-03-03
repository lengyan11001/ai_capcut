import Link from "next/link";

export function Footer() {
  return (
    <footer className="mt-auto border-t border-gray-200 bg-gray-50">
      <div className="mx-auto max-w-6xl px-4 py-10">
        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          <div>
            <h3 className="font-semibold text-gray-900">Shop</h3>
            <ul className="mt-3 space-y-2">
              <li>
                <Link href="/products" className="text-gray-600 hover:text-gray-900">
                  All Products
                </Link>
              </li>
              <li>
                <Link href="/guides" className="text-gray-600 hover:text-gray-900">
                  Buying Guides
                </Link>
              </li>
              <li>
                <Link href="/category/full-body" className="text-gray-600 hover:text-gray-900">
                  Full Body
                </Link>
              </li>
              <li>
                <Link href="/category/tpe" className="text-gray-600 hover:text-gray-900">
                  TPE Dolls
                </Link>
              </li>
              <li>
                <Link href="/category/silicone" className="text-gray-600 hover:text-gray-900">
                  Silicone
                </Link>
              </li>
              <li>
                <Link href="/category/accessories" className="text-gray-600 hover:text-gray-900">
                  Accessories
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">Info</h3>
            <ul className="mt-3 space-y-2">
              <li>
                <Link href="/about" className="text-gray-600 hover:text-gray-900">
                  About Us
                </Link>
              </li>
              <li>
                <Link href="/shipping" className="text-gray-600 hover:text-gray-900">
                  Shipping & Delivery
                </Link>
              </li>
              <li>
                <Link href="/guides/how-to-choose-first-doll" className="text-gray-600 hover:text-gray-900">
                  First Purchase Guide
                </Link>
              </li>
              <li>
                <Link href="/contact" className="text-gray-600 hover:text-gray-900">
                  Contact
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">Legal</h3>
            <ul className="mt-3 space-y-2">
              <li>
                <Link href="/privacy" className="text-gray-600 hover:text-gray-900">
                  Privacy Policy
                </Link>
              </li>
            </ul>
          </div>
          <div>
            <h3 className="font-semibold text-gray-900">Trust</h3>
            <p className="mt-3 text-sm text-gray-600">
              Discreet packaging. Secure checkout. We’ll contact you for secure payment after order confirmation.
            </p>
          </div>
        </div>
        <p className="mt-8 border-t border-gray-200 pt-6 text-center text-sm text-gray-500">
          © {new Date().getFullYear()} Doll Store. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
