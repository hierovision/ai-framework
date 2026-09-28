import { db } from "./client";

export const db = {
  query: async (_sql: string, _params: unknown[]) => ({ rows: [] as any[] }),
};
