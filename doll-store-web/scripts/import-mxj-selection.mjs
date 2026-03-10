import { readFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import { resolve, extname } from "node:path";
import { mkdtempSync, rmSync, readdirSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { spawnSync } from "node:child_process";
import { createClient } from "@supabase/supabase-js";
import XLSX from "xlsx";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
const assetBucket = process.env.SUPABASE_ASSET_BUCKET ?? "product-media";

if (!supabaseUrl || !serviceRoleKey) {
  console.error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
  process.exit(1);
}

const SOURCE_DIR = "/Users/ncnslks/Downloads/mxj";
const XLSX_PATH = resolve(SOURCE_DIR, "副本3月9日刘总选品.xlsx");
const FX_RATE = 7.2;
const MARKUP = 3.5;
const MAX_IMAGES = Number(process.env.MXJ_MAX_IMAGES ?? 12);
const MAX_VIDEO_BYTES = Number(process.env.MXJ_MAX_VIDEO_BYTES ?? 50 * 1024 * 1024);
const onlyArg = process.argv.find((arg) => arg.startsWith("--only="));
const onlyList = onlyArg
  ? onlyArg
      .slice("--only=".length)
      .split(",")
      .map((v) => v.trim().toLowerCase())
      .filter(Boolean)
  : [];
const skipMedia = process.argv.includes("--skip-media");

function toMb(bytes) {
  return Math.round((bytes / 1024 / 1024) * 10) / 10;
}

const NAME_TO_ZIP = {
  "硅胶名器2号": "硅胶名器2号新视觉已修.zip",
  芷琳: "7.5斤硅胶胸模芷琳.zip",
  思香: "14斤硅胶半身思香.zip",
  "雯雯2号": "12公斤雯雯2号.zip",
  苏亦芙: "苏亦芙视觉2已修.zip",
};

const NAME_TO_SLUG = {
  "硅胶名器2号": "mxj-sgjq-2",
  芷琳: "mxj-zhilin",
  思香: "mxj-sixiang",
  "雯雯2号": "mxj-wenwen-2",
  苏亦芙: "mxj-suyifu",
};

function normalizeName(input) {
  return String(input ?? "").trim();
}

function toNumber(value) {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
}

function getCategoryId(productName) {
  return productName.includes("名器") ? "accessories" : "silicone";
}

function listFilesRecursive(dir) {
  const result = [];
  for (const entry of readdirSync(dir)) {
    const full = resolve(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) {
      result.push(...listFilesRecursive(full));
    } else {
      result.push(full);
    }
  }
  return result;
}

function isImageFile(path) {
  const ext = extname(path).toLowerCase();
  return [".jpg", ".jpeg", ".png", ".webp"].includes(ext);
}

function isVideoFile(path) {
  const ext = extname(path).toLowerCase();
  return [".mp4", ".mov", ".webm"].includes(ext);
}

function detectContentType(path) {
  const ext = extname(path).toLowerCase();
  if (ext === ".jpg" || ext === ".jpeg") return "image/jpeg";
  if (ext === ".png") return "image/png";
  if (ext === ".webp") return "image/webp";
  if (ext === ".mp4") return "video/mp4";
  if (ext === ".mov") return "video/quicktime";
  if (ext === ".webm") return "video/webm";
  return "application/octet-stream";
}

function hashedName(path) {
  const ext = extname(path).toLowerCase();
  const hash = createHash("sha1").update(path).digest("hex").slice(0, 16);
  return `media-${hash}${ext}`;
}

function unzipToTemp(zipPath, productSlug) {
  const dir = mkdtempSync(resolve(tmpdir(), `mxj-${productSlug}-`));
  const rs = spawnSync("bsdtar", ["-xf", zipPath, "-C", dir], { encoding: "utf-8" });
  if (rs.status !== 0) {
    throw new Error(`extract failed for ${zipPath}: ${rs.stderr || rs.stdout}`);
  }
  return dir;
}

function compressVideoToLimit(videoPath, productSlug) {
  const outputPath = resolve(tmpdir(), `mxj-${productSlug}-${Date.now()}-compressed.mp4`);
  const rs = spawnSync(
    "ffmpeg",
    [
      "-y",
      "-i",
      videoPath,
      "-vf",
      "scale='min(1280,iw)':-2",
      "-c:v",
      "libx264",
      "-preset",
      "veryfast",
      "-crf",
      "30",
      "-c:a",
      "aac",
      "-b:a",
      "96k",
      "-movflags",
      "+faststart",
      "-fs",
      String(MAX_VIDEO_BYTES),
      outputPath,
    ],
    { encoding: "utf-8" }
  );
  if (rs.status !== 0) {
    rmSync(outputPath, { force: true });
    throw new Error(`ffmpeg compress failed for ${productSlug}: ${rs.stderr || rs.stdout}`);
  }
  return outputPath;
}

async function uploadMediaForProduct(supabase, productName, productSlug) {
  if (skipMedia) return { images: [], videoUrl: null };
  const zipFilename = NAME_TO_ZIP[productName];
  if (!zipFilename) {
    console.warn(`No zip mapping for product: ${productName}`);
    return { images: [], videoUrl: null };
  }
  const zipPath = resolve(SOURCE_DIR, zipFilename);
  const tempDir = unzipToTemp(zipPath, productSlug);
  try {
    const allFiles = listFilesRecursive(tempDir);
    const imagePaths = allFiles.filter(isImageFile).sort().slice(0, MAX_IMAGES);
    const videoPath = allFiles.filter(isVideoFile).sort()[0];

    const imageUrls = [];
    for (const imagePath of imagePaths) {
      const storagePath = `products/mxj/${productSlug}/${hashedName(imagePath)}`;
      const body = await readFile(imagePath);
      const { error } = await supabase.storage.from(assetBucket).upload(storagePath, body, {
        upsert: true,
        contentType: detectContentType(imagePath),
      });
      if (error) {
        console.warn(`Skip image upload failed (${storagePath}): ${error.message}`);
        continue;
      }
      const { data } = supabase.storage.from(assetBucket).getPublicUrl(storagePath);
      imageUrls.push(data.publicUrl);
    }

    let videoUrl = null;
    if (videoPath) {
      const originalStats = statSync(videoPath);
      let uploadPath = videoPath;
      let removeAfterUpload = false;
      if (originalStats.size > MAX_VIDEO_BYTES) {
        console.log(
          `Video too large for ${productSlug} (${toMb(originalStats.size)}MB), compressing to <= ${toMb(
            MAX_VIDEO_BYTES
          )}MB...`
        );
        uploadPath = compressVideoToLimit(videoPath, productSlug);
        removeAfterUpload = true;
      }
      const uploadStats = statSync(uploadPath);
      if (uploadStats.size > MAX_VIDEO_BYTES) {
        if (removeAfterUpload) rmSync(uploadPath, { force: true });
        throw new Error(
          `video still too large after compress for ${productSlug}: ${toMb(uploadStats.size)}MB > ${toMb(
            MAX_VIDEO_BYTES
          )}MB`
        );
      }
      const storagePath = `products/mxj/${productSlug}/${hashedName(uploadPath)}`;
      const body = await readFile(uploadPath);
      const { error } = await supabase.storage.from(assetBucket).upload(storagePath, body, {
        upsert: true,
        contentType: detectContentType(uploadPath),
      });
      if (removeAfterUpload) rmSync(uploadPath, { force: true });
      if (error) {
        throw new Error(`upload video failed (${storagePath}): ${error.message}`);
      }
      const { data } = supabase.storage.from(assetBucket).getPublicUrl(storagePath);
      videoUrl = data.publicUrl;
    }

    return { images: imageUrls, videoUrl };
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

function buildDescription(row) {
  const lines = [];
  const feature = String(row["产品特点"] ?? "").trim();
  const size = String(row["产品尺寸"] ?? "").replace(/\s+/g, " ").trim();
  const packSize = String(row["外包装尺寸（CM）"] ?? "").replace(/\s+/g, " ").trim();
  const material = String(row["材质"] ?? "").trim();

  if (feature) lines.push(feature);
  if (material) lines.push(`Material: ${material}`);
  if (size) lines.push(`Product size: ${size}`);
  if (packSize) lines.push(`Packaging size: ${packSize}`);
  return lines.join(" ");
}

async function main() {
  const wb = XLSX.readFile(XLSX_PATH);
  const sheet = wb.Sheets[wb.SheetNames[0]];
  const rows = XLSX.utils.sheet_to_json(sheet, { defval: "" });

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false, autoRefreshToken: false },
  });

  const upsertRows = [];
  for (const row of rows) {
    const productName = normalizeName(row["产品名称"]);
    if (!productName) continue;

    const slug = NAME_TO_SLUG[productName] ?? `mxj-${productName}`;
    if (onlyList.length > 0) {
      const hit = onlyList.includes(slug.toLowerCase()) || onlyList.includes(productName.toLowerCase());
      if (!hit) continue;
    }
    const costCny = toNumber(row["供货价格"]);
    if (!costCny) {
      console.warn(`Skip ${productName}: invalid cost price`);
      continue;
    }

    const saleUsd = Math.round((costCny / FX_RATE) * MARKUP);
    console.log(`Processing ${productName} (${slug}) ...`);
    const media = await uploadMediaForProduct(supabase, productName, slug);

    upsertRows.push({
      slug,
      name: productName,
      description: buildDescription(row),
      category_id: getCategoryId(productName),
      material: String(row["材质"] ?? "").trim() || "Silicone",
      currency: "USD",
      cost_currency: "CNY",
      sale_currency: "USD",
      cost_price: costCny,
      sale_price: saleUsd,
      compare_at_price: null,
      source_type: "origin",
      shipping_quote_mode: "quote_after_confirm",
      is_free_shipping_overseas: false,
      asset_status: "published",
      images: media.images,
      video_url: media.videoUrl,
      specs: {
        supplier: "mxj",
        supplier_name: "miao-xiaojie",
        source_file: "副本3月9日刘总选品.xlsx",
        product_weight: String(row["产品重量"] ?? "").trim(),
        vaginal_size_cm: String(row["阴道尺寸（CM）"] ?? "").trim(),
        anal_size_cm: String(row["肛门尺寸（CM）"] ?? "").trim(),
        product_size: String(row["产品尺寸"] ?? "").trim(),
        package_size_cm: String(row["外包装尺寸（CM）"] ?? "").trim(),
        feature: String(row["产品特点"] ?? "").trim(),
      },
      add_on_options: [],
      visible_regions: ["ALL"],
      shippable_countries: [],
      featured: true,
    });
    console.log(`Prepared ${productName}: cost CNY ${costCny} -> sale USD ${saleUsd}, images=${media.images.length}`);
  }

  if (upsertRows.length === 0) {
    console.log("No valid rows to import.");
    return;
  }

  const { error } = await supabase.from("products").upsert(upsertRows, { onConflict: "slug" });
  if (error) {
    console.error("Upsert failed:", error.message);
    process.exit(1);
  }
  console.log(`Imported/updated ${upsertRows.length} mxj products.`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
