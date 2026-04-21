import { createRoute, OpenAPIHono, z } from "@hono/zod-openapi";
import { db } from "../db.js";
import { installations, measurements } from "../schema.js";
import { InstallationIdSchema, PushBodySchema } from "../validation.js";

const app = new OpenAPIHono();

const pushRoute = createRoute({
  method: "post",
  path: "/{installation_id}",
  request: {
    params: z.object({
      installation_id: InstallationIdSchema,
    }),
    headers: z.object({
      authorization: z.string().openapi({
        example: "Bearer your_push_token",
        description: "Bearer token for authorized updates",
      }),
    }),
    body: {
      content: {
        "application/json": {
          schema: PushBodySchema,
        },
      },
    },
  },
  responses: {
    201: {
      content: {
        "application/json": {
          schema: z.object({
            id: z.number(),
          }),
        },
      },
      description: "Measurement created",
    },
    401: {
      description: "Unauthorized",
    },
    400: {
      description: "Invalid input",
    },
    500: {
      description: "Database error",
    },
  },
});

app.openapi(pushRoute, async (c) => {
  const { installation_id: installationId } = c.req.valid("param");
  const { authorization } = c.req.valid("header");
  const pushData = c.req.valid("json");

  const expectedToken = process.env.PUSH_TOKEN;
  if (!expectedToken || authorization !== `Bearer ${expectedToken}`) {
    return c.json({ error: "Unauthorized" }, 401);
  }

  try {
    await db
      .insert(installations)
      .values({
        id: installationId,
        lastSeen: new Date(),
      })
      .onConflictDoUpdate({
        target: installations.id,
        set: { lastSeen: new Date() },
      });

    const [inserted] = await db
      .insert(measurements)
      .values({
        installationId,
        capturedAt: new Date(pushData.captured_at),
        chlorineStatus: pushData.chlorine.status,
        chlorineDiagnosis: pushData.chlorine.diagnosis,
        chlorinePattern: pushData.chlorine.pattern_detected,
        chlorineBlinking: pushData.chlorine.blinking_leds,
        chlorineSolid: pushData.chlorine.solid_leds,
        chlorineSummary: pushData.chlorine.summary,
        chlorineAction: pushData.chlorine.action_required,
        chlorineRecommended: pushData.chlorine.recommended_action,
        phStatus: pushData.ph.status,
        phDiagnosis: pushData.ph.diagnosis,
        phPattern: pushData.ph.pattern_detected,
        phBlinking: pushData.ph.blinking_leds,
        phSolid: pushData.ph.solid_leds,
        phSummary: pushData.ph.summary,
        phAction: pushData.ph.action_required,
        phRecommended: pushData.ph.recommended_action,
        rawResponse: pushData.raw_response,
      })
      .returning({ id: measurements.id });

    if (!inserted) {
      throw new Error("Failed to insert measurement");
    }

    return c.json({ id: inserted.id }, 201);
  } catch (err) {
    console.error(err);
    return c.json({ error: "Database error" }, 500);
  }
});

export default app;
