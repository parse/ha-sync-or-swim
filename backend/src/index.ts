import "dotenv/config";
import { serve } from "@hono/node-server";
import { OpenAPIHono } from "@hono/zod-openapi";
import { logger } from "hono/logger";
import { swaggerUI } from "@hono/swagger-ui";
import pushRoute from "./routes/push.js";
import latestRoute from "./routes/latest.js";
import debugRoute from "./routes/debug.js";
import installationsRoute from "./routes/installations.js";

const app = new OpenAPIHono();
app.use("*", logger());

app.route("/push", pushRoute);
app.route("/latest", latestRoute);
app.route("/debug", debugRoute);
app.route("/installations", installationsRoute);

app.get("/health", (c) => c.json({ ok: true }));

// OpenAPI
app.doc("/openapi.json", {
  openapi: "3.0.0",
  info: {
    title: "Pahlen Monitor API",
    version: "1.0.0",
  },
});

app.get("/docs", swaggerUI({ url: "/openapi.json" }));

const port = Number(process.env.PORT ?? 3000);
serve({ fetch: app.fetch, port });

console.log(`Listening on port ${port.toString()}`);
console.log(`Documentation available at http://localhost:${port.toString()}/docs`);
