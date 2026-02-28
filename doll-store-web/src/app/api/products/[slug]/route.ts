import { NextRequest } from "next/server";
import { getProductBySlug } from "@/lib/data";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ slug: string }> }
) {
  const { slug } = await params;
  const product = getProductBySlug(slug);
  if (!product) return Response.json({ error: "Not found" }, { status: 404 });
  return Response.json(product);
}
