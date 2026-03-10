import type { Lang } from "@/lib/i18n";

function hasChinese(input: string): boolean {
  return /[\u3400-\u9fff]/.test(input);
}

function normalizeSpaces(input: string): string {
  return input.replace(/\s+/g, " ").trim();
}

function normalizeUnits(input: string): string {
  return input
    .replace(/×/g, "x")
    .replace(/（/g, "(")
    .replace(/）/g, ")")
    .replace(/(\d+(?:\.\d+)?)\s*CM/gi, "$1 cm")
    .replace(/(\d+(?:\.\d+)?)\s*KG/gi, "$1 kg");
}

function translateMaterialValue(value: string): string {
  return normalizeUnits(
    value
      .replace(/硅胶/g, "Silicone")
      .replace(/实体硅胶/g, "Solid silicone")
      .replace(/TPE/gi, "TPE")
      .replace(/树脂/gi, "Resin")
  );
}

function translateFeatureValue(value: string): string {
  if (!hasChinese(value)) return normalizeUnits(value);
  let text = value;
  const phraseMap: Array<[RegExp, string]> = [
    [/接近真人比例硅胶肥臀/g, "realistic-proportion silicone peach hips"],
    [/可前入、后入、侧入/g, "supports front, rear, and side entry"],
    [/可前入后入侧入/g, "supports front, rear, and side entry"],
    [/蜜桃臀设计撞击感更足/g, "peach-hip design with stronger thrust feedback"],
    [/前入/g, "front entry"],
    [/后入/g, "rear entry"],
    [/侧入/g, "side entry"],
  ];
  for (const [pattern, replacement] of phraseMap) {
    text = text.replace(pattern, replacement);
  }
  const normalized = normalizeUnits(normalizeSpaces(text.replace(/，/g, ", ")));
  return hasChinese(normalized) ? "See product details." : normalized;
}

function translateProductSizeValue(value: string): string {
  const text = normalizeSpaces(value);
  const sizeMatch = text.match(/长\s*(\d+(?:\.\d+)?)\s*宽\s*(\d+(?:\.\d+)?)\s*高\s*(\d+(?:\.\d+)?)/i);
  const waistMatch = text.match(/腰围\s*(\d+(?:\.\d+)?)/i);
  const hipMatch = text.match(/臀围\s*(\d+(?:\.\d+)?)/i);
  if (!sizeMatch && !waistMatch && !hipMatch) {
    return normalizeUnits(text);
  }
  const parts: string[] = [];
  if (sizeMatch) {
    parts.push(`L${sizeMatch[1]} x W${sizeMatch[2]} x H${sizeMatch[3]} cm`);
  }
  if (waistMatch) parts.push(`waist ${waistMatch[1]} cm`);
  if (hipMatch) parts.push(`hips ${hipMatch[1]} cm`);
  return parts.join(", ");
}

function translatePackageSizeValue(value: string): string {
  const cleaned = normalizeUnits(normalizeSpaces(value));
  const match = cleaned.match(/(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)\s*x\s*(\d+(?:\.\d+)?)/i);
  if (!match) return cleaned;
  return `${match[1]} x ${match[2]} x ${match[3]} cm`;
}

const NAME_MAP: Record<string, string> = {
  "硅胶名器2号": "Silicone Pleasure Mold No.2",
  芷琳: "Zhilin",
  思香: "Sixiang",
  "雯雯2号": "Wenwen No.2",
  苏亦芙: "Suyifu",
};

const SLUG_NAME_MAP: Record<string, string> = {
  "mxj-sgjq-2": "Silicone Pleasure Mold No.2",
  "mxj-zhilin": "Zhilin",
  "mxj-sixiang": "Sixiang",
  "mxj-wenwen-2": "Wenwen No.2",
  "mxj-suyifu": "Suyifu",
};

function titleizeFromSlug(slug?: string): string {
  if (!slug) return "Product";
  return slug
    .replace(/[_-]+/g, " ")
    .trim()
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() + part.slice(1))
    .join(" ");
}

export function localizeMaterial(material: string, lang: Lang): string {
  if (lang === "zh") return material;
  const localized = translateMaterialValue(material);
  return hasChinese(localized) ? "See specs" : localized;
}

export function localizeSpecValue(key: string, value: string, lang: Lang): string {
  if (lang === "zh") return value;
  const raw = normalizeSpaces(value);
  switch (key) {
    case "feature":
      return translateFeatureValue(raw);
    case "product_size":
      return translateProductSizeValue(raw);
    case "package_size_cm":
      return translatePackageSizeValue(raw);
    case "product_weight":
      return normalizeUnits(raw);
    default:
      return hasChinese(raw) ? "N/A" : normalizeUnits(raw);
  }
}

export function localizeDescription(description: string, lang: Lang): string {
  if (lang === "zh") return description;
  const raw = normalizeSpaces(description);
  const materialMatch = raw.match(/Material:\s*(.+?)(?=Product size:|Packaging size:|$)/i);
  const productSizeMatch = raw.match(/Product size:\s*(.+?)(?=Packaging size:|$)/i);
  const packageSizeMatch = raw.match(/Packaging size:\s*(.+)$/i);
  const featurePart = raw
    .replace(/Material:\s*(.+?)(?=Product size:|Packaging size:|$)/i, "")
    .replace(/Product size:\s*(.+?)(?=Packaging size:|$)/i, "")
    .replace(/Packaging size:\s*(.+)$/i, "")
    .trim();
  const parts: string[] = [];
  if (featurePart) parts.push(translateFeatureValue(featurePart));
  if (materialMatch?.[1]) parts.push(`Material: ${translateMaterialValue(materialMatch[1].trim())}`);
  if (productSizeMatch?.[1]) parts.push(`Product size: ${translateProductSizeValue(productSizeMatch[1].trim())}`);
  if (packageSizeMatch?.[1]) parts.push(`Packaging size: ${translatePackageSizeValue(packageSizeMatch[1].trim())}`);
  if (parts.length === 0) {
    const fallback = normalizeUnits(raw);
    return hasChinese(fallback) ? "See detailed specifications below." : fallback;
  }
  const merged = parts.join(" ");
  return hasChinese(merged) ? "See detailed specifications below." : merged;
}

export function localizeProductName(name: string, slug: string | undefined, lang: Lang): string {
  if (lang === "zh") return name;
  const raw = normalizeSpaces(name);
  if (!hasChinese(raw)) return raw;
  if (SLUG_NAME_MAP[slug ?? ""]) return SLUG_NAME_MAP[slug ?? ""];
  if (NAME_MAP[raw]) return NAME_MAP[raw];
  return titleizeFromSlug(slug);
}

export function localizeShippingNotice(notice: string, lang: Lang): string {
  if (lang === "zh") return notice;
  const normalized = normalizeSpaces(notice)
    .replace(/运费按收货地区确认后报价。?/g, "Shipping is quoted after destination confirmation.")
    .replace(/海外仓包邮。?/g, "Free shipping from overseas warehouse.")
    .replace(/，/g, ", ");
  return hasChinese(normalized) ? "Shipping is confirmed after destination review." : normalized;
}

export function localizeAddOnOption(option: string, lang: Lang): string {
  if (lang === "zh") return option;
  const normalized = normalizeUnits(normalizeSpaces(option).replace(/，/g, ", "));
  return hasChinese(normalized) ? "Optional add-on (details on request)" : normalized;
}
