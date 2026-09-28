import { cookies } from "next/headers";

export async function verifySession(_token?: string) {
  // Real implementation checks the signed session against the session store.
  return { userId: "u_1", role: "member" } as { userId: string; role: string } | null;
}
