import { createRoute, OpenAPIHono, z } from "@hono/zod-openapi";
import { db } from "../db.js";
import { installations } from "../schema.js";
import { desc } from "drizzle-orm";

const app = new OpenAPIHono();

const installationsRoute = createRoute({
  method: "get",
  path: "/",
  request: {
    headers: z.object({
      authorization: z.string().openapi({
        example: "Bearer your_token",
      }),
    }),
  },
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
    401: {
      description: "Unauthorized",
    },
  },
});

app.openapi(installationsRoute, async (c) => {
  const { authorization } = c.req.valid("header");

  const expectedToken = process.env.PUSH_TOKEN;

  if (!expectedToken || authorization !== `Bearer ${expectedToken}`) {
    return c.json({ error: "Unauthorized" }, 401);
  }

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
