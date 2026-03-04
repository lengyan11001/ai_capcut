import { createClient } from "@supabase/supabase-js";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
const dryRun = process.argv.includes("--dry-run");

if (!supabaseUrl || !serviceRoleKey) {
  console.error("Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY");
  process.exit(1);
}

const CJK_REGEX = /[\u3400-\u9FFF]/g;

function stripCjk(input) {
  if (!input || typeof input !== "string") return "";
  return input
    .replace(CJK_REGEX, "")
    .replace(/[；]/g, ";")
    .replace(/[：]/g, ":")
    .replace(/\s+/g, " ")
    .trim();
}

const supabase = createClient(supabaseUrl, serviceRoleKey, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const { data, error } = await supabase
  .from("products")
  .select("id, slug, source_type, specs")
  .eq("source_type", "overseas_us")
  .limit(5000);

if (error) {
  console.error("Load failed:", error.message);
  process.exit(1);
}

const rows = data ?? [];
console.log(`US products loaded: ${rows.length}`);
if (dryRun) {
  console.log("Dry run enabled. No DB writes.");
  process.exit(0);
}

let updated = 0;
for (const row of rows) {
  const specs = row.specs && typeof row.specs === "object" ? row.specs : {};
  const code = String(specs.supplier_code || row.slug || "").trim();
  const stock = String(specs.supplier_stock || "").trim();
  const grossWeight = stripCjk(String(specs.gross_weight || "")).replace(/\s*kg$/i, "");
  const packageStats = stripCjk(String(specs.vital_statistics || specs.package_stats || ""));
  const downloadLink = String(specs.download_link || "").trim();

  const nextSpecs = {
    supplier: "supplier_us_inventory",
    supplier_code: code,
    supplier_stock: stock,
    gross_weight: grossWeight ? `${grossWeight} kg` : "",
    package_stats: packageStats,
    download_link: downloadLink,
  };

  const { error: updateError } = await supabase
    .from("products")
    .update({
      name: `US Local Product ${code || row.slug}`,
      description: `Supplier US local stock item ${code || row.slug}. In-stock item from US warehouse${
        stock ? ` (stock: ${stock})` : ""
      }.`,
      material: "TPE/Silicone",
      specs: nextSpecs,
      updated_at: new Date().toISOString(),
    })
    .eq("id", row.id);

  if (updateError) {
    console.warn(`Skip ${row.slug}: ${updateError.message}`);
    continue;
  }
  updated += 1;
}

console.log(`English normalization completed. Updated ${updated} records.`);
