import Link from "next/link";
import { requireAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { normalizeOrderItems } from "@/lib/order-items";
import OrderEditorForm from "../OrderEditorForm";
import { formatMoney } from "@/lib/money";

type OrderRow = {
  id: string;
  email: string;
  shipping_name: string;
  shipping_address: string;
  shipping_phone: string | null;
  total: number;
  currency: "CNY" | "USD" | "EUR";
  status: string;
  created_at: string;
  items: unknown;
};

export default async function AdminOrderDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireAdminSession();
  const { id } = await params;
  const supabase = getSupabaseAdmin();

  if (!supabase) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900">Order detail</h1>
        <p className="mt-3 text-red-700">Supabase is not configured.</p>
      </div>
    );
  }

  const { data, error } = await supabase
    .from("orders")
    .select("id, email, shipping_name, shipping_address, shipping_phone, total, currency, status, created_at, items")
    .eq("id", id)
    .single();

  if (error || !data) {
    return (
      <div className="mx-auto max-w-5xl px-4 py-10">
        <p className="rounded bg-red-50 p-3 text-sm text-red-700">{error?.message ?? "Order not found"}</p>
        <Link href="/admin/orders" className="mt-3 inline-block text-sm text-gray-700 underline">
          Back to orders
        </Link>
      </div>
    );
  }

  const order = data as OrderRow;
  const details = normalizeOrderItems(order.items);

  return (
    <div className="mx-auto max-w-5xl px-4 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Order detail</h1>
        <Link href="/admin/orders" className="text-sm text-gray-700 underline hover:text-gray-900">
          Back to orders
        </Link>
      </div>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="space-y-4 rounded border border-gray-200 bg-gray-50 p-4">
          <div>
            <p className="text-xs text-gray-500">Order ID</p>
            <p className="font-mono text-sm text-gray-800">{order.id}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Customer</p>
            <p className="text-sm font-medium text-gray-900">{order.shipping_name}</p>
            <p className="text-sm text-gray-700">{order.email}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Shipping address</p>
            <p className="text-sm text-gray-800">{order.shipping_address}</p>
            {order.shipping_phone ? <p className="text-sm text-gray-700">{order.shipping_phone}</p> : null}
          </div>
          <div>
            <p className="text-xs text-gray-500">Payment</p>
            <p className="text-sm text-gray-800">
              {details.paymentMethod === "crypto_manual"
                ? "Crypto (manual)"
                : details.paymentMethod === "paypal"
                  ? "PayPal"
                  : "Manual contact"}
            </p>
            {details.payment?.txHash ? (
              <p className="break-all text-xs text-gray-600">tx: {details.payment.txHash}</p>
            ) : null}
          </div>
          <div>
            <p className="text-xs text-gray-500">Amount</p>
            <p className="text-sm font-medium text-gray-900">{formatMoney(order.total, order.currency ?? "CNY")}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500">Created</p>
            <p className="text-sm text-gray-800">{new Date(order.created_at).toLocaleString()}</p>
          </div>
        </div>

        <OrderEditorForm
          id={order.id}
          initialStatus={order.status ?? "pending"}
          initialCarrier={details.fulfillment?.carrier ?? ""}
          initialTrackingNumber={details.fulfillment?.trackingNumber ?? ""}
          initialTrackingUrl={details.fulfillment?.trackingUrl ?? ""}
          initialAdminNote={details.notes?.admin ?? ""}
          initialTxHash={details.payment?.txHash ?? ""}
          initialPaidAmount={details.payment?.paidAmount?.toString() ?? ""}
          initialProofImages={details.fulfillment?.proofImages ?? []}
          initialProofVideos={details.fulfillment?.proofVideos ?? []}
        />
      </div>

      <div className="mt-6 rounded border border-gray-200 bg-white p-4">
        <h2 className="font-semibold text-gray-900">Order lines</h2>
        <ul className="mt-3 space-y-2 text-sm text-gray-700">
          {details.lines.map((line) => (
            <li key={`${line.productId}-${line.slug}`} className="flex items-center justify-between gap-3">
              <span>{line.name} × {line.quantity}</span>
              <span>
                {line.currency ?? "CNY"} {Number(line.price * line.quantity).toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
