"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

type FormValues = {
  slug: string;
  name: string;
  description: string;
  categoryId: string;
  material: string;
  currency: "CNY" | "USD" | "EUR";
  costPrice: number;
  salePrice: number;
  compareAtPrice?: number;
  sourceType: "origin" | "overseas_us" | "overseas_eu";
  shippingQuoteMode: "included" | "quote_after_confirm";
  isFreeShippingOverseas: boolean;
  images: string[];
  videoUrl?: string;
  addOnOptions: string[];
  featured: boolean;
  visibleRegions: string[];
  shippableCountries: string[];
};

interface Props {
  mode: "create" | "edit";
  productId?: string;
  initialValue: FormValues;
}

function parseCommaList(input: string): string[] {
  return input
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

export function ProductEditorForm({ mode, productId, initialValue }: Props) {
  const router = useRouter();
  const [form, setForm] = useState<FormValues>(initialValue);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const imageInput = useMemo(() => form.images.join(", "), [form.images]);
  const addOnInput = useMemo(() => form.addOnOptions.join(", "), [form.addOnOptions]);
  const visibleRegionsInput = useMemo(() => form.visibleRegions.join(", "), [form.visibleRegions]);
  const shippableCountriesInput = useMemo(
    () => form.shippableCountries.join(", "),
    [form.shippableCountries]
  );

  const uploadFile = async (file: File, target: "image" | "video") => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch("/api/admin/upload", {
      method: "POST",
      body: fd,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error ?? "Upload failed");
    if (target === "image") {
      setForm((f) => ({ ...f, images: [...f.images, data.url] }));
    } else {
      setForm((f) => ({ ...f, videoUrl: data.url }));
    }
  };

  const onUploadImage = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      await uploadFile(file, "image");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const onUploadVideo = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      await uploadFile(file, "video");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      const payload = {
        ...form,
        images: parseCommaList(imageInput),
        addOnOptions: parseCommaList(addOnInput),
        visibleRegions: parseCommaList(visibleRegionsInput),
        shippableCountries: parseCommaList(shippableCountriesInput),
      };
      const endpoint = mode === "create" ? "/api/admin/products" : `/api/admin/products/${productId}`;
      const method = mode === "create" ? "POST" : "PATCH";
      const res = await fetch(endpoint, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Save failed");
      setSuccess("Saved successfully.");
      router.refresh();
      if (mode === "create" && data.id) {
        router.push(`/admin/products/${data.id}`);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} className="space-y-4 rounded-lg border border-gray-200 p-5">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Slug *</span>
          <input
            required
            value={form.slug}
            onChange={(e) => setForm((f) => ({ ...f, slug: e.target.value }))}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Name *</span>
          <input
            required
            value={form.name}
            onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          />
        </label>
      </div>

      <label className="text-sm block">
        <span className="block font-medium text-gray-700">Description</span>
        <textarea
          rows={3}
          value={form.description}
          onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
          className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
        />
      </label>

      <div className="grid gap-4 md:grid-cols-3">
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Cost price *</span>
          <input
            type="number"
            required
            value={form.costPrice}
            onChange={(e) => setForm((f) => ({ ...f, costPrice: Number(e.target.value) }))}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Sale price *</span>
          <input
            type="number"
            required
            value={form.salePrice}
            onChange={(e) => setForm((f) => ({ ...f, salePrice: Number(e.target.value) }))}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Compare-at</span>
          <input
            type="number"
            value={form.compareAtPrice ?? ""}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                compareAtPrice: e.target.value ? Number(e.target.value) : undefined,
              }))
            }
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          />
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Category</span>
          <input
            value={form.categoryId}
            onChange={(e) => setForm((f) => ({ ...f, categoryId: e.target.value }))}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Material</span>
          <input
            value={form.material}
            onChange={(e) => setForm((f) => ({ ...f, material: e.target.value }))}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Source type</span>
          <select
            value={form.sourceType}
            onChange={(e) =>
              setForm((f) => ({ ...f, sourceType: e.target.value as FormValues["sourceType"] }))
            }
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          >
            <option value="origin">origin</option>
            <option value="overseas_us">overseas_us</option>
            <option value="overseas_eu">overseas_eu</option>
          </select>
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Image URLs (comma-separated)</span>
          <input
            value={imageInput}
            onChange={(e) => setForm((f) => ({ ...f, images: parseCommaList(e.target.value) }))}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Video URL</span>
          <input
            value={form.videoUrl ?? ""}
            onChange={(e) => setForm((f) => ({ ...f, videoUrl: e.target.value }))}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          />
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Upload image</span>
          <input type="file" accept="image/*" onChange={onUploadImage} className="mt-1 block w-full text-sm" />
        </label>
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Upload video</span>
          <input type="file" accept="video/*" onChange={onUploadVideo} className="mt-1 block w-full text-sm" />
        </label>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Add-on options (comma-separated)</span>
          <input
            value={addOnInput}
            onChange={(e) => setForm((f) => ({ ...f, addOnOptions: parseCommaList(e.target.value) }))}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          />
        </label>
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Visible regions (comma-separated)</span>
          <input
            value={visibleRegionsInput}
            onChange={(e) => setForm((f) => ({ ...f, visibleRegions: parseCommaList(e.target.value) }))}
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          />
        </label>
      </div>

      <label className="text-sm block">
        <span className="block font-medium text-gray-700">Shippable countries (comma-separated ISO2)</span>
        <input
          value={shippableCountriesInput}
          onChange={(e) => setForm((f) => ({ ...f, shippableCountries: parseCommaList(e.target.value) }))}
          className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
        />
      </label>

      <div className="flex flex-wrap items-center gap-6 text-sm">
        <label className="inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={form.featured}
            onChange={(e) => setForm((f) => ({ ...f, featured: e.target.checked }))}
          />
          Featured
        </label>
        <label className="inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={form.isFreeShippingOverseas}
            onChange={(e) => setForm((f) => ({ ...f, isFreeShippingOverseas: e.target.checked }))}
          />
          Free shipping overseas
        </label>
        <label className="inline-flex items-center gap-2">
          Shipping mode
          <select
            value={form.shippingQuoteMode}
            onChange={(e) =>
              setForm((f) => ({
                ...f,
                shippingQuoteMode: e.target.value as FormValues["shippingQuoteMode"],
              }))
            }
            className="rounded border border-gray-300 px-2 py-1"
          >
            <option value="quote_after_confirm">quote_after_confirm</option>
            <option value="included">included</option>
          </select>
        </label>
      </div>

      {error && <p className="rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>}
      {success && <p className="rounded bg-green-50 p-2 text-sm text-green-700">{success}</p>}
      <button
        type="submit"
        disabled={submitting || uploading}
        className="rounded bg-gray-900 px-5 py-2 font-medium text-white hover:bg-gray-800 disabled:opacity-70"
      >
        {submitting ? "Saving..." : mode === "create" ? "Create product" : "Save changes"}
      </button>
    </form>
  );
}

