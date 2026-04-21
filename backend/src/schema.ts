import { pgTable, text, boolean, jsonb, serial, timestamp, index } from "drizzle-orm/pg-core";

export const installations = pgTable("installations", {
  id: text("id").primaryKey(),
  lastSeen: timestamp("last_seen", { withTimezone: true }).notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).defaultNow(),
});

export const measurements = pgTable(
  "measurements",
  {
    id: serial("id").primaryKey(),
    installationId: text("installation_id")
      .notNull()
      .references(() => installations.id),
    capturedAt: timestamp("captured_at", { withTimezone: true }).notNull(),
    pushedAt: timestamp("pushed_at", { withTimezone: true }).defaultNow(),

    // Free chlorine unit (left)
    chlorineStatus: text("chlorine_status").notNull(),
    chlorineDiagnosis: text("chlorine_diagnosis"),
    chlorinePattern: text("chlorine_pattern"),
    chlorineBlinking: jsonb("chlorine_blinking").$type<string[]>(),
    chlorineSolid: jsonb("chlorine_solid").$type<string[]>(),
    chlorineSummary: text("chlorine_summary"),
    chlorineAction: boolean("chlorine_action").notNull().default(false),
    chlorineRecommended: text("chlorine_recommended"),

    // pH unit (right)
    phStatus: text("ph_status").notNull(),
    phDiagnosis: text("ph_diagnosis"),
    phPattern: text("ph_pattern"),
    phBlinking: jsonb("ph_blinking").$type<string[]>(),
    phSolid: jsonb("ph_solid").$type<string[]>(),
    phSummary: text("ph_summary"),
    phAction: boolean("ph_action").notNull().default(false),
    phRecommended: text("ph_recommended"),

    rawResponse: text("raw_response"),
  },
  (table) => [index("idx_measurements_inst_captured").on(table.installationId, table.capturedAt)],
);

// Shared types for use in routes and HA plugin
export interface UnitAnalysis {
  status: "ok" | "warning" | "error" | "unknown";
  diagnosis: string | null;
  pattern_detected: string | null;
  blinking_leds: string[];
  solid_leds: string[];
  summary: string;
  action_required: boolean;
  recommended_action: string;
}
