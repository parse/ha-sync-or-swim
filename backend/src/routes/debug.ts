import { createRoute, OpenAPIHono, z } from "@hono/zod-openapi";
import { InstallationIdSchema, LatestMeasurementSchema } from "../validation.js";

const app = new OpenAPIHono();

const debugRoute = createRoute({
  method: "get",
  path: "/{installation_id}",
  request: {
    params: z.object({
      installation_id: InstallationIdSchema,
    }),
    headers: z.object({
      authorization: z.string().openapi({
        example: "Bearer your_debug_token",
      }),
    }),
  },
  responses: {
    200: {
      content: {
        "application/json": {
          schema: LatestMeasurementSchema.extend({
            debug: z.boolean(),
          }),
        },
      },
      description: "Mock measurement data",
    },
    401: {
      description: "Unauthorized",
    },
  },
});

app.openapi(debugRoute, (c) => {
  const { installation_id: installationId } = c.req.valid("param");
  const { authorization } = c.req.valid("header");

  const expectedToken = process.env.DEBUG_TOKEN;

  const token = authorization.replace("Bearer ", "");
  if (!expectedToken || token !== expectedToken) {
    return c.json({ error: "Unauthorized" }, 401);
  }

  return c.json({
    installation_id: installationId,
    captured_at: new Date().toISOString(),
    pushed_at: new Date().toISOString(),
    raw_response: null,
    chlorine: {
      status: "ok",
      diagnosis: "Auto mode",
      pattern_detected: "LED 4 solid",
      blinking_leds: [],
      solid_leds: ["LED 4 – green"],
      summary: "Normal operation.",
      action_required: false,
      recommended_action: "No action required",
    },
    ph: {
      status: "warning",
      diagnosis: "Standby mode",
      pattern_detected: "LED 5 blinking",
      blinking_leds: ["LED 5 – yellow"],
      solid_leds: [],
      summary: "pH unit in standby.",
      action_required: false,
      recommended_action: "Check if the pump is running",
    },
    debug: true,
  });
});

export default app;
