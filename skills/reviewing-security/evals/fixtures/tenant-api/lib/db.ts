import { db } from "./client";

export async function findDocumentById(id: string) {
  const result = await db.query("SELECT * FROM documents WHERE id = $1", [id]);
  return result.rows[0];
}

export async function deleteDocument(id: string) {
  await db.query("DELETE FROM documents WHERE id = $1", [id]);
}

export async function listUsers() {
  const result = await db.query("SELECT id, email, role FROM users");
  return result.rows;
}
