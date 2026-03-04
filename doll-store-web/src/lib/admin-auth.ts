import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import type { NextRequest } from "next/server";

const SESSION_COOKIE = "admin_session";
const DEFAULT_SESSION_VALUE = "ok";

function getAdminPassword() {
  return process.env.ADMIN_PANEL_PASSWORD ?? "";
}

function getSessionSecret() {
  return process.env.ADMIN_SESSION_SECRET ?? DEFAULT_SESSION_VALUE;
}

export function isAdminPasswordValid(password: string): boolean {
  const expected = getAdminPassword();
  return Boolean(expected) && password === expected;
}

export function getAdminSessionCookie() {
  return {
    name: SESSION_COOKIE,
    value: getSessionSecret(),
    httpOnly: true,
    sameSite: "lax" as const,
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 12,
  };
}

export function isAdminRequestAuthorized(request: NextRequest): boolean {
  return request.cookies.get(SESSION_COOKIE)?.value === getSessionSecret();
}

export async function requireAdminSession() {
  const store = await cookies();
  const ok = store.get(SESSION_COOKIE)?.value === getSessionSecret();
  if (!ok) redirect("/admin/login");
}

