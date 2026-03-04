import { NextRequest } from "next/server";
import { getDebugRegion, getProductBySlug, getRegionFromCountry } from "@/lib/data";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params;
  const debugRegion = getDebugRegion(request.nextUrl.searchParams.get("debug_region"));
  const debugAllParam = request.nextUrl.searchParams.get("debug_all");
  const debugAll = debugAllParam === "1" || debugAllParam === "true";
  const region = debugRegion ?? getRegionFromCountry(request.headers.get("x-vercel-ip-country"));
  const product = await getProductBySlug(slug, { region, debugAll });
  if (!product) return Response.json({ error: "Not found" }, { status: 404 });
  return Response.json(product);
}
