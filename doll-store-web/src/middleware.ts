import { NextRequest, NextResponse } from "next/server";

const BYPASS_COOKIE = "site_access_bypass";

function isBypassKeyValid(input: string | null): boolean {
  const expected = process.env.ACCESS_BYPASS_KEY;
  if (!expected) return false;
  return input === expected;
}

function shouldBlockMainland(): boolean {
  return process.env.BLOCK_MAINLAND_CN !== "false";
}

function getCountryCode(request: NextRequest): string {
  return (request.headers.get("x-vercel-ip-country") ?? "").toUpperCase();
}

export function middleware(request: NextRequest) {
  const url = request.nextUrl.clone();
  const accessKey = url.searchParams.get("access_key");

  if (isBypassKeyValid(accessKey)) {
    url.searchParams.delete("access_key");
    const response = NextResponse.redirect(url);
    response.cookies.set({
      name: BYPASS_COOKIE,
      value: "1",
      httpOnly: true,
      sameSite: "lax",
      secure: process.env.NODE_ENV === "production",
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
    return response;
  }

  const bypass = request.cookies.get(BYPASS_COOKIE)?.value === "1";
  const isMainlandCn = getCountryCode(request) === "CN";

  if (shouldBlockMainland() && isMainlandCn && !bypass) {
    return new NextResponse("403 Forbidden", {
      status: 403,
      headers: { "content-type": "text/plain; charset=utf-8" },
    });
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|robots.txt|sitemap.xml).*)"],
};
