import { NextRequest } from "next/server";
import { getProducts } from "@/lib/data";

export function GET(request: NextRequest) {
  const category = request.nextUrl.searchParams.get("category") ?? undefined;
  const products = getProducts(category);
  return Response.json(products);
}
