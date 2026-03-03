import { NextRequest } from "next/server";

const ALLOWED_PREFIX = "http://47.107.244.246:3000/uploads/";

export async function GET(request: NextRequest) {
  const sourceUrl = request.nextUrl.searchParams.get("url");
  if (!sourceUrl) {
    return Response.json({ error: "Missing url parameter" }, { status: 400 });
  }

  if (!sourceUrl.startsWith(ALLOWED_PREFIX)) {
    return Response.json({ error: "URL is not allowed" }, { status: 400 });
  }

  const upstream = await fetch(sourceUrl, {
    headers: { Accept: "image/*" },
  });

  if (!upstream.ok) {
    return Response.json(
      { error: `Failed to fetch image: ${upstream.status}` },
      { status: upstream.status }
    );
  }

  const contentType = upstream.headers.get("content-type") ?? "image/png";
  const buffer = await upstream.arrayBuffer();

  return new Response(buffer, {
    headers: {
      "Content-Type": contentType,
      "Cache-Control": "public, max-age=3600, s-maxage=3600",
    },
  });
}

