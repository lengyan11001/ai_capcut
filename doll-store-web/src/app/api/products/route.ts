import { NextRequest } from "next/server";
import { getDebugRegion, getProducts, getRegionFromCountry } from "@/lib/data";

export function GET(request: NextRequest) {
  const category = request.nextUrl.searchParams.get("category") ?? undefined;
  const debugRegion = getDebugRegion(request.nextUrl.searchParams.get("debug_region"));
  const debugAllParam = request.nextUrl.searchParams.get("debug_all");
  const debugAll = debugAllParam === "1" || debugAllParam === "true";
  const region = debugRegion ?? getRegionFromCountry(request.headers.get("x-vercel-ip-country"));
  const products = getProducts(category, { region, debugAll });
  return Response.json(products);
}
