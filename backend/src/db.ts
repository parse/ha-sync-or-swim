import postgres from "postgres";
import { drizzle } from "drizzle-orm/postgres-js";
import * as schema from "./schema.js";

const databaseUrl = process.env.DATABASE_URL;
if (!databaseUrl) {
  throw new Error("DATABASE_URL environment variable is not set");
}
const client = postgres(databaseUrl, { max: 5 });
export const db = drizzle(client, { schema });
