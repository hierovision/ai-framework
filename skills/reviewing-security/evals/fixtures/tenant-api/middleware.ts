import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { verifySession } from "./lib/session";

// Authentication is enforced here for every /api request. The handlers below
// can rely on x-user-id / x-user-role being present.
export async function middleware(req: NextRequest) {
  const session = await verifySession(req.cookies.get("session")?.value);
  if (!session) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const requestHeaders = new Headers(req.headers);
  requestHeaders.set("x-user-id", session.userId);
  requestHeaders.set("x-user-role", session.role);
  return NextResponse.next({ request: { headers: requestHeaders } });
}

export const config = { matcher: "/api/:path*" };
