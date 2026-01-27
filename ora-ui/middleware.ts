// [SUSPENDED] Auth disabled per user request until domain purchase
// export { auth as middleware } from "@/auth"

// Define empty middleware to satisfy Next.js requirement "must export middleware"
import { NextResponse } from "next/server";
export function middleware() {
    return NextResponse.next();
}

export const config = {
    // Match nothing effectively, or just let it run and do nothing
    matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
}
