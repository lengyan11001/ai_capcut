const SUPPORTED_COUNTRIES = new Set([
  "US",
  "CA",
  "GB",
  "DE",
  "FR",
  "IT",
  "ES",
  "NL",
  "BE",
  "AT",
  "SE",
  "PL",
  "PT",
  "IE",
  "DK",
  "FI",
  "CZ",
  "HU",
  "RO",
  "GR",
]);

const NAME_TO_CODE: Record<string, string> = {
  "UNITED STATES": "US",
  "USA": "US",
  "CANADA": "CA",
  "UNITED KINGDOM": "GB",
  "UK": "GB",
  "GERMANY": "DE",
  "FRANCE": "FR",
  "ITALY": "IT",
  "SPAIN": "ES",
  "NETHERLANDS": "NL",
  "BELGIUM": "BE",
  "AUSTRIA": "AT",
  "SWEDEN": "SE",
  "POLAND": "PL",
  "PORTUGAL": "PT",
  "IRELAND": "IE",
  "DENMARK": "DK",
  "FINLAND": "FI",
  "CZECH REPUBLIC": "CZ",
  "HUNGARY": "HU",
  "ROMANIA": "RO",
  "GREECE": "GR",
};

export function normalizeCountryCode(value: string): string {
  const normalized = value.trim().toUpperCase();
  if (normalized.length === 2) return normalized;
  return NAME_TO_CODE[normalized] ?? "";
}

export function isCountrySupported(value: string): boolean {
  const code = normalizeCountryCode(value);
  if (!code) return false;
  return SUPPORTED_COUNTRIES.has(code);
}

export function getSupportedCountryCodes(): string[] {
  return Array.from(SUPPORTED_COUNTRIES);
}

