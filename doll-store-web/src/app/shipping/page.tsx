import { getSupportedCountryCodes } from "@/lib/shipping";

export default function ShippingPage() {
  const countries = getSupportedCountryCodes();
  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <h1 className="text-2xl font-bold text-gray-900">Shipping & Delivery</h1>
      <div className="mt-6 space-y-6 text-gray-600">
        <p>
          We ship worldwide with discreet packaging. No sensitive labels or content on the outside.
        </p>
        <p>
          Delivery times vary by region. After you place an order, we will contact you with
          shipping options and an estimated delivery window.
        </p>
        <p>
          Shipping costs are confirmed after destination review. Current prices on product pages are
          factory-to-forwarder quotes.
        </p>
        <p>
          For returns and refunds, please see our policies or contact us directly.
        </p>
        <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
          <h2 className="font-medium text-gray-900">Current shipping allowlist (preview)</h2>
          <p className="mt-2 text-sm">
            {countries.join(", ")}
          </p>
          <p className="mt-2 text-xs text-gray-500">
            We can add more countries after freight lane confirmation.
          </p>
        </div>
      </div>
    </div>
  );
}
