import { findDocumentById, deleteDocument } from "../../../../lib/db";

export async function GET(
  req: Request,
  { params }: { params: { id: string } }
) {
  const userId = req.headers.get("x-user-id");
  if (!userId) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }
  const doc = await findDocumentById(params.id);
  if (!doc) {
    return Response.json({ error: "not found" }, { status: 404 });
  }
  return Response.json(doc);
}

export async function DELETE(
  req: Request,
  { params }: { params: { id: string } }
) {
  const userId = req.headers.get("x-user-id");
  if (!userId) {
    return Response.json({ error: "unauthorized" }, { status: 401 });
  }
  await deleteDocument(params.id);
  return new Response(null, { status: 204 });
}
