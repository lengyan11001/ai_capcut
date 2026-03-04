import Link from "next/link";
import { requireAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { normalizeOrderItems } from "@/lib/order-items";

type AdminOrderRow = {
  id: string;
  email: string;
  shipping_name: string;
  total: number;
  currency: string;
  status: string;
  created_at: string;
  items: unknown;
};

export default async function AdminOrdersPage() {
  await requireAdminSession();
  const supabase = getSupabaseAdmin();

  if (!supabase) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900">Admin Orders</h1>
        <p className="mt-3 text-red-700">Supabase is not configured. Set env vars before using admin CMS.</p>
      </div>
    );
  }

  const { data, error } = await supabase
    .from("orders")
    .select("id, email, shipping_name, total, currency, status, created_at, items")
    .order("created_at", { ascending: false })
    .limit(500);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Admin Orders</h1>
        <div className="flex items-center gap-3 text-sm">
          <Link href="/admin/products" className="text-gray-700 underline hover:text-gray-900">
            Products
          </Link>
        </div>
      </div>
      <p className="mt-2 text-sm text-gray-600">Track payment status, shipping, and logistics number.</p>
      {error ? (
        <p className="mt-4 rounded bg-red-50 p-3 text-sm text-red-700">{error.message}</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Created</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Order</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Customer</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Payment</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Status</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Tracking</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Amount</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {(data as AdminOrderRow[] | null)?.map((row) => {
                const details = normalizeOrderItems(row.items);
                return (
                  <tr key={row.id}>
                    <td className="px-3 py-2 text-gray-500">{new Date(row.created_at).toLocaleString()}</td>
                    <td className="px-3 py-2 font-mono text-xs text-gray-700">{row.id}</td>
                    <td className="px-3 py-2">
                      <div className="font-medium text-gray-900">{row.shipping_name}</div>
                      <div className="text-xs text-gray-500">{row.email}</div>
                    </td>
                    <td className="px-3 py-2">{details.paymentMethod === "crypto_manual" ? "Crypto" : "Manual"}</td>
                    <td className="px-3 py-2">
                      <span className="rounded bg-gray-100 px-2 py-1 text-xs text-gray-700">{row.status ?? "pending"}</span>
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-600">{details.fulfillment?.trackingNumber ?? "-"}</td>
                    <td className="px-3 py-2 font-medium">
                      {row.currency ?? "CNY"} {Number(row.total ?? 0).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <Link className="text-gray-700 underline hover:text-gray-900" href={`/admin/orders/${row.id}`}>
                        Edit
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
