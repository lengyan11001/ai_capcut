"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";

type FormValues = {
  slug: string;
  name: string;
  description: string;
  categoryId: string;
  material: string;
  costCurrency: "CNY" | "USD" | "EUR";
  saleCurrency: "CNY" | "USD" | "EUR";
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
  assetStatus: "raw" | "processed" | "published";
  visibleRegions: string[];
  shippableCountries: string[];
};

type MediaItem = {
  id: string;
  type: "image" | "video";
  url: string;
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
  const [mediaItems, setMediaItems] = useState<MediaItem[]>(() => {
    const images = (initialValue.images ?? []).map((url, index) => ({
      id: `image-${index}-${url}`,
      type: "image" as const,
      url,
    }));
    const videos = initialValue.videoUrl
      ? [{ id: `video-0-${initialValue.videoUrl}`, type: "video" as const, url: initialValue.videoUrl }]
      : [];
    return [...videos, ...images];
  });
  const [manualMediaUrl, setManualMediaUrl] = useState("");
  const [manualMediaType, setManualMediaType] = useState<"image" | "video">("image");
  const [previewVideoUrl, setPreviewVideoUrl] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const addOnInput = useMemo(() => form.addOnOptions.join(", "), [form.addOnOptions]);
  const visibleRegionsInput = useMemo(() => form.visibleRegions.join(", "), [form.visibleRegions]);
  const shippableCountriesInput = useMemo(
    () => form.shippableCountries.join(", "),
    [form.shippableCountries]
  );

  const uploadFile = async (file: File) => {
    const signedRes = await fetch("/api/admin/upload", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        filename: file.name,
        contentType: file.type || "application/octet-stream",
        folder: "products",
      }),
    });
    const signedData = await signedRes.json();
    if (!signedRes.ok) throw new Error(signedData.error ?? "Upload init failed");
    const uploadRes = await fetch(signedData.signedUrl as string, {
      method: "PUT",
      headers: { "Content-Type": file.type || "application/octet-stream" },
      body: file,
    });
    if (!uploadRes.ok) {
      let reason = "Upload failed";
      try {
        const text = await uploadRes.text();
        if (text) reason = text;
      } catch {
        // ignore body parse error
      }
      throw new Error(reason);
    }
    return signedData.url as string;
  };

  const appendMediaItem = (type: "image" | "video", url: string) => {
    const item: MediaItem = { id: `${type}-${Date.now()}-${Math.random()}`, type, url };
    setMediaItems((prev) => {
      if (type === "video") {
        const noVideos = prev.filter((m) => m.type !== "video");
        return [item, ...noVideos];
      }
      return [...prev, item];
    });
  };

  const onUploadImage = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setError(null);
    setUploading(true);
    try {
      const url = await uploadFile(file);
      appendMediaItem("image", url);
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
      const url = await uploadFile(file);
      appendMediaItem("video", url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const addManualMedia = () => {
    const url = manualMediaUrl.trim();
    if (!url) return;
    appendMediaItem(manualMediaType, url);
    setManualMediaUrl("");
  };

  const moveMedia = (index: number, direction: -1 | 1) => {
    setMediaItems((prev) => {
      const target = index + direction;
      if (target < 0 || target >= prev.length) return prev;
      const next = [...prev];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const removeMedia = (index: number) => {
    setMediaItems((prev) => prev.filter((_, i) => i !== index));
  };

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);
    setSubmitting(true);
    try {
      const orderedImages = mediaItems.filter((m) => m.type === "image").map((m) => m.url.trim()).filter(Boolean);
      const orderedVideo = mediaItems.find((m) => m.type === "video")?.url?.trim() || null;
      const payload = {
        ...form,
        currency: form.saleCurrency,
        images: orderedImages,
        videoUrl: orderedVideo,
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
          <span className="block font-medium text-gray-700">Code / SKU (slug) *</span>
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

      <div className="grid gap-4 md:grid-cols-2">
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
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Cost currency</span>
          <select
            value={form.costCurrency}
            onChange={(e) =>
              setForm((f) => ({ ...f, costCurrency: e.target.value as FormValues["costCurrency"] }))
            }
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          >
            <option value="CNY">CNY</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Sale currency</span>
          <select
            value={form.saleCurrency}
            onChange={(e) =>
              setForm((f) => ({ ...f, saleCurrency: e.target.value as FormValues["saleCurrency"] }))
            }
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          >
            <option value="CNY">CNY</option>
            <option value="USD">USD</option>
            <option value="EUR">EUR</option>
          </select>
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
        <label className="text-sm">
          <span className="block font-medium text-gray-700">Asset status</span>
          <select
            value={form.assetStatus}
            onChange={(e) =>
              setForm((f) => ({ ...f, assetStatus: e.target.value as FormValues["assetStatus"] }))
            }
            className="mt-1 w-full rounded border border-gray-300 px-3 py-2"
          >
            <option value="raw">raw</option>
            <option value="processed">processed</option>
            <option value="published">published</option>
          </select>
        </label>
      </div>

      <div className="space-y-3 rounded border border-gray-200 p-4">
        <p className="text-sm font-medium text-gray-700">Media (images + video in one panel)</p>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="text-sm">
            <span className="block font-medium text-gray-700">Upload image</span>
            <input type="file" accept="image/*" onChange={onUploadImage} className="mt-1 block w-full text-sm" />
          </label>
          <label className="text-sm">
            <span className="block font-medium text-gray-700">Upload video</span>
            <input type="file" accept="video/*" onChange={onUploadVideo} className="mt-1 block w-full text-sm" />
          </label>
        </div>
        <div className="grid gap-3 md:grid-cols-[120px_1fr_auto]">
          <select
            value={manualMediaType}
            onChange={(e) => setManualMediaType(e.target.value as "image" | "video")}
            className="rounded border border-gray-300 px-2 py-2 text-sm"
          >
            <option value="image">Image URL</option>
            <option value="video">Video URL</option>
          </select>
          <input
            value={manualMediaUrl}
            onChange={(e) => setManualMediaUrl(e.target.value)}
            placeholder="https://..."
            className="rounded border border-gray-300 px-3 py-2 text-sm"
          />
          <button
            type="button"
            onClick={addManualMedia}
            className="rounded border border-gray-300 px-3 py-2 text-sm hover:bg-gray-50"
          >
            Add
          </button>
        </div>
        {mediaItems.length === 0 ? (
          <p className="text-xs text-gray-500">No media yet.</p>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {mediaItems.map((item, index) => (
              <div key={item.id} className="rounded border border-gray-200 p-2">
                <div className="relative aspect-square overflow-hidden rounded bg-gray-100">
                  {item.type === "image" ? (
                    <Image
                      src={item.url}
                      alt={`media-${index + 1}`}
                      fill
                      className="object-cover"
                      unoptimized
                    />
                  ) : (
                    <button
                      type="button"
                      onClick={() => setPreviewVideoUrl(item.url)}
                      className="flex h-full w-full items-center justify-center bg-gray-900 text-sm text-white"
                    >
                      Preview video
                    </button>
                  )}
                </div>
                <p className="mt-1 truncate text-xs text-gray-600">
                  #{index + 1} · {item.type}
                </p>
                <div className="mt-2 flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => moveMedia(index, -1)}
                    className="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    onClick={() => moveMedia(index, 1)}
                    className="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
                  >
                    ↓
                  </button>
                  <button
                    type="button"
                    onClick={() => removeMedia(index)}
                    className="ml-auto rounded border border-red-300 px-2 py-1 text-xs text-red-600 hover:bg-red-50"
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
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
      {previewVideoUrl && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-2xl rounded-lg bg-white p-3">
            <div className="mb-2 flex justify-end">
              <button
                type="button"
                onClick={() => setPreviewVideoUrl(null)}
                className="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50"
              >
                Close
              </button>
            </div>
            <video src={previewVideoUrl} controls className="aspect-video w-full rounded bg-black" autoPlay />
          </div>
        </div>
      )}
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

