import { z } from "@hono/zod-openapi";

export const UnitAnalysisSchema = z
  .object({
    status: z.enum(["ok", "warning", "error", "unknown"]),
    diagnosis: z.string().nullable(),
    pattern_detected: z.string().nullable(),
    blinking_leds: z.array(z.string()),
    solid_leds: z.array(z.string()),
    summary: z.string(),
    action_required: z.boolean(),
    recommended_action: z.string(),
  })
  .openapi("UnitAnalysis");

export const PushBodySchema = z
  .object({
    captured_at: z.iso.datetime(),
    chlorine: UnitAnalysisSchema,
    ph: UnitAnalysisSchema,
    raw_response: z.string().optional(),
  })
  .openapi("PushBody");

export const InstallationIdSchema = z
  .string()
  .regex(/^[a-z0-9-]{1,64}$/)
  .openapi({
    param: {
      name: "installation_id",
      in: "path",
    },
    example: "my-pool-123",
  });
