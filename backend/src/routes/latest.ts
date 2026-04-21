import { createRoute, OpenAPIHono, z } from "@hono/zod-openapi";
import { db } from "../db.js";
import { measurements, type UnitAnalysis } from "../schema.js";
import { eq, desc } from "drizzle-orm";
import { InstallationIdSchema, LatestMeasurementSchema } from "../validation.js";

const app = new OpenAPIHono();

const latestRoute = createRoute({
  method: "get",
  path: "/{installation_id}",
  request: {
    params: z.object({
      installation_id: InstallationIdSchema,
    }),
  },
  responses: {
    200: {
      content: {
        "application/json": {
          schema: LatestMeasurementSchema,
        },
      },
      description: "Latest measurement",
    },
    404: {
      description: "No measurements found",
    },
  },
});

app.openapi(latestRoute, async (c) => {
  const { installation_id: installationId } = c.req.valid("param");

  const latest = await db.query.measurements.findFirst({
    where: eq(measurements.installationId, installationId),
    orderBy: [desc(measurements.capturedAt)],
  });

  if (!latest) {
    return c.json({ error: "No measurements found for this installation" }, 404);
  }

  return c.json({
    installation_id: latest.installationId,
    captured_at: latest.capturedAt.toISOString(),
    pushed_at: latest.pushedAt?.toISOString() ?? null,
    chlorine: {
      status: latest.chlorineStatus as UnitAnalysis["status"],
      diagnosis: latest.chlorineDiagnosis,
      pattern_detected: latest.chlorinePattern,
      blinking_leds: latest.chlorineBlinking,
      solid_leds: latest.chlorineSolid,
      summary: latest.chlorineSummary ?? "",
      action_required: latest.chlorineAction,
      recommended_action: latest.chlorineRecommended ?? "",
    },
    ph: {
      status: latest.phStatus as UnitAnalysis["status"],
      diagnosis: latest.phDiagnosis,
      pattern_detected: latest.phPattern,
      blinking_leds: latest.phBlinking,
      solid_leds: latest.phSolid,
      summary: latest.phSummary ?? "",
      action_required: latest.phAction,
      recommended_action: latest.phRecommended ?? "",
    },
    raw_response: latest.rawResponse,
  });
});

export default app;
