import Link from "next/link";
import { requireAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-admin";

type AdminProductRow = {
  id: string;
  slug: string;
  name: string;
  source_type: string;
  cost_currency: "CNY" | "USD" | "EUR" | null;
  sale_currency: "CNY" | "USD" | "EUR" | null;
  cost_price: number;
  sale_price: number;
  asset_status: "raw" | "processed" | "published" | null;
  is_free_shipping_overseas: boolean;
  featured: boolean;
  updated_at: string;
};

export default async function AdminProductsPage() {
  await requireAdminSession();
  const supabase = getSupabaseAdmin();
  if (!supabase) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-10">
        <h1 className="text-2xl font-bold text-gray-900">Admin Products</h1>
        <p className="mt-3 text-red-700">Supabase is not configured. Set env vars before using admin CMS.</p>
      </div>
    );
  }

  const { data, error } = await supabase
    .from("products")
    .select("id, slug, name, source_type, cost_currency, sale_currency, cost_price, sale_price, asset_status, is_free_shipping_overseas, featured, updated_at")
    .order("updated_at", { ascending: false })
    .limit(500);

  return (
    <div className="mx-auto max-w-6xl px-4 py-10">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Admin Products</h1>
        <Link href="/admin/products/new" className="rounded bg-gray-900 px-4 py-2 text-sm text-white hover:bg-gray-800">
          + New product
        </Link>
      </div>
      <p className="mt-2 text-sm text-gray-600">Manage sale price, cost reference, and shipping strategy.</p>
      {error ? (
        <p className="mt-4 rounded bg-red-50 p-3 text-sm text-red-700">{error.message}</p>
      ) : (
        <div className="mt-6 overflow-x-auto rounded border border-gray-200">
          <table className="min-w-full divide-y divide-gray-200 text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Name</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Slug</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Source</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Cost</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Sale</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Shipping</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Asset</th>
                <th className="px-3 py-2 text-left font-medium text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100 bg-white">
              {(data as AdminProductRow[] | null)?.map((row) => (
                <tr key={row.id}>
                  <td className="px-3 py-2">{row.name}</td>
                  <td className="px-3 py-2 text-gray-500">{row.slug}</td>
                  <td className="px-3 py-2">{row.source_type}</td>
                  <td className="px-3 py-2">
                    {(row.cost_currency ?? "CNY")} {Number(row.cost_price ?? 0).toLocaleString()}
                  </td>
                  <td className="px-3 py-2 font-medium">
                    {(row.sale_currency ?? "CNY")} {Number(row.sale_price ?? 0).toLocaleString()}
                  </td>
                  <td className="px-3 py-2">
                    {row.is_free_shipping_overseas ? "Free overseas" : "Quote after confirm"}
                  </td>
                  <td className="px-3 py-2">{row.asset_status ?? "published"}</td>
                  <td className="px-3 py-2">
                    <Link className="text-gray-700 underline hover:text-gray-900" href={`/admin/products/${row.id}`}>
                      Edit
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

