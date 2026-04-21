import "dotenv/config";
import { serve } from "@hono/node-server";
import { createApp } from "./app.js";

const port = Number(process.env.PORT ?? 3000);
const app = createApp();
serve({ fetch: app.fetch, port });

console.log(`Listening on port ${port.toString()}`);
console.log(`Documentation available at http://localhost:${port.toString()}/docs`);
