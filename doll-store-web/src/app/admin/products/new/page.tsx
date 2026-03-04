import { requireAdminSession } from "@/lib/admin-auth";
import { ProductEditorForm } from "../ProductEditorForm";

export default async function AdminNewProductPage() {
  await requireAdminSession();
  return (
    <div className="mx-auto max-w-4xl px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">Create Product</h1>
      <p className="mt-2 text-sm text-gray-600">Create a product and set cost/sale price strategy.</p>
      <div className="mt-6">
        <ProductEditorForm
          mode="create"
          initialValue={{
            slug: "",
            name: "",
            description: "",
            categoryId: "silicone",
            material: "Silicone",
            currency: "CNY",
            costPrice: 0,
            salePrice: 0,
            compareAtPrice: undefined,
            sourceType: "origin",
            shippingQuoteMode: "quote_after_confirm",
            isFreeShippingOverseas: false,
            images: [],
            videoUrl: "",
            addOnOptions: [],
            featured: false,
            visibleRegions: ["ALL"],
            shippableCountries: [],
          }}
        />
      </div>
    </div>
  );
}

