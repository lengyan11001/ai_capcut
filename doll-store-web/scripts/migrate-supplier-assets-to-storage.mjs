import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
const bucket = process.env.SUPABASE_ASSET_BUCKET || "product-media";
const dryRun = process.argv.includes("--dry-run");

if (!supabaseUrl || !serviceRoleKey) {
  console.error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
  process.exit(1);
}

const SUPPLIER_PREFIXES = [
  "http://47.107.244.246:3000/uploads/",
  "https://47.107.244.246:3000/uploads/",
];

const supabase = createClient(supabaseUrl, serviceRoleKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});

function shouldMigrate(url) {
  return typeof url === "string" && SUPPLIER_PREFIXES.some((prefix) => url.startsWith(prefix));
}

function guessExt(url, contentType) {
  try {
    const pathname = new URL(url).pathname;
    const dot = pathname.lastIndexOf(".");
    if (dot > -1 && dot < pathname.length - 1) {
      return pathname.slice(dot + 1).toLowerCase();
    }
  } catch {}
  if (contentType?.includes("png")) return "png";
  if (contentType?.includes("webp")) return "webp";
  if (contentType?.includes("gif")) return "gif";
  if (contentType?.includes("mp4")) return "mp4";
  return "jpg";
}

async function fetchBinary(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`download failed (${response.status})`);
  const contentType = response.headers.get("content-type") || "application/octet-stream";
  const bytes = Buffer.from(await response.arrayBuffer());
  return { bytes, contentType };
}

const cache = new Map();

async function uploadFromUrl(url, productId, mediaIndex, mediaType) {
  if (cache.has(url)) return cache.get(url);
  const { bytes, contentType } = await fetchBinary(url);
  const ext = guessExt(url, contentType);
  const filePath = `products/migrated/${productId}-${mediaType}-${mediaIndex}-${Date.now()}.${ext}`;
  if (dryRun) {
    const fake = `DRY_RUN:${filePath}`;
    cache.set(url, fake);
    return fake;
  }
  const { error } = await supabase.storage.from(bucket).upload(filePath, bytes, {
    contentType,
    upsert: false,
  });
  if (error) throw new Error(error.message);
  const { data } = supabase.storage.from(bucket).getPublicUrl(filePath);
  cache.set(url, data.publicUrl);
  return data.publicUrl;
}

const { data: rows, error } = await supabase
  .from("products")
  .select("id, slug, images, video_url")
  .order("updated_at", { ascending: false })
  .limit(5000);

if (error) {
  console.error("Load products failed:", error.message);
  process.exit(1);
}

let migratedProductCount = 0;
let migratedAssetCount = 0;

for (const row of rows || []) {
  const oldImages = Array.isArray(row.images) ? row.images : [];
  const nextImages = [...oldImages];
  let changed = false;

  for (let i = 0; i < oldImages.length; i += 1) {
    const url = oldImages[i];
    if (!shouldMigrate(url)) continue;
    try {
      nextImages[i] = await uploadFromUrl(url, row.id, i, "image");
      changed = true;
      migratedAssetCount += 1;
      console.log(`[${row.slug}] image ${i + 1} migrated`);
    } catch (err) {
      console.warn(`[${row.slug}] image ${i + 1} skipped: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  let nextVideoUrl = row.video_url;
  if (shouldMigrate(row.video_url)) {
    try {
      nextVideoUrl = await uploadFromUrl(row.video_url, row.id, 0, "video");
      changed = true;
      migratedAssetCount += 1;
      console.log(`[${row.slug}] video migrated`);
    } catch (err) {
      console.warn(`[${row.slug}] video skipped: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  if (!changed) continue;
  migratedProductCount += 1;
  if (dryRun) continue;

  const { error: updateError } = await supabase
    .from("products")
    .update({
      images: nextImages,
      video_url: nextVideoUrl,
      updated_at: new Date().toISOString(),
    })
    .eq("id", row.id);

  if (updateError) {
    console.warn(`[${row.slug}] update failed: ${updateError.message}`);
  }
}

console.log(
  `Done. products=${migratedProductCount}, assets=${migratedAssetCount}, bucket=${bucket}, dryRun=${dryRun}`
);
