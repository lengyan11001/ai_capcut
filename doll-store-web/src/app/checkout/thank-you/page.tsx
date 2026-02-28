import Link from "next/link";

export default async function ThankYouPage({
  searchParams,
}: {
  searchParams: Promise<{ orderId?: string }>;
}) {
  const params = await searchParams;
  const orderId = params.orderId ?? "";

  return (
    <div className="mx-auto max-w-2xl px-4 py-16 text-center">
      <h1 className="text-2xl font-bold text-gray-900">Thank you for your order</h1>
      <p className="mt-4 text-gray-600">
        We’ve received your order and will contact you shortly for secure payment and shipping details.
      </p>
      {orderId && (
        <p className="mt-2 text-sm text-gray-500">Order reference: {orderId}</p>
      )}
      <Link
        href="/products"
        className="mt-8 inline-block rounded bg-gray-900 px-6 py-3 text-white hover:bg-gray-800"
      >
        Continue shopping
      </Link>
    </div>
  );
}
