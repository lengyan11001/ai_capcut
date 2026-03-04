import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

if (!supabaseUrl || !serviceRoleKey) {
  console.error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
  process.exit(1);
}

const DEFAULT_SUPPLIER_JSON =
  "/Users/ncnslks/Library/Containers/com.tencent.xinWeChat/Data/Library/Application Support/com.tencent.xinWeChat/2.0b4.0.9/7e76e0f5307b4d8b2d5c379ab9e40f1a/Message/MessageTemp/c623036d3e0174e1e1b87bd8ab619124/File/inventory_raw.json";

const supplierJsonArg = process.argv.find((arg) => arg.startsWith("--file="));
const supplierJsonPath = supplierJsonArg ? supplierJsonArg.slice("--file=".length) : DEFAULT_SUPPLIER_JSON;
const dryRun = process.argv.includes("--dry-run");

const SUPPLIER_ASSET_BASE = "http://47.107.244.246:3000";

function normalizeImage(picture) {
  if (!picture || typeof picture !== "string") return [];
  if (picture.startsWith("http://") || picture.startsWith("https://")) return [picture];
  if (picture.startsWith("/")) return [`${SUPPLIER_ASSET_BASE}${picture}`];
  return [`${SUPPLIER_ASSET_BASE}/${picture}`];
}

function normalizeCurrency(input) {
  if (input === "USD" || input === "EUR" || input === "CNY") return input;
  return "CNY";
}

function toProductRow(item) {
  const code = String(item.code || "").trim();
  if (!code.startsWith("US-")) return null;
  const stock = Number(item.stock ?? 0);
  if (!Number.isFinite(stock) || stock <= 0) return null;

  const usPrice = item?.price?.["美国本土"]?.price ?? 0;
  const usCurrency = normalizeCurrency(item?.price?.["美国本土"]?.currency);
  const priceNumber = Number(usPrice);
  if (!Number.isFinite(priceNumber) || priceNumber <= 0) return null;

  const height = item.height ? String(item.height).trim() : "";
  const color = item.color ? String(item.color).trim() : "";
  const name = `US Local ${height}${color ? ` · ${color}` : ""}`.trim();

  return {
    slug: code,
    name,
    description: `Supplier US local stock item ${code}. Height: ${height || "N/A"}, color: ${
      color || "N/A"
    }, stock: ${stock}.`,
    category_id: "silicone",
    material: "TPE/Silicone",
    currency: usCurrency,
    cost_currency: usCurrency,
    sale_currency: usCurrency,
    cost_price: priceNumber,
    sale_price: priceNumber,
    compare_at_price: null,
    source_type: "overseas_us",
    shipping_quote_mode: "quote_after_confirm",
    is_free_shipping_overseas: false,
    asset_status: "published",
    images: normalizeImage(item.picture),
    video_url: null,
    specs: {
      supplier: "supplier_us_inventory",
      supplier_code: code,
      supplier_stock: String(stock),
      gross_weight: item.gross_weight ? String(item.gross_weight) : "",
      vital_statistics: item.vital_statistics ? String(item.vital_statistics) : "",
      download_link: item.downloadlink ? String(item.downloadlink) : "",
    },
    add_on_options: [],
    visible_regions: ["US"],
    shippable_countries: ["US"],
    featured: false,
  };
}

const supabase = createClient(supabaseUrl, serviceRoleKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const raw = await readFile(resolve(supplierJsonPath), "utf-8");
const list = JSON.parse(raw);
if (!Array.isArray(list)) {
  console.error("Supplier file is not an array:", supplierJsonPath);
  process.exit(1);
}

const rows = list.map(toProductRow).filter(Boolean);

console.log(`Prepared US stock rows: ${rows.length}`);
if (rows.length === 0) process.exit(0);
if (dryRun) {
  console.log("Dry run enabled. No DB writes.");
  console.log("Sample codes:", rows.slice(0, 5).map((r) => r.slug).join(", "));
  process.exit(0);
}

const { error } = await supabase.from("products").upsert(rows, { onConflict: "slug" });
if (error) {
  console.error("Import failed:", error.message);
  process.exit(1);
}

console.log(`Imported/updated ${rows.length} US in-stock products from supplier data.`);
