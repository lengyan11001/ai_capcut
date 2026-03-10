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
  return normalizeUnits(normalizeSpaces(text.replace(/，/g, ", ")));
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

export function localizeMaterial(material: string, lang: Lang): string {
  if (lang === "zh") return material;
  return translateMaterialValue(material);
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
      return normalizeUnits(raw);
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
  if (parts.length === 0) return normalizeUnits(raw);
  return parts.join(" ");
}
