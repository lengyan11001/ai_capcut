import { notFound } from "next/navigation";
import { requireAdminSession } from "@/lib/admin-auth";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { ProductEditorForm } from "../ProductEditorForm";

type DbProduct = {
  id: string;
  slug: string;
  name: string;
  description: string;
  category_id: string;
  material: string;
  currency: "CNY" | "USD" | "EUR";
  cost_currency: "CNY" | "USD" | "EUR" | null;
  sale_currency: "CNY" | "USD" | "EUR" | null;
  cost_price: number;
  sale_price: number;
  compare_at_price: number | null;
  source_type: "origin" | "overseas_us" | "overseas_eu";
  shipping_quote_mode: "included" | "quote_after_confirm";
  is_free_shipping_overseas: boolean;
  images: string[] | null;
  video_url: string | null;
  add_on_options: string[] | null;
  featured: boolean;
  asset_status: "raw" | "processed" | "published" | null;
  visible_regions: string[] | null;
  shippable_countries: string[] | null;
};

export default async function AdminEditProductPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  await requireAdminSession();
  const { id } = await params;
  const supabase = getSupabaseAdmin();
  if (!supabase) notFound();

  const { data, error } = await supabase.from("products").select("*").eq("id", id).single();
  if (error || !data) notFound();
  const row = data as DbProduct;

  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">Edit Product</h1>
      <p className="mt-2 text-sm text-gray-600">{row.name}</p>
      <div className="mt-6">
        <ProductEditorForm
          mode="edit"
          productId={id}
          initialValue={{
            slug: row.slug ?? "",
            name: row.name ?? "",
            description: row.description ?? "",
            categoryId: row.category_id ?? "silicone",
            material: row.material ?? "",
            costCurrency: row.cost_currency ?? row.currency ?? "CNY",
            saleCurrency: row.sale_currency ?? row.currency ?? "CNY",
            costPrice: Number(row.cost_price ?? 0),
            salePrice: Number(row.sale_price ?? 0),
            compareAtPrice: row.compare_at_price ?? undefined,
            sourceType: row.source_type ?? "origin",
            shippingQuoteMode: row.shipping_quote_mode ?? "quote_after_confirm",
            isFreeShippingOverseas: row.is_free_shipping_overseas ?? false,
            images: row.images ?? [],
            videoUrl: row.video_url ?? "",
            addOnOptions: row.add_on_options ?? [],
            featured: row.featured ?? false,
            assetStatus: row.asset_status ?? "published",
            visibleRegions: row.visible_regions ?? ["ALL"],
            shippableCountries: row.shippable_countries ?? [],
          }}
        />
      </div>
    </div>
  );
}

