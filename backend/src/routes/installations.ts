import { createRoute, OpenAPIHono, z } from "@hono/zod-openapi";
import { db } from "../db.js";
import { installations } from "../schema.js";
import { desc } from "drizzle-orm";

const app = new OpenAPIHono();

const installationsRoute = createRoute({
  method: "get",
  path: "/",
  responses: {
    200: {
      content: {
        "application/json": {
          schema: z.array(
            z.object({
              id: z.string(),
              last_seen: z.iso.datetime().optional(),
            }),
          ),
        },
      },
      description: "List of all installations",
    },
  },
});

app.openapi(installationsRoute, async (c) => {
  const allInstallations = await db.query.installations.findMany({
    orderBy: [desc(installations.lastSeen)],
  });

  return c.json(
    allInstallations.map((i) => ({
      id: i.id,
      last_seen: i.lastSeen.toISOString(),
    })),
  );
});

export default app;
