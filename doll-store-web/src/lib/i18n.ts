export type Lang = "en" | "zh";

export function normalizeLang(input?: string | null): Lang {
  if (!input) return "en";
  const lower = input.toLowerCase();
  if (lower === "zh" || lower === "zh-cn" || lower === "cn") return "zh";
  return "en";
}

export function getLangFromSearchParams(
  searchParams?: Record<string, string | string[] | undefined>
): Lang {
  const raw = searchParams?.lang;
  const value = Array.isArray(raw) ? raw[0] : raw;
  return normalizeLang(value);
}

export function t(lang: Lang, en: string, zh: string): string {
  return lang === "zh" ? zh : en;
}
