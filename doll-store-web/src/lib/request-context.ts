import { headers } from "next/headers";
import { getDebugRegion, getRegionFromCountry, type RegionCode } from "@/lib/data";

export interface RegionContext {
  region: RegionCode;
  debugAll: boolean;
  debugRegion: RegionCode | null;
}

export async function resolveRegionContext(
  searchParams?: Record<string, string | string[] | undefined>
): Promise<RegionContext> {
  const allHeaders = await headers();
  const country = allHeaders.get("x-vercel-ip-country");
  const defaultRegion = getRegionFromCountry(country);

  const regionValue = searchParams?.debug_region;
  const debugRegion = getDebugRegion(Array.isArray(regionValue) ? regionValue[0] : regionValue);

  const debugAllRaw = searchParams?.debug_all;
  const debugAllValue = Array.isArray(debugAllRaw) ? debugAllRaw[0] : debugAllRaw;
  const debugAll = debugAllValue === "1" || debugAllValue === "true";

  return {
    region: debugRegion ?? defaultRegion,
    debugAll,
    debugRegion,
  };
}

