import { OpenAPIHono } from "@hono/zod-openapi";
import { logger } from "hono/logger";
import { swaggerUI } from "@hono/swagger-ui";
import debugRoute from "./routes/debug.js";
import installationsRoute from "./routes/installations.js";
import latestRoute from "./routes/latest.js";
import pushRoute from "./routes/push.js";

export function createApp() {
  const app = new OpenAPIHono();
  app.use("*", logger());

  app.route("/push", pushRoute);
  app.route("/latest", latestRoute);
  app.route("/debug", debugRoute);
  app.route("/installations", installationsRoute);

  app.get("/health", (c) => c.json({ ok: true }));

  app.doc("/openapi.json", {
    openapi: "3.0.0",
    info: {
      title: "Pahlen Monitor API",
      version: "1.0.0",
    },
  });

  app.get("/docs", swaggerUI({ url: "/openapi.json" }));
  return app;
}
