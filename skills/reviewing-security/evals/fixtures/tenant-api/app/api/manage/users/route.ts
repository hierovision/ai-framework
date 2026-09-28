import { listUsers } from "../../../../lib/db";

export async function GET(req: Request) {
  const userId = req.headers.get("x-user-id");
  if (!userId) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }
  const users = await listUsers();
  return Response.json(users);
}
