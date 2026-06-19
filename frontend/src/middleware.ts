import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Paths accessible without auth
const PUBLIC_PREFIXES = ["/login", "/register", "/verify-email", "/invitations"];

// Paths that should redirect to dashboard if already authed
const AUTH_ONLY_PREFIXES = ["/login", "/register"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token = request.cookies.get("access_token")?.value;

  const isPublic = PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));

  if (!token && !isPublic) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (token && AUTH_ONLY_PREFIXES.some((p) => pathname.startsWith(p))) {
    return NextResponse.redirect(new URL("/", request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Skip Next.js internals, static assets, and API routes
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};
