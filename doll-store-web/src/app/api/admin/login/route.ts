import { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { getAdminSessionCookie, isAdminPasswordValid } from "@/lib/admin-auth";

export async function POST(request: NextRequest) {
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return Response.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { password } = body as { password?: string };
  if (!password || !isAdminPasswordValid(password)) {
    return Response.json({ error: "Invalid credentials" }, { status: 401 });
  }

  const response = NextResponse.json({ success: true });
  response.cookies.set(getAdminSessionCookie());
  return response;
}

